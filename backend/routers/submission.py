from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.crud import (
    cargar_preguntas_y_casos,
    cerrar_entrega,
    get_entrega,
    guardar_calificacion,
    guardar_respuestas,
)
from backend.database import get_db
from backend.errors import conflict, forbidden, not_found, request_timeout
from backend.grader import grade_entrega
from backend.models import UsuarioPermitido
from backend.schemas import SubmissionCreate, SubmissionResponse
from backend.security import exigir_rol

router = APIRouter()


def utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def response_from_calificacion(entrega_id: int, calificacion) -> SubmissionResponse:
    return SubmissionResponse(
        entrega_id=entrega_id,
        nota_global=calificacion.nota_global,
        preguntas_pendientes=calificacion.preguntas_pendientes,
        desglose=json.loads(calificacion.desglose_json),
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
    if entrega.cerrada:
        raise conflict("La entrega ya está cerrada.")

    limite = entrega.hora_inicio + timedelta(seconds=entrega.examen.duracion_segundos)
    if utc_now_naive() > limite:
        raise request_timeout(
            "El servidor ha marcado esta entrega como fuera de tiempo."
        )

    respuestas = [respuesta.model_dump() for respuesta in request.respuestas]
    respuestas_guardadas = guardar_respuestas(db, entrega, respuestas)
    preguntas, casos_por_pregunta = cargar_preguntas_y_casos(db, entrega.examen_id)
    resultado = grade_entrega(respuestas_guardadas, preguntas, casos_por_pregunta)
    calificacion = guardar_calificacion(
        db,
        entrega_id=entrega.id,
        nota_global=float(resultado["nota_global"]),
        preguntas_pendientes=int(resultado["preguntas_pendientes"]),
        desglose=list(resultado["desglose"]),
    )
    cerrar_entrega(
        db,
        entrega,
        hora_entrega=utc_now_naive(),
        entregado_automaticamente=request.entregado_automaticamente,
    )
    return response_from_calificacion(entrega.id, calificacion)


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
