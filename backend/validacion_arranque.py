from __future__ import annotations

from collections.abc import Callable

from backend.config import Settings
from backend.sandbox.runner_docker import comprobar_disponibilidad_docker


ComprobadorDocker = Callable[[], tuple[bool, str]]


def validar_arranque(
    settings: Settings,
    comprobar_docker: ComprobadorDocker = comprobar_disponibilidad_docker,
) -> None:
    """Impide que producción degrade silenciosamente al runner local."""
    if settings.app_environment != "production":
        return
    disponible, detalle = comprobar_docker()
    if not disponible:
        raise RuntimeError(
            "El entorno de producción requiere un sandbox Docker operativo. " + detalle
        )
