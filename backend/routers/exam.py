from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.crud import (
    crear_entrega,
    get_examen_activo,
    get_ultima_entrega,
    seleccionar_preguntas,
)
from backend.database import get_db
from backend.datos_iniciales import obtener_version_consentimiento
from backend.errors import bad_request, conflict, not_found
from backend.models import Entrega, Pregunta, UsuarioPermitido
from backend.schemas import ExamenResponse, IniciarExamenRequest, PreguntaExamen
from backend.security import exigir_rol
from backend.template_engine import contar_huecos

router = APIRouter()


def utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def to_public_utc(value: datetime) -> str:
    return value.replace(tzinfo=UTC).isoformat().replace("+00:00", "Z")


def pregunta_publica(
    pregunta: Pregunta, orden: int | None = None, peso: float | None = None
) -> PreguntaExamen:
    opciones = json.loads(pregunta.opciones_json) if pregunta.opciones_json else None
    limites = (
        json.loads(pregunta.limites_caracteres_json)
        if pregunta.limites_caracteres_json
        else None
    )
    return PreguntaExamen(
        id=pregunta.id,
        clave=pregunta.clave,
        version=pregunta.version,
        tipo=pregunta.tipo,
        titulo=pregunta.titulo,
        enunciado=pregunta.enunciado,
        codigo_plantilla=pregunta.codigo_plantilla,
        opciones=opciones,
        numero_huecos=(
            contar_huecos(pregunta.codigo_plantilla or "")
            if pregunta.tipo == "rellenar_huecos"
            else 0
        ),
        limites_caracteres=limites,
        peso=pregunta.peso if peso is None else peso,
        orden=pregunta.orden if orden is None else orden,
    )


def response_from_entrega(entrega: Entrega) -> ExamenResponse:
    if entrega.preguntas_asignadas:
        preguntas = [
            pregunta_publica(
                asignacion.pregunta,
                orden=asignacion.orden,
                peso=asignacion.peso,
            )
            for asignacion in entrega.preguntas_asignadas
        ]
    else:
        preguntas = [
            pregunta_publica(pregunta)
            for pregunta in sorted(
                entrega.examen.preguntas, key=lambda item: item.orden
            )
        ]
    return ExamenResponse(
        examen_id=entrega.examen.id,
        entrega_id=entrega.id,
        titulo=entrega.titulo_examen or entrega.examen.titulo,
        duracion_segundos=(
            entrega.duracion_examen_segundos or entrega.examen.duracion_segundos
        ),
        hora_inicio_servidor=to_public_utc(entrega.hora_inicio),
        hora_actual_servidor=to_public_utc(utc_now_naive()),
        hora_limite_servidor=to_public_utc(
            entrega.hora_inicio
            + timedelta(
                seconds=entrega.duracion_examen_segundos
                or entrega.examen.duracion_segundos
            )
        ),
        preguntas=preguntas,
    )


@router.post("/iniciar", response_model=ExamenResponse)
def iniciar_examen(
    request: IniciarExamenRequest,
    alumno: UsuarioPermitido = Depends(exigir_rol("alumno")),
    db: Session = Depends(get_db),
) -> ExamenResponse:
    if not request.acepta_grabacion:
        raise bad_request("Debes aceptar el consentimiento para iniciar la prueba.")
    if not request.permisos_evidencia_verificados:
        raise bad_request(
            "Debes conceder los permisos de pantalla, cámara y micrófono."
        )

    version_actual = obtener_version_consentimiento()
    if request.consentimiento_version != version_actual:
        raise bad_request(
            "El texto de consentimiento no coincide con la versión actual."
        )

    examen = get_examen_activo(db)
    if examen is None:
        raise not_found("No hay ningún examen activo.")

    entrega = get_ultima_entrega(db, alumno.id, examen.id)
    if entrega is not None and entrega.cerrada:
        raise conflict("La entrega ya está cerrada.")
    if entrega is None:
        try:
            preguntas = seleccionar_preguntas(examen)
        except ValueError as exc:
            raise conflict(str(exc)) from exc
        if not preguntas:
            raise conflict("El examen no tiene preguntas publicadas.")
        entrega = crear_entrega(
            db,
            alumno_id=alumno.id,
            examen=examen,
            hora_inicio=utc_now_naive(),
            consentimiento_version=version_actual,
            acepta_grabacion=request.acepta_grabacion,
            permisos_evidencia_verificados=(request.permisos_evidencia_verificados),
            preguntas=preguntas,
        )
        entrega.examen = examen

    return response_from_entrega(entrega)
