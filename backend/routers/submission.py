from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.crud import (
    cargar_preguntas_y_casos,
    get_entrega,
)
from backend.database import get_db
from backend.errors import bad_request, conflict, forbidden, not_found, request_timeout
from backend.grader import grade_entrega
from backend.models import UsuarioPermitido
from backend.schemas import SubmissionCreate, SubmissionResponse
from backend.security import exigir_rol
from backend.servicios_entregas import (
    EntregaCerradaDuranteEnvio,
    ReservaEntregaNoValida,
    calcular_hash_envio,
    construir_respuestas_temporales,
    liberar_reserva,
    persistir_envio_atomico,
    reservar_entrega,
)

router = APIRouter()
MARGEN_ENVIO_AUTOMATICO_SEGUNDOS = 10


def utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def response_from_calificacion(entrega_id: int, calificacion) -> SubmissionResponse:
    desglose = json.loads(calificacion.desglose_json)
    for item in desglose:
        item.setdefault("peso", 1.0)
        item.setdefault(
            "contribucion",
            None if item.get("nota") is None else float(item["nota"]),
        )
        item.setdefault("version_pregunta", 1)
    return SubmissionResponse(
        entrega_id=entrega_id,
        nota_global=calificacion.nota_global,
        preguntas_pendientes=calificacion.preguntas_pendientes,
        desglose=desglose,
    )


@router.post("/enviar", response_model=SubmissionResponse)
def enviar_entrega(
    request: SubmissionCreate,
    alumno: UsuarioPermitido = Depends(exigir_rol("alumno")),
    db: Session = Depends(get_db),
) -> SubmissionResponse:
    entrega = get_entrega(db, request.entrega_id)
    if entrega is None:
        raise not_found("La entrega solicitada no existe.")
    if entrega.alumno_id != alumno.id:
        raise forbidden("No puedes enviar la entrega de otro alumno.")
    respuestas = [respuesta.model_dump() for respuesta in request.respuestas]
    hash_envio = calcular_hash_envio(respuestas, request.entregado_automaticamente)
    if entrega.cerrada:
        if entrega.calificacion is not None:
            if entrega.hash_envio is not None and entrega.hash_envio != hash_envio:
                raise conflict(
                    "La entrega ya está cerrada con un contenido de envío distinto."
                )
            return response_from_calificacion(entrega.id, entrega.calificacion)
        raise conflict("La entrega ya está cerrada.")

    duracion = entrega.duracion_examen_segundos or entrega.examen.duracion_segundos
    limite = entrega.hora_inicio + timedelta(seconds=duracion)
    ahora = utc_now_naive()
    if ahora > limite and not (
        request.entregado_automaticamente
        and ahora <= limite + timedelta(seconds=MARGEN_ENVIO_AUTOMATICO_SEGUNDOS)
    ):
        raise request_timeout(
            "El servidor ha marcado esta entrega como fuera de tiempo."
        )

    ids_asignados = {
        asignacion.pregunta_id for asignacion in entrega.preguntas_asignadas
    }
    ids_recibidos = {respuesta["pregunta_id"] for respuesta in respuestas}
    if ids_recibidos != ids_asignados or len(respuestas) != len(ids_recibidos):
        raise bad_request(
            "Debes enviar una única respuesta para cada pregunta asignada."
        )
    entrega_id = entrega.id
    reserva_id = reservar_entrega(db, entrega_id, ahora)
    if reserva_id is None:
        db.expire_all()
        actual = get_entrega(db, entrega_id)
        if actual is not None and actual.cerrada and actual.calificacion is not None:
            if actual.hash_envio is not None and actual.hash_envio != hash_envio:
                raise conflict(
                    "La entrega ya está cerrada con un contenido de envío distinto."
                )
            return response_from_calificacion(actual.id, actual.calificacion)
        raise conflict("La entrega se está procesando en otra petición.")

    try:
        actual = get_entrega(db, entrega_id)
        if actual is None:
            raise ReservaEntregaNoValida("La entrega reservada ya no existe.")
        preguntas, casos_por_pregunta = cargar_preguntas_y_casos(db, entrega_id)
        pesos_por_pregunta = {
            asignacion.pregunta_id: asignacion.peso
            for asignacion in actual.preguntas_asignadas
        }
        resultado = grade_entrega(
            construir_respuestas_temporales(entrega_id, respuestas),
            preguntas,
            casos_por_pregunta,
            pesos_por_pregunta=pesos_por_pregunta,
            modo_calificacion=actual.modo_calificacion,
        )
        calificacion = persistir_envio_atomico(
            db,
            entrega_id=entrega_id,
            reserva_id=reserva_id,
            respuestas=respuestas,
            resultado=resultado,
            hora_entrega=utc_now_naive(),
            entregado_automaticamente=request.entregado_automaticamente,
            hash_envio=hash_envio,
        )
    except EntregaCerradaDuranteEnvio:
        liberar_reserva(db, entrega_id, reserva_id)
        db.expire_all()
        actual = get_entrega(db, entrega_id)
        if (
            actual is not None
            and actual.cerrada
            and actual.calificacion is not None
            and (actual.hash_envio is None or actual.hash_envio == hash_envio)
        ):
            return response_from_calificacion(actual.id, actual.calificacion)
        raise conflict("La entrega ya fue confirmada por otra petición.")
    except ReservaEntregaNoValida as exc:
        liberar_reserva(db, entrega_id, reserva_id)
        raise conflict(str(exc)) from exc
    except Exception:
        liberar_reserva(db, entrega_id, reserva_id)
        raise
    return response_from_calificacion(entrega_id, calificacion)


@router.get("/{entrega_id}/resultado", response_model=SubmissionResponse)
def obtener_resultado(
    entrega_id: int,
    alumno: UsuarioPermitido = Depends(exigir_rol("alumno")),
    db: Session = Depends(get_db),
) -> SubmissionResponse:
    entrega = get_entrega(db, entrega_id)
    if entrega is None:
        raise not_found("La entrega solicitada no existe.")
    if entrega.alumno_id != alumno.id:
        raise forbidden("No puedes consultar la entrega de otro alumno.")
    if entrega.calificacion is None:
        raise not_found("La entrega todavía no tiene calificación calculada.")
    return response_from_calificacion(entrega.id, entrega.calificacion)
