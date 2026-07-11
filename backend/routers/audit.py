from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.crud import (
    get_examen_activo,
    get_ultima_entrega,
    guardar_evidencia,
    obtener_evento,
    registrar_evento_auditoria,
)
from backend.database import get_db
from backend.errors import forbidden, not_found, payload_too_large
from backend.models import UsuarioPermitido
from backend.schemas import AuditEventCreate, AuditEventResponse, EvidenciaResponse
from backend.security import exigir_rol

router = APIRouter()
settings = get_settings()
EVENTOS_CON_EVIDENCIA = {"CAMBIO_PESTANA", "PERDIDA_FOCO"}


@router.post("/eventos", response_model=AuditEventResponse)
def registrar_evento(
    request: AuditEventCreate,
    alumno: UsuarioPermitido = Depends(exigir_rol("alumno")),
    db: Session = Depends(get_db),
) -> AuditEventResponse:
    examen = get_examen_activo(db)
    entrega = (
        get_ultima_entrega(db, alumno.id, examen.id) if examen is not None else None
    )
    evento = registrar_evento_auditoria(
        db,
        usuario_id=alumno.id,
        entrega_id=entrega.id if entrega is not None else None,
        tipo=request.tipo,
        timestamp_cliente=request.timestamp_cliente,
        metadata=request.metadata,
    )
    grabar = (
        entrega is not None
        and not entrega.cerrada
        and entrega.acepta_grabacion
        and request.tipo in EVENTOS_CON_EVIDENCIA
    )
    return AuditEventResponse(ok=True, evento_id=evento.id, grabar_evidencia=grabar)


@router.post("/evidencias", response_model=EvidenciaResponse)
async def subir_evidencia(
    evento_id: int = Form(...),
    tipo: str = Form(...),
    mime_type: str = Form(...),
    archivo: UploadFile = File(...),
    alumno: UsuarioPermitido = Depends(exigir_rol("alumno")),
    db: Session = Depends(get_db),
) -> EvidenciaResponse:
    evento = obtener_evento(db, evento_id)
    if evento is None:
        raise not_found("El evento de auditoría no existe.")
    if evento.usuario_id != alumno.id:
        raise forbidden("No puedes adjuntar evidencia a un evento ajeno.")
    if evento.entrega is None or not evento.entrega.acepta_grabacion:
        raise forbidden("La entrega no tiene consentimiento de grabación asociado.")

    contenido = await archivo.read()
    if len(contenido) > settings.evidencia_max_bytes:
        raise payload_too_large("La evidencia supera el tamaño máximo permitido.")

    evidencia = guardar_evidencia(
        db,
        evento_id=evento.id,
        tipo=tipo,
        mime_type=mime_type or archivo.content_type or "application/octet-stream",
        nombre_archivo=archivo.filename or "evidencia.webm",
        contenido=contenido,
    )
    return EvidenciaResponse(ok=True, evidencia_id=evidencia.id)
