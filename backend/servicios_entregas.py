from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import Session

from backend.models import BorradorRespuesta, Calificacion, Entrega, RespuestaAlumno


PUNTO_DESPUES_ELIMINAR_RESPUESTAS = "despues_eliminar_respuestas"
PUNTO_DESPUES_PRIMERA_RESPUESTA = "despues_primera_respuesta"
PUNTO_DESPUES_TODAS_RESPUESTAS = "despues_todas_respuestas"
PUNTO_DESPUES_CALIFICACION = "despues_calificacion"
PUNTO_ANTES_CIERRE = "antes_cierre"
PUNTO_DESPUES_CIERRE = "despues_cierre_antes_commit"
PUNTO_DURANTE_LIBERACION = "durante_liberacion_reserva"

PUNTOS_FALLO_ENVIO = (
    PUNTO_DESPUES_ELIMINAR_RESPUESTAS,
    PUNTO_DESPUES_PRIMERA_RESPUESTA,
    PUNTO_DESPUES_TODAS_RESPUESTAS,
    PUNTO_DESPUES_CALIFICACION,
    PUNTO_ANTES_CIERRE,
    PUNTO_DESPUES_CIERRE,
    PUNTO_DURANTE_LIBERACION,
)

HookTransaccion = Callable[[str], None]


class ReservaEntregaNoValida(RuntimeError):
    pass


class EntregaCerradaDuranteEnvio(RuntimeError):
    pass


