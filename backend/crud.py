from __future__ import annotations

import json
import random
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from backend.models import (
    Calificacion,
    CasoPrueba,
    Entrega,
    EventoAuditoria,
    EvidenciaAuditoria,
    Examen,
    Pregunta,
    PreguntaAsignada,
    RespuestaAlumno,
    UsuarioPermitido,
)


def obtener_o_crear_usuario_permitido(
    db: Session, datos_usuario: dict[str, str]
) -> UsuarioPermitido:
    correo = datos_usuario["correo"].strip().lower()
    usuario = db.scalar(
        select(UsuarioPermitido).where(UsuarioPermitido.correo == correo)
    )
    if usuario is not None:
        return usuario

    usuario = UsuarioPermitido(
        rol=datos_usuario["rol"],
        nombre=datos_usuario["nombre"],
        apellidos=datos_usuario.get("apellidos", ""),
        correo=correo,
    )
    db.add(usuario)
    try:
        db.commit()
        db.refresh(usuario)
        return usuario
    except IntegrityError:
        db.rollback()
        existente = db.scalar(
            select(UsuarioPermitido).where(UsuarioPermitido.correo == correo)
        )
        if existente is None:
            raise
        return existente


def get_examen_activo(db: Session) -> Examen | None:
    ahora = datetime.now(UTC).replace(tzinfo=None)
    resultado = db.execute(
        select(Examen)
        .where(
            Examen.activo.is_(True),
            Examen.estado == "publicado",
            or_(Examen.apertura_en.is_(None), Examen.apertura_en <= ahora),
            or_(Examen.cierre_en.is_(None), Examen.cierre_en >= ahora),
        )
        .options(joinedload(Examen.preguntas).joinedload(Pregunta.casos_prueba))
        .order_by(Examen.id.desc())
    )
    return resultado.unique().scalars().first()


def seleccionar_preguntas(
    examen: Examen, randomizador: random.Random | random.SystemRandom | None = None
) -> list[Pregunta]:
    publicadas = [
        pregunta for pregunta in examen.preguntas if pregunta.estado == "publicada"
    ]
    seleccion = json.loads(examen.seleccion_json or "{}")
    if not seleccion:
        return sorted(publicadas, key=lambda pregunta: pregunta.orden)

    generador = randomizador or random.SystemRandom()
    elegidas: list[Pregunta] = []
    for tipo, cantidad in seleccion.items():
        candidatas = [pregunta for pregunta in publicadas if pregunta.tipo == tipo]
        if not isinstance(cantidad, int) or cantidad < 0:
            raise ValueError(f"Cantidad no válida para el tipo {tipo}.")
        if len(candidatas) < cantidad:
            raise ValueError(
                f"No hay suficientes preguntas publicadas del tipo {tipo}."
            )
        elegidas.extend(generador.sample(candidatas, cantidad))
    return elegidas


def get_entrega(db: Session, entrega_id: int) -> Entrega | None:
    resultado = db.execute(
        select(Entrega)
        .where(Entrega.id == entrega_id)
        .options(
            joinedload(Entrega.examen),
            joinedload(Entrega.preguntas_asignadas)
            .joinedload(PreguntaAsignada.pregunta)
            .joinedload(Pregunta.casos_prueba),
            joinedload(Entrega.respuestas_alumno),
            joinedload(Entrega.calificacion),
            joinedload(Entrega.alumno),
        )
    )
    return resultado.unique().scalars().first()


def get_ultima_entrega(db: Session, alumno_id: int, examen_id: int) -> Entrega | None:
    return db.scalar(
        select(Entrega)
        .where(Entrega.alumno_id == alumno_id, Entrega.examen_id == examen_id)
        .order_by(Entrega.id.desc())
    )


def crear_entrega(
    db: Session,
    alumno_id: int,
    examen: Examen,
    hora_inicio: datetime,
    consentimiento_version: str,
    acepta_grabacion: bool,
    preguntas: list[Pregunta],
) -> Entrega:
    entrega = Entrega(
        alumno_id=alumno_id,
        examen_id=examen.id,
        version_examen=examen.version,
        titulo_examen=examen.titulo,
        duracion_examen_segundos=examen.duracion_segundos,
        modo_calificacion=examen.modo_calificacion,
        hora_inicio=hora_inicio,
        consentimiento_version=consentimiento_version,
        acepta_grabacion=acepta_grabacion,
    )
    db.add(entrega)
    db.flush()
    for orden, pregunta in enumerate(preguntas, start=1):
        entrega.preguntas_asignadas.append(
            PreguntaAsignada(
                pregunta_id=pregunta.id,
                orden=orden,
                peso=pregunta.peso,
                version_pregunta=pregunta.version,
            )
        )
    db.commit()
    db.refresh(entrega)
    return entrega


def guardar_respuestas(
    db: Session, entrega: Entrega, respuestas: list[dict[str, Any]]
) -> list[RespuestaAlumno]:
    for respuesta in list(entrega.respuestas_alumno):
        db.delete(respuesta)
    db.flush()

    nuevas: list[RespuestaAlumno] = []
    for respuesta in respuestas:
        nueva = RespuestaAlumno(
            entrega_id=entrega.id,
            pregunta_id=respuesta["pregunta_id"],
            contenido=respuesta["contenido"],
        )
        db.add(nueva)
        nuevas.append(nueva)

    db.commit()
    for respuesta in nuevas:
        db.refresh(respuesta)
    return nuevas


