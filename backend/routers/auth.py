from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.crud import obtener_o_crear_usuario_permitido
from backend.database import get_db
from backend.datos_iniciales import (
    buscar_usuario_en_semilla,
    normalizar_correo,
    validar_dominio_institucional,
)
from backend.errors import forbidden
from backend.schemas import AccesoRequest, AccesoResponse
from backend.security import crear_token_acceso

router = APIRouter()


@router.post("/acceder", response_model=AccesoResponse)
def acceder(request: AccesoRequest, db: Session = Depends(get_db)) -> AccesoResponse:
    correo = normalizar_correo(str(request.correo_institucional))
    if not validar_dominio_institucional(request.rol, correo):
        raise forbidden("El correo no pertenece al dominio institucional esperado.")

    datos_usuario = buscar_usuario_en_semilla(request.rol, correo)
    if datos_usuario is None:
        raise forbidden("El correo no está incluido en la lista inicial autorizada.")

    usuario = obtener_o_crear_usuario_permitido(db, datos_usuario)
    return AccesoResponse(
        token=crear_token_acceso(usuario),
        rol=request.rol,
        nombre=usuario.nombre,
        correo=usuario.correo,
    )
