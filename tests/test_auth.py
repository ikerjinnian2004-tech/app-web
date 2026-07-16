from datetime import UTC, datetime, timedelta

from jose import jwt

from backend.security import (
    ALGORITHM,
    TOKEN_AUDIENCE,
    TOKEN_ISSUER,
    settings,
)


def test_acceso_alumno_y_profesor(client, examen_activo) -> None:
    alumno = client.post(
        "/auth/acceder",
        json={
            "rol": "alumno",
            "correo_institucional": "IKERJINNIAN.BLANCO@ALU.UCLM.ES",
        },
    )
    profesor = client.post(
        "/auth/acceder",
        json={"rol": "profesor", "correo_institucional": "david.munoz@uclm.es"},
    )

    assert alumno.status_code == 200
    assert alumno.json()["rol"] == "alumno"
    assert profesor.status_code == 200
    assert profesor.json()["rol"] == "profesor"


def test_rechaza_correo_fuera_de_semilla(client, examen_activo) -> None:
    response = client.post(
        "/auth/acceder",
        json={"rol": "alumno", "correo_institucional": "nadie@alu.uclm.es"},
    )
    assert response.status_code == 403


def test_rechaza_dominio_incorrecto(client, examen_activo) -> None:
    response = client.post(
        "/auth/acceder",
        json={"rol": "alumno", "correo_institucional": "iker.blanco@uclm.es"},
    )
    assert response.status_code == 403


def test_rechaza_token_firmado_con_identificador_malformado(
    client, examen_activo
) -> None:
    token = jwt.encode(
        {
            "sub": "no-es-entero",
            "iss": TOKEN_ISSUER,
            "aud": TOKEN_AUDIENCE,
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        settings.secret_key,
        algorithm=ALGORITHM,
    )
    response = client.get(
        "/profesor/entregas", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401


def test_rechaza_token_destinado_a_otra_aplicacion(client, examen_activo) -> None:
    token = jwt.encode(
        {
            "sub": "1",
            "iss": TOKEN_ISSUER,
            "aud": "otra-aplicacion",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        settings.secret_key,
        algorithm=ALGORITHM,
    )
    response = client.get(
        "/profesor/entregas", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401
