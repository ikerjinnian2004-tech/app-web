from __future__ import annotations

import json
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_runtime.db")
os.environ.setdefault("SECRET_KEY", "super-clave-de-tests-minimo-32-caracteres")
os.environ.setdefault("IDENTITY_HMAC_KEY", "clave-hmac-de-tests-minimo-32-caracteres")
os.environ.setdefault("EXAM_DURATION_MINUTES", "90")
os.environ.setdefault("SANDBOX_TIMEOUT_SECONDS", "3")
os.environ.setdefault("SANDBOX_MAX_OUTPUT_CHARS", "5000")
os.environ.setdefault("SANDBOX_USE_DOCKER", "false")
os.environ.setdefault("SANDBOX_IMAGE", "python:3.11-slim")
os.environ.setdefault("SANDBOX_MEM_LIMIT_MB", "64")
os.environ.setdefault("SANDBOX_CPU", "0.5")
os.environ.setdefault("SANDBOX_PIDS_LIMIT", "50")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:5500,http://127.0.0.1:5500")
os.environ.setdefault("LOG_LEVEL", "INFO")
os.environ.setdefault("HEALTHCHECK_INTERVAL_SECONDS", "30")

from backend.database import Base, get_db  # noqa: E402
from backend.datos_iniciales import cargar_datos_iniciales  # noqa: E402
from backend.main import app  # noqa: E402
from backend.models import CasoPrueba, Examen, Pregunta, UsuarioPermitido  # noqa: E402


@pytest.fixture(scope="function")
def db_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record) -> None:  # noqa: ANN001, ARG001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    testing_session_local = sessionmaker(
        bind=engine, autocommit=False, autoflush=False, future=True
    )
    Base.metadata.create_all(bind=engine)
    session = testing_session_local()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session: Session) -> TestClient:
    def override_get_db() -> Session:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def examen_activo(db_session: Session) -> Examen:
    datos = cargar_datos_iniciales()
    for rol, usuarios in (
        ("alumno", datos["usuarios"]["alumnos"]),
        ("profesor", datos["usuarios"]["profesores"]),
    ):
        for usuario in usuarios:
            db_session.add(
                UsuarioPermitido(
                    rol=rol,
                    nombre=usuario["nombre"],
                    apellidos=usuario.get("apellidos", ""),
                    correo=usuario["correo"].lower(),
                )
            )
    examen_data = datos["examen"]
    examen = Examen(
        titulo=examen_data["titulo"],
        duracion_segundos=int(examen_data["duracion_minutos"]) * 60,
        activo=True,
    )
    db_session.add(examen)
    db_session.flush()

    for pregunta_data in examen_data["preguntas"]:
        pregunta = Pregunta(
            examen_id=examen.id,
            tipo=pregunta_data["tipo"],
            titulo=pregunta_data["titulo"],
            enunciado=pregunta_data["enunciado"],
            codigo_plantilla=pregunta_data.get("codigo_plantilla"),
            codigo_solucion=pregunta_data.get("codigo_solucion"),
            opciones_json=(
                json.dumps(pregunta_data["opciones"], ensure_ascii=False)
                if "opciones" in pregunta_data
                else None
            ),
            respuesta_correcta=pregunta_data.get("respuesta_correcta"),
            orden=pregunta_data["orden"],
            peso=pregunta_data["peso"],
        )
        db_session.add(pregunta)
        db_session.flush()
        for caso_data in pregunta_data.get("casos_prueba", []):
            db_session.add(
                CasoPrueba(
                    pregunta_id=pregunta.id,
                    descripcion=caso_data["descripcion"],
                    codigo_test=caso_data["codigo_test"],
                    salida_esperada=caso_data.get("salida_esperada", ""),
                    peso=caso_data.get("peso", 1.0),
                )
            )

    db_session.commit()
    db_session.refresh(examen)
    return examen


def acceder_alumno(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/auth/acceder",
        json={"rol": "alumno", "correo_institucional": "ana.garcia@alu.uclm.es"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


def acceder_profesor(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/auth/acceder",
        json={"rol": "profesor", "correo_institucional": "david.munoz@uclm.es"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}
