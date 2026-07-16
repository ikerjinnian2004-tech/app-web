from __future__ import annotations

import hmac
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.database import get_db
from backend.models import UsuarioPermitido

settings = get_settings()
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 8
TOKEN_ISSUER = "evaluador-python-tfg"
TOKEN_AUDIENCE = "evaluador-web"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/acceder")


def hash_identificador(tipo: str, valor: str) -> str:
    """Genera un HMAC estable para valores que no deban guardarse en claro."""
    normalizado = valor.strip().lower() if tipo == "correo" else valor.strip().upper()
    message = f"{tipo}:{normalizado}".encode("utf-8")
    return hmac.new(
        settings.identity_hmac_key.encode("utf-8"), message, "sha256"
    ).hexdigest()


def crear_token_acceso(usuario: UsuarioPermitido) -> str:
    expires_at = datetime.now(UTC) + timedelta(hours=TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": str(usuario.id),
        "rol": usuario.rol,
        "nombre": usuario.nombre,
        "correo": usuario.correo,
        "iss": TOKEN_ISSUER,
        "aud": TOKEN_AUDIENCE,
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def verificar_token(token: str) -> dict | None:
    try:
        return jwt.decode(
            token,
            settings.secret_key,
            algorithms=[ALGORITHM],
            audience=TOKEN_AUDIENCE,
            issuer=TOKEN_ISSUER,
        )
    except JWTError:
        return None


def obtener_usuario_actual(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> UsuarioPermitido:
    claims = verificar_token(token)
    if claims is None or "sub" not in claims:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado.",
        )

    try:
        usuario_id = int(claims["sub"])
    except (TypeError, ValueError):
        usuario_id = -1
    usuario = db.get(UsuarioPermitido, usuario_id)
    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El usuario de la sesión ya no existe.",
        )
    return usuario


def exigir_rol(rol: Literal["alumno", "profesor"]):
    def dependencia(usuario: UsuarioPermitido = Depends(obtener_usuario_actual)):
        if usuario.rol != rol:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para esta operación.",
            )
        return usuario

    return dependencia
