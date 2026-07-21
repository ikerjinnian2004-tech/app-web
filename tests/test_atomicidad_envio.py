from __future__ import annotations

import multiprocessing
import os
from collections.abc import Generator
from datetime import timedelta

import pytest
from starlette.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from backend.database import Base, get_db
from backend.main import app
from backend.models import (
    Calificacion,
    Entrega,
    Examen,
    Pregunta,
    PreguntaAsignada,
    RespuestaAlumno,
    UsuarioPermitido,
    utc_now,
)
from backend.routers import submission as submission_router
from backend.security import crear_token_acceso
from backend.servicios_entregas import (
    PUNTO_DESPUES_CIERRE,
    PUNTOS_FALLO_ENVIO,
    liberar_reserva,
    persistir_envio_atomico,
    reservar_entrega,
)


def preparar_entrega(sesiones: sessionmaker[Session]) -> tuple[int, str]:
    with sesiones.begin() as db:
        alumno = UsuarioPermitido(
            rol="alumno",
            nombre="Alumna",
            apellidos="Atomicidad",
            correo="atomicidad@alu.uclm.es",
        )
        examen = Examen(
            titulo="Atomicidad",
            duracion_segundos=3600,
            activo=True,
            estado="publicado",
            seleccion_json="{}",
        )
        db.add_all([alumno, examen])
        db.flush()
        pregunta = Pregunta(
            examen_id=examen.id,
            clave="atomicidad-tipo-test",
            version=1,
            estado="publicada",
            tipo="tipo_test",
            titulo="Pregunta de atomicidad",
            enunciado="Selecciona A.",
            opciones_json='["A", "B"]',
            respuesta_correcta="A",
            orden=1,
            peso=1.0,
        )
        db.add(pregunta)
        db.flush()
        entrega = Entrega(
            alumno_id=alumno.id,
            examen_id=examen.id,
            version_examen=1,
            titulo_examen=examen.titulo,
            duracion_examen_segundos=3600,
            modo_calificacion="parcial_por_tests",
            hora_inicio=utc_now(),
            consentimiento_version="a" * 64,
            acepta_grabacion=True,
            permisos_evidencia_verificados=True,
        )
        db.add(entrega)
        db.flush()
        db.add(
            PreguntaAsignada(
                entrega_id=entrega.id,
                pregunta_id=pregunta.id,
                orden=1,
                peso=1.0,
                version_pregunta=1,
            )
        )
        entrega_id = entrega.id
        token = crear_token_acceso(alumno)
    return entrega_id, token


def snapshot(sesiones: sessionmaker[Session], entrega_id: int) -> dict[str, object]:
    with sesiones() as db:
        entrega = db.get(Entrega, entrega_id)
        assert entrega is not None
        return {
            "cerrada": entrega.cerrada,
            "hora_entrega": entrega.hora_entrega,
            "procesando": entrega.procesando,
            "procesando_desde": entrega.procesando_desde,
            "reserva_id": entrega.reserva_id,
            "reserva_expira_en": entrega.reserva_expira_en,
            "version_estado": entrega.version_estado,
            "hash_envio": entrega.hash_envio,
            "respuestas": int(
                db.scalar(
                    select(func.count(RespuestaAlumno.id)).where(
                        RespuestaAlumno.entrega_id == entrega_id
                    )
                )
                or 0
            ),
            "calificaciones": int(
                db.scalar(
                    select(func.count(Calificacion.id)).where(
                        Calificacion.entrega_id == entrega_id
                    )
                )
                or 0
            ),
        }