def reclamar_entrega(
    db: Session,
    entrega_id: int,
    ahora: datetime,
    caducidad_segundos: int = 120,
) -> bool:
    """Reserva una entrega con un UPDATE atómico y recupera reservas caducadas."""
    reserva_caducada = ahora - timedelta(seconds=caducidad_segundos)
    resultado = db.execute(
        update(Entrega)
        .where(
            Entrega.id == entrega_id,
            Entrega.cerrada.is_(False),
            or_(
                Entrega.procesando.is_(False),
                Entrega.procesando_desde.is_(None),
                Entrega.procesando_desde < reserva_caducada,
            ),
        )
        .values(procesando=True, procesando_desde=ahora)
    )
    db.commit()
    return resultado.rowcount == 1


def liberar_entrega(db: Session, entrega_id: int) -> None:
    db.execute(
        update(Entrega)
        .where(Entrega.id == entrega_id, Entrega.cerrada.is_(False))
        .values(procesando=False, procesando_desde=None)
    )
    db.commit()


def cargar_preguntas_y_casos(
    db: Session, entrega_id: int
) -> tuple[list[Pregunta], dict[int, list[CasoPrueba]]]:
    asignaciones = list(
        db.scalars(
            select(PreguntaAsignada)
            .where(PreguntaAsignada.entrega_id == entrega_id)
            .options(
                joinedload(PreguntaAsignada.pregunta).joinedload(Pregunta.casos_prueba)
            )
            .order_by(PreguntaAsignada.orden.asc())
        )
        .unique()
        .all()
    )
    preguntas = [asignacion.pregunta for asignacion in asignaciones]
    return preguntas, {
        pregunta.id: list(pregunta.casos_prueba) for pregunta in preguntas
    }


def guardar_calificacion(
    db: Session,
    entrega_id: int,
    nota_global: float,
    preguntas_pendientes: int,
    desglose: list[dict[str, Any]],
) -> Calificacion:
    calificacion = db.scalar(
        select(Calificacion).where(Calificacion.entrega_id == entrega_id)
    )
    if calificacion is None:
        calificacion = Calificacion(entrega_id=entrega_id)
        db.add(calificacion)

    calificacion.nota_global = nota_global
    calificacion.preguntas_pendientes = preguntas_pendientes
    calificacion.desglose_json = json.dumps(desglose, ensure_ascii=False)
    db.commit()
    db.refresh(calificacion)
    return calificacion


def cerrar_entrega(
    db: Session,
    entrega: Entrega,
    hora_entrega: datetime,
    entregado_automaticamente: bool,
) -> Entrega:
    entrega.hora_entrega = hora_entrega
    entrega.entregado_automaticamente = entregado_automaticamente
    entrega.cerrada = True
    entrega.procesando = False
    entrega.procesando_desde = None
    db.commit()
    db.refresh(entrega)
    return entrega


def registrar_evento_auditoria(
    db: Session,
    usuario_id: int,
    entrega_id: int | None,
    tipo: str,
    timestamp_cliente: str,
    metadata: dict[str, Any],
) -> EventoAuditoria:
    evento = EventoAuditoria(
        usuario_id=usuario_id,
        entrega_id=entrega_id,
        tipo=tipo,
        timestamp_cliente=timestamp_cliente,
        metadata_json=json.dumps(metadata, ensure_ascii=False),
    )
    db.add(evento)
    db.commit()
    db.refresh(evento)
    return evento


def obtener_evento(db: Session, evento_id: int) -> EventoAuditoria | None:
    resultado = db.execute(
        select(EventoAuditoria)
        .where(EventoAuditoria.id == evento_id)
        .options(
            joinedload(EventoAuditoria.entrega), joinedload(EventoAuditoria.usuario)
        )
    )
    return resultado.unique().scalars().first()


def guardar_evidencia(
    db: Session,
    evento_id: int,
    tipo: str,
    mime_type: str,
    nombre_archivo: str,
    contenido: bytes,
) -> EvidenciaAuditoria:
    evidencia = EvidenciaAuditoria(
        evento_id=evento_id,
        tipo=tipo,
        mime_type=mime_type,
        nombre_archivo=nombre_archivo,
        tamano_bytes=len(contenido),
        contenido=contenido,
    )
    db.add(evidencia)
    db.commit()
    db.refresh(evidencia)
    return evidencia


def obtener_evidencia(db: Session, evidencia_id: int) -> EvidenciaAuditoria | None:
    return db.get(EvidenciaAuditoria, evidencia_id)


def listar_entregas_para_profesor(db: Session) -> list[Entrega]:
    resultado = db.execute(
        select(Entrega)
        .options(
            joinedload(Entrega.alumno),
            joinedload(Entrega.examen),
            joinedload(Entrega.calificacion),
            joinedload(Entrega.eventos).joinedload(EventoAuditoria.evidencias),
        )
        .order_by(Entrega.hora_inicio.desc())
    )
    return list(resultado.unique().scalars().all())


def contar_eventos_por_entrega(db: Session, entrega_id: int) -> int:
    return int(
        db.scalar(
            select(func.count(EventoAuditoria.id)).where(
                EventoAuditoria.entrega_id == entrega_id
            )
        )
        or 0
    )
