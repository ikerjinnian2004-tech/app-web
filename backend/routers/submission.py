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
from backend.errors import bad_request, conflict, forbidden, not_found, request_timeout
from backend.grader import grade_entrega
from backend.models import UsuarioPermitido
from backend.schemas import SubmissionCreate, SubmissionResponse
from backend.security import exigir_rol

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
    if entrega.cerrada:
        if entrega.calificacion is not None:
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

    respuestas = [respuesta.model_dump() for respuesta in request.respuestas]
    ids_asignados = {
        asignacion.pregunta_id for asignacion in entrega.preguntas_asignadas
    }
    ids_recibidos = {respuesta["pregunta_id"] for respuesta in respuestas}
    if ids_recibidos != ids_asignados or len(respuestas) != len(ids_recibidos):
        raise bad_request(
            "Debes enviar una única respuesta para cada pregunta asignada."
        )
    respuestas_guardadas = guardar_respuestas(db, entrega, respuestas)
    preguntas, casos_por_pregunta = cargar_preguntas_y_casos(db, entrega.id)
    pesos_por_pregunta = {
        asignacion.pregunta_id: asignacion.peso
        for asignacion in entrega.preguntas_asignadas
    }
    resultado = grade_entrega(
        respuestas_guardadas,
        preguntas,
        casos_por_pregunta,
        pesos_por_pregunta=pesos_por_pregunta,
        modo_calificacion=entrega.modo_calificacion,
    )
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
