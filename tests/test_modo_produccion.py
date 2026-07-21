from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.config import Settings, get_settings
from backend.main import app
from backend.validacion_arranque import validar_arranque


def datos_configuracion(**cambios: object) -> dict[str, object]:
    datos: dict[str, object] = {
        "DATABASE_URL": "postgresql+psycopg2://user:pass@db:5432/app",
        "SECRET_KEY": "clave-produccion-segura-1234567890-abcdefghijkl",
        "IDENTITY_HMAC_KEY": "hmac-produccion-seguro-1234567890-abcdefghijkl",
        "ALLOWED_ORIGINS": "https://evaluador.example.edu",
    }
    datos.update(cambios)
    return datos


def test_produccion_rechaza_autenticacion_de_demostracion() -> None:
    with pytest.raises(ValidationError, match="DEMO_AUTH_ENABLED"):
        Settings.model_validate(
            datos_configuracion(
                APP_ENVIRONMENT="production",
                DEMO_AUTH_ENABLED=True,
                SANDBOX_USE_DOCKER=True,
            )
        )


def test_produccion_rechaza_runner_local() -> None:
    with pytest.raises(ValidationError, match="SANDBOX_USE_DOCKER"):
        Settings.model_validate(
            datos_configuracion(
                APP_ENVIRONMENT="production",
                DEMO_AUTH_ENABLED=False,
                SANDBOX_USE_DOCKER=False,
            )
        )


def test_produccion_falla_si_daemon_o_imagen_no_estan_disponibles() -> None:
    settings = Settings.model_validate(
        datos_configuracion(
            APP_ENVIRONMENT="production",
            DEMO_AUTH_ENABLED=False,
            SANDBOX_USE_DOCKER=True,
        )
    )

    with pytest.raises(RuntimeError, match="sandbox Docker operativo"):
        validar_arranque(settings, lambda: (False, "daemon ausente"))


def test_produccion_arranca_si_el_sandbox_requerido_responde() -> None:
    settings = Settings.model_validate(
        datos_configuracion(
            APP_ENVIRONMENT="production",
            DEMO_AUTH_ENABLED=False,
            SANDBOX_USE_DOCKER=True,
        )
    )

    validar_arranque(settings, lambda: (True, "imagen disponible"))


def test_ruta_demo_rechaza_acceso_cuando_esta_deshabilitada(
    client, examen_activo
) -> None:
    settings = Settings.model_validate(
        datos_configuracion(
            APP_ENVIRONMENT="production",
            DEMO_AUTH_ENABLED=False,
            SANDBOX_USE_DOCKER=True,
        )
    )
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        respuesta = client.post(
            "/auth/acceder",
            json={
                "rol": "alumno",
                "correo_institucional": "alumna.demo@alu.uclm.es",
            },
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert respuesta.status_code == 403
    assert "demostración" in respuesta.json()["detail"]
