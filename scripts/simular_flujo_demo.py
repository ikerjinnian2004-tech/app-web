from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def bootstrap_python_path() -> None:
    os.chdir(PROJECT_ROOT)
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))


def bootstrap_local_environment() -> None:
    os.environ.setdefault("DATABASE_URL", "sqlite:///./dev.db")
    os.environ.setdefault("SECRET_KEY", "clave-local-demo-1234567890-abcdefghijkl")
    os.environ.setdefault(
        "IDENTITY_HMAC_KEY", "clave-hmac-local-demo-minimo-32-caracteres"
    )
    os.environ.setdefault(
        "ALLOWED_ORIGINS", "http://localhost:5500,http://127.0.0.1:5500"
    )
    os.environ.setdefault("SANDBOX_USE_DOCKER", "false")
    os.environ.setdefault("SANDBOX_TIMEOUT_SECONDS", "2")
    os.environ.setdefault("SANDBOX_MAX_OUTPUT_CHARS", "5000")


def acceder(client, rol: str, correo: str) -> dict[str, str]:
    response = client.post(
        "/auth/acceder",
        json={"rol": rol, "correo_institucional": correo},
    )
    response.raise_for_status()
    return {"Authorization": f"Bearer {response.json()['token']}"}


def iniciar_examen(client, headers: dict[str, str]) -> dict:
    consentimiento = client.get("/consentimiento").json()
    response = client.post(
        "/examen/iniciar",
        headers=headers,
        json={
            "consentimiento_version": consentimiento["version"],
            "acepta_grabacion": True,
        },
    )
    response.raise_for_status()
    return response.json()


def respuesta_correcta(pregunta: dict) -> str:
    respuestas = {
        "suma-basica": "a + b",
        "suma-producto-dos-huecos": json.dumps(["a + b", "a * b"]),
        "maximo-dos-valores": (
            "def maximo(a, b):\n    if a >= b:\n        return a\n    return b"
        ),
        "clasificar-edad": (
            "def clasificar_edad(edad):\n"
            "    if 0 <= edad <= 12:\n"
            "        return 'niñez'\n"
            "    if 12 < edad < 18:\n"
            "        return 'adolescencia'\n"
            "    if edad >= 18:\n"
            "        return 'edad adulta'\n"
            "    raise ValueError('edad no válida')"
        ),
        "estructura-mutable": "list",
        "resultado-range": "[1, 3, 5]",
        "traza-acumulador": "Imprime 6 porque suma los valores 1, 2 y 3.",
        "acceso-diccionario": (
            "Se encadenan las claves del alumno, la asignatura y la nota."
        ),
    }
    return respuestas[pregunta["clave"]]


def main() -> int:
    bootstrap_python_path()
    bootstrap_local_environment()

    from fastapi.testclient import TestClient

    from scripts.reset_db import main as reset_db
    from backend.data.seed_questions import main as seed_data

    reset_db()
    seed_data()

    from backend.main import app

    with TestClient(app) as client:
        headers_alumno = acceder(client, "alumno", "ikerjinnian.blanco@alu.uclm.es")
        examen = iniciar_examen(client, headers_alumno)
        respuestas = [
            {"pregunta_id": pregunta["id"], "contenido": respuesta_correcta(pregunta)}
            for pregunta in examen["preguntas"]
        ]
        entrega = client.post(
            "/entregas/enviar",
            headers=headers_alumno,
            json={"entrega_id": examen["entrega_id"], "respuestas": respuestas},
        )
        entrega.raise_for_status()

        headers_profesor = acceder(client, "profesor", "david.munoz@uclm.es")
        panel = client.get("/profesor/entregas", headers=headers_profesor)
        panel.raise_for_status()

    resultado = entrega.json()
    print(f"nota_global={resultado['nota_global']}")
    print(f"preguntas_pendientes={resultado['preguntas_pendientes']}")
    print(f"entregas_panel_docente={len(panel.json())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