def crear_sesiones(tmp_path, nombre: str) -> sessionmaker[Session]:
    engine = create_engine(
        f"sqlite:///{(tmp_path / nombre).as_posix()}",
        connect_args={"check_same_thread": False, "timeout": 30},
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


def enviar(
    sesiones: sessionmaker[Session], entrega_id: int, token: str, contenido: str = "A"
):
    def override_get_db() -> Generator[Session, None, None]:
        with sesiones() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            return client.post(
                "/entregas/enviar",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "entrega_id": entrega_id,
                    "respuestas": [
                        {"pregunta_id": 1, "contenido": contenido},
                    ],
                },
            )
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("punto_fallo", PUNTOS_FALLO_ENVIO)
def test_cada_fallo_anterior_al_commit_restaura_el_snapshot(
    tmp_path, monkeypatch, punto_fallo: str
) -> None:
    sesiones = crear_sesiones(tmp_path, f"atomicidad-{punto_fallo}.db")
    entrega_id, token = preparar_entrega(sesiones)
    previo = snapshot(sesiones, entrega_id)

    persistir_real = submission_router.persistir_envio_atomico

    def persistir_con_fallo(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        def inyectar(punto: str) -> None:
            if punto == punto_fallo:
                raise RuntimeError(f"fallo inyectado en {punto}")

        return persistir_real(*args, **kwargs, hook_transaccion=inyectar)

    monkeypatch.setattr(
        submission_router, "persistir_envio_atomico", persistir_con_fallo
    )
    respuesta = enviar(sesiones, entrega_id, token)

    assert respuesta.status_code == 500
    assert snapshot(sesiones, entrega_id) == previo


def test_envio_exitoso_confirma_respuestas_nota_y_cierre(tmp_path) -> None:
    sesiones = crear_sesiones(tmp_path, "atomicidad-exito.db")
    entrega_id, token = preparar_entrega(sesiones)

    respuesta = enviar(sesiones, entrega_id, token)

    assert respuesta.status_code == 200
    posterior = snapshot(sesiones, entrega_id)
    assert posterior["cerrada"] is True
    assert posterior["hora_entrega"] is not None
    assert posterior["procesando"] is False
    assert posterior["reserva_id"] is None
    assert posterior["respuestas"] == 1
    assert posterior["calificaciones"] == 1
    assert posterior["version_estado"] == 1
    assert posterior["hash_envio"] is not None


def test_reenvio_con_payload_distinto_se_rechaza_sin_modificar_resultado(
    tmp_path,
) -> None:
    sesiones = crear_sesiones(tmp_path, "atomicidad-reenvio-distinto.db")
    entrega_id, token = preparar_entrega(sesiones)
    primero = enviar(sesiones, entrega_id, token, "A")
    tras_primero = snapshot(sesiones, entrega_id)

    segundo = enviar(sesiones, entrega_id, token, "B")

    assert primero.status_code == 200
    assert segundo.status_code == 409
    assert snapshot(sesiones, entrega_id) == tras_primero


def test_fallo_del_corrector_libera_la_reserva_sin_persistir(
    tmp_path, monkeypatch
) -> None:
    sesiones = crear_sesiones(tmp_path, "atomicidad-fallo-corrector.db")
    entrega_id, token = preparar_entrega(sesiones)
    previo = snapshot(sesiones, entrega_id)

    def fallar_corrector(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        raise TimeoutError("timeout inyectado en el corrector")

    monkeypatch.setattr(submission_router, "grade_entrega", fallar_corrector)
    respuesta = enviar(sesiones, entrega_id, token)

    assert respuesta.status_code == 500
    assert snapshot(sesiones, entrega_id) == previo


def _persistir_y_terminar_proceso(
    database_url: str, entrega_id: int, reserva_id: str
) -> None:
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False, "timeout": 30},
        future=True,
    )
    sesiones = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with sesiones() as db:
        persistir_envio_atomico(
            db,
            entrega_id=entrega_id,
            reserva_id=reserva_id,
            respuestas=[{"pregunta_id": 1, "contenido": "A"}],
            resultado={
                "nota_global": 10.0,
                "preguntas_pendientes": 0,
                "desglose": [],
            },
            hora_entrega=utc_now(),
            entregado_automaticamente=False,
            hash_envio="a" * 64,
            hook_transaccion=lambda punto: (
                os._exit(17) if punto == PUNTO_DESPUES_CIERRE else None
            ),
        )


def test_caida_del_proceso_antes_del_commit_revierte_y_permite_recuperar(
    tmp_path,
) -> None:
    ruta = tmp_path / "atomicidad-caida-proceso.db"
    sesiones = crear_sesiones(tmp_path, ruta.name)
    entrega_id, _ = preparar_entrega(sesiones)
    previo = snapshot(sesiones, entrega_id)
    with sesiones() as db:
        reserva_id = reservar_entrega(db, entrega_id, utc_now(), 30)
    assert reserva_id is not None

    contexto = multiprocessing.get_context("spawn")
    proceso = contexto.Process(
        target=_persistir_y_terminar_proceso,
        args=(f"sqlite:///{ruta.as_posix()}", entrega_id, reserva_id),
    )
    proceso.start()
    proceso.join(timeout=45)

    if proceso.is_alive():
        proceso.terminate()
        proceso.join(timeout=5)
        pytest.fail("El proceso hijo no alcanzo el punto de caida inyectado a tiempo.")

    assert proceso.exitcode == 17
    tras_caida = snapshot(sesiones, entrega_id)
    assert tras_caida["cerrada"] is False
    assert tras_caida["respuestas"] == 0
    assert tras_caida["calificaciones"] == 0
    assert tras_caida["reserva_id"] == reserva_id

    with sesiones() as db:
        nueva_reserva = reservar_entrega(
            db, entrega_id, utc_now() + timedelta(seconds=60), 30
        )
        assert nueva_reserva is not None
        assert liberar_reserva(db, entrega_id, nueva_reserva) is True
    assert snapshot(sesiones, entrega_id) == previo