def calcular_hash_envio(
    respuestas: Sequence[dict[str, Any]], entregado_automaticamente: bool
) -> str:
    carga = {
        "entregado_automaticamente": entregado_automaticamente,
        "respuestas": sorted(
            (
                {
                    "pregunta_id": int(respuesta["pregunta_id"]),
                    "contenido": str(respuesta["contenido"]),
                }
                for respuesta in respuestas
            ),
            key=lambda respuesta: respuesta["pregunta_id"],
        ),
    }
    serializado = json.dumps(
        carga, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(serializado.encode("utf-8")).hexdigest()


def construir_respuestas_temporales(
    entrega_id: int, respuestas: Sequence[dict[str, Any]]
) -> list[RespuestaAlumno]:
    return [
        RespuestaAlumno(
            entrega_id=entrega_id,
            pregunta_id=int(respuesta["pregunta_id"]),
            contenido=str(respuesta["contenido"]),
        )
        for respuesta in respuestas
    ]


def reservar_entrega(
    db: Session,
    entrega_id: int,
    ahora: datetime,
    caducidad_segundos: int = 120,
) -> str | None:
    """Adquiere una reserva breve e identificada mediante un único UPDATE."""
    if db.in_transaction():
        db.rollback()
    reserva_id = str(uuid4())
    reserva_caducada = ahora - timedelta(seconds=caducidad_segundos)
    reserva_expira_en = ahora + timedelta(seconds=caducidad_segundos)
    try:
        resultado = db.execute(
            update(Entrega)
            .where(
                Entrega.id == entrega_id,
                Entrega.cerrada.is_(False),
                or_(
                    Entrega.procesando.is_(False),
                    Entrega.procesando_desde.is_(None),
                    Entrega.procesando_desde < reserva_caducada,
                    Entrega.reserva_expira_en.is_(None),
                    Entrega.reserva_expira_en < ahora,
                ),
            )
            .values(
                procesando=True,
                procesando_desde=ahora,
                reserva_id=reserva_id,
                reserva_expira_en=reserva_expira_en,
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return reserva_id if resultado.rowcount == 1 else None


def liberar_reserva(
    db: Session,
    entrega_id: int,
    reserva_id: str | None = None,
) -> bool:
    """Libera una reserva abierta; con token solo su propietario puede hacerlo."""
    if db.in_transaction():
        db.rollback()
    condiciones = [Entrega.id == entrega_id, Entrega.cerrada.is_(False)]
    if reserva_id is not None:
        condiciones.append(Entrega.reserva_id == reserva_id)
    try:
        resultado = db.execute(
            update(Entrega)
            .where(*condiciones)
            .values(
                procesando=False,
                procesando_desde=None,
                reserva_id=None,
                reserva_expira_en=None,
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return resultado.rowcount == 1


def _inyectar(hook: HookTransaccion | None, punto: str) -> None:
    if hook is not None:
        hook(punto)


def persistir_envio_atomico(
    db: Session,
    *,
    entrega_id: int,
    reserva_id: str,
    respuestas: Sequence[dict[str, Any]],
    resultado: dict[str, Any],
    hora_entrega: datetime,
    entregado_automaticamente: bool,
    hash_envio: str,
    hook_transaccion: HookTransaccion | None = None,
) -> Calificacion:
    """Guarda respuestas, calificación y cierre en una sola transacción."""
    if db.in_transaction():
        db.rollback()

    with db.begin():
        entrega = db.scalar(
            select(Entrega).where(Entrega.id == entrega_id).with_for_update()
        )
        if entrega is None:
            raise ReservaEntregaNoValida("La entrega reservada ya no existe.")
        if entrega.cerrada:
            raise EntregaCerradaDuranteEnvio("La entrega ya fue confirmada.")
        if (
            not entrega.procesando
            or entrega.reserva_id != reserva_id
            or entrega.reserva_expira_en is None
            or entrega.reserva_expira_en < hora_entrega
        ):
            raise ReservaEntregaNoValida(
                "La reserva de la entrega no pertenece a esta petición o ha caducado."
            )

        db.execute(
            delete(BorradorRespuesta).where(BorradorRespuesta.entrega_id == entrega_id)
        )
        db.execute(
            delete(RespuestaAlumno).where(RespuestaAlumno.entrega_id == entrega_id)
        )
        db.flush()
        _inyectar(hook_transaccion, PUNTO_DESPUES_ELIMINAR_RESPUESTAS)

        nuevas: list[RespuestaAlumno] = []
        for indice, respuesta in enumerate(respuestas):
            nueva = RespuestaAlumno(
                entrega_id=entrega_id,
                pregunta_id=int(respuesta["pregunta_id"]),
                contenido=str(respuesta["contenido"]),
            )
            db.add(nueva)
            nuevas.append(nueva)
            db.flush()
            if indice == 0:
                _inyectar(hook_transaccion, PUNTO_DESPUES_PRIMERA_RESPUESTA)
        _inyectar(hook_transaccion, PUNTO_DESPUES_TODAS_RESPUESTAS)

        calificacion = db.scalar(
            select(Calificacion).where(Calificacion.entrega_id == entrega_id)
        )
        if calificacion is None:
            calificacion = Calificacion(entrega_id=entrega_id)
            db.add(calificacion)
        calificacion.nota_global = float(resultado["nota_global"])
        calificacion.preguntas_pendientes = int(resultado["preguntas_pendientes"])
        calificacion.desglose_json = json.dumps(
            list(resultado["desglose"]), ensure_ascii=False
        )
        calificacion.calculada_en = hora_entrega
        db.flush()
        _inyectar(hook_transaccion, PUNTO_DESPUES_CALIFICACION)

        _inyectar(hook_transaccion, PUNTO_ANTES_CIERRE)
        entrega.hora_entrega = hora_entrega
        entrega.entregado_automaticamente = entregado_automaticamente
        entrega.cerrada = True
        entrega.hash_envio = hash_envio
        entrega.version_estado += 1
        _inyectar(hook_transaccion, PUNTO_DESPUES_CIERRE)

        entrega.procesando = False
        entrega.procesando_desde = None
        entrega.reserva_id = None
        entrega.reserva_expira_en = None
        _inyectar(hook_transaccion, PUNTO_DURANTE_LIBERACION)
        db.flush()

    db.refresh(calificacion)
    return calificacion
