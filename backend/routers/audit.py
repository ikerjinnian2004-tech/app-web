from __future__ import annotations

from uuid import uuid4

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
from backend.errors import bad_request, forbidden, not_found, payload_too_large
from backend.models import UsuarioPermitido
from backend.schemas import AuditEventCreate, AuditEventResponse, EvidenciaResponse
from backend.security import exigir_rol

router = APIRouter()
settings = get_settings()
EVENTOS_CON_EVIDENCIA = {"CAMBIO_PESTANA", "PERDIDA_FOCO"}
TIPOS_EVIDENCIA = {"pantalla_camara_audio", "pantalla", "camara", "audio"}
MIME_EVIDENCIA = {"video/webm", "video/mp4", "audio/webm"}
TAMANO_BLOQUE = 1_048_576


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
        and entrega.permisos_evidencia_verificados
        and request.tipo in EVENTOS_CON_EVIDENCIA
    )
    return AuditEventResponse(ok=True, evento_id=evento.id, grabar_evidencia=grabar)


@router.post("/evidencias", response_model=EvidenciaResponse)
async def subir_evidencia(
    evento_id: int = Form(...),
    tipo: str = Form(...),
    mime_type: str = Form(...),
    duracion_ms: int = Form(..., ge=1),
    archivo: UploadFile = File(...),
    alumno: UsuarioPermitido = Depends(exigir_rol("alumno")),
    db: Session = Depends(get_db),
) -> EvidenciaResponse:
    evento = obtener_evento(db, evento_id)
    if evento is None:
        raise not_found("El evento de auditoría no existe.")
    if evento.usuario_id != alumno.id:
        raise forbidden("No puedes adjuntar evidencia a un evento ajeno.")
    if (
        evento.entrega is None
        or not evento.entrega.acepta_grabacion
        or not evento.entrega.permisos_evidencia_verificados
    ):
        raise forbidden("La entrega no tiene consentimiento de grabación asociado.")
    if evento.entrega.cerrada:
        raise forbidden("No se admiten evidencias para una entrega cerrada.")
    if evento.tipo not in EVENTOS_CON_EVIDENCIA:
        raise bad_request("El tipo de evento no requiere evidencia.")
    if tipo not in TIPOS_EVIDENCIA:
        raise bad_request("El tipo de evidencia no está permitido.")
    mime_declarado = mime_type or archivo.content_type or ""
    if mime_declarado not in MIME_EVIDENCIA:
        raise bad_request("El formato de evidencia no está permitido.")
    if duracion_ms > settings.evidencia_duracion_segundos * 1000:
        raise bad_request("La evidencia supera la duración máxima permitida.")

    bloques: list[bytes] = []
    tamano = 0
    while bloque := await archivo.read(TAMANO_BLOQUE):
        tamano += len(bloque)
        if tamano > settings.evidencia_max_bytes:
            raise payload_too_large("La evidencia supera el tamaño máximo permitido.")
        bloques.append(bloque)
    if tamano == 0:
        raise bad_request("La evidencia está vacía.")
    contenido = b"".join(bloques)
    es_webm = contenido.startswith(b"\x1aE\xdf\xa3")
    es_mp4 = len(contenido) >= 12 and contenido[4:8] == b"ftyp"
    if (mime_declarado in {"video/webm", "audio/webm"} and not es_webm) or (
        mime_declarado == "video/mp4" and not es_mp4
    ):
        raise bad_request("El contenido no coincide con el formato declarado.")
    extension = ".mp4" if mime_declarado == "video/mp4" else ".webm"
    nombre_seguro = f"evidencia-{uuid4().hex}{extension}"

    evidencia = guardar_evidencia(
        db,
        evento_id=evento.id,
        tipo=tipo,
        mime_type=mime_declarado,
        nombre_archivo=nombre_seguro,
        duracion_ms=duracion_ms,
        contenido=contenido,
    )
    return EvidenciaResponse(ok=True, evidencia_id=evidencia.id)
