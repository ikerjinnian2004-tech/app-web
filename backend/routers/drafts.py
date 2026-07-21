from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.errors import conflict, forbidden, not_found, request_timeout
from backend.models import UsuarioPermitido
from backend.schemas import BorradorGuardarRequest, BorradorResponse
from backend.security import exigir_rol
from backend.servicios_borradores import (
    BorradorNoAutorizado,
    BorradorNoDisponible,
    BorradorNoEncontrado,
    ConflictoVersionBorrador,
    guardar_borrador,
    listar_borradores,
)


router = APIRouter()


def utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _mapear_error(exc: RuntimeError):
    if isinstance(exc, BorradorNoEncontrado):
        return not_found(str(exc))
    if isinstance(exc, BorradorNoAutorizado):
        return forbidden(str(exc))
    if isinstance(exc, ConflictoVersionBorrador):
        return conflict(str(exc))
    if "tiempo" in str(exc).lower():
        return request_timeout(str(exc))
    return conflict(str(exc))


@router.get("/{entrega_id}", response_model=list[BorradorResponse])
def obtener_borradores(
    entrega_id: int,
    alumno: UsuarioPermitido = Depends(exigir_rol("alumno")),
    db: Session = Depends(get_db),
) -> list[BorradorResponse]:
    try:
        borradores = listar_borradores(db, entrega_id, alumno.id, utc_now_naive())
    except (BorradorNoEncontrado, BorradorNoAutorizado, BorradorNoDisponible) as exc:
        raise _mapear_error(exc) from exc
    return [BorradorResponse.model_validate(borrador) for borrador in borradores]


@router.post("/{entrega_id}", response_model=BorradorResponse)
def actualizar_borrador(
    entrega_id: int,
    request: BorradorGuardarRequest,
    alumno: UsuarioPermitido = Depends(exigir_rol("alumno")),
    db: Session = Depends(get_db),
) -> BorradorResponse:
    try:
        borrador = guardar_borrador(
            db,
            entrega_id=entrega_id,
            alumno_id=alumno.id,
            pregunta_id=request.pregunta_id,
            contenido=request.contenido,
            version_esperada=request.version_esperada,
            ahora=utc_now_naive(),
        )
    except (
        BorradorNoEncontrado,
        BorradorNoAutorizado,
        BorradorNoDisponible,
        ConflictoVersionBorrador,
    ) as exc:
        raise _mapear_error(exc) from exc
    return BorradorResponse.model_validate(borrador)
