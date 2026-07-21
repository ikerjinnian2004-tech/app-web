from __future__ import annotations

import json
import os
import random
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from backend.crud import (
    crear_entrega,
    get_examen_activo,
    get_ultima_entrega,
    seleccionar_preguntas,
)
from backend.database import Base
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
from backend.servicios_entregas import (
    PUNTOS_FALLO_ENVIO,
    liberar_reserva,
    persistir_envio_atomico,
    reservar_entrega,
)


pytestmark = pytest.mark.postgresql
POSTGRES_TEST_URL = os.environ.get("POSTGRES_TEST_URL")


def _comprobar_url_pruebas(database_url: str) -> None:
    url = make_url(database_url)
    assert url.drivername.startswith("postgresql")
    assert (url.database or "").endswith("_test")


@pytest.fixture
def sesiones_postgresql() -> sessionmaker[Session]:
    if not POSTGRES_TEST_URL:
        pytest.skip("POSTGRES_TEST_URL no está configurada.")
    if os.environ.get("ALLOW_POSTGRES_TEST_RESET") != "1":
        pytest.skip("El reinicio de la base PostgreSQL de pruebas no fue autorizado.")
    _comprobar_url_pruebas(POSTGRES_TEST_URL)
    engine = create_engine(
        POSTGRES_TEST_URL,
        pool_size=24,
        max_overflow=0,
        future=True,
    )
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    Base.metadata.create_all(engine)
    sesiones = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    try:
        yield sesiones
    finally:
        engine.dispose()


def _sembrar_entrega(sesiones: sessionmaker[Session]) -> int:
    with sesiones.begin() as db:
        alumno = UsuarioPermitido(
            rol="alumno",
            nombre="PostgreSQL",
            apellidos="Atomicidad",
            correo="postgresql-atomicidad@alu.uclm.es",
        )
        examen = Examen(
            titulo="PostgreSQL",
            duracion_segundos=3600,
            activo=True,
            estado="publicado",
            seleccion_json="{}",
        )
        db.add_all([alumno, examen])
        db.flush()
        pregunta = Pregunta(
            examen_id=examen.id,
            clave="postgresql-atomicidad",
            tipo="tipo_test",
            titulo="Atomicidad",
            enunciado="Selecciona A.",
            opciones_json='["A", "B"]',
            respuesta_correcta="A",
            orden=1,
            peso=1.0,
            estado="publicada",
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
            consentimiento_version="p" * 64,
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
        return entrega.id


def _snapshot(sesiones: sessionmaker[Session], entrega_id: int) -> tuple:
    with sesiones() as db:
        entrega = db.get(Entrega, entrega_id)
        assert entrega is not None
        return (
            entrega.cerrada,
            entrega.hora_entrega,
            entrega.procesando,
            entrega.reserva_id,
            entrega.hash_envio,
            int(
                db.scalar(
                    select(func.count(RespuestaAlumno.id)).where(
                        RespuestaAlumno.entrega_id == entrega_id
                    )
                )
                or 0
            ),
            int(
                db.scalar(
                    select(func.count(Calificacion.id)).where(
                        Calificacion.entrega_id == entrega_id
                    )
                )
                or 0
            ),
        )


@pytest.mark.parametrize("punto_fallo", PUNTOS_FALLO_ENVIO)
def test_postgresql_revierte_cada_fallo_desde_otra_conexion(
    sesiones_postgresql: sessionmaker[Session], punto_fallo: str
) -> None:
    entrega_id = _sembrar_entrega(sesiones_postgresql)
    previo = _snapshot(sesiones_postgresql, entrega_id)
    with sesiones_postgresql() as db:
        reserva_id = reservar_entrega(db, entrega_id, utc_now())
        assert reserva_id is not None

        def fallar(punto: str) -> None:
            if punto == punto_fallo:
                raise RuntimeError(f"fallo PostgreSQL inyectado en {punto}")

        with pytest.raises(RuntimeError):
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
                hook_transaccion=fallar,
            )
        assert liberar_reserva(db, entrega_id, reserva_id) is True
    assert _snapshot(sesiones_postgresql, entrega_id) == previo


def test_postgresql_veinte_inicios_concurrentes_recuperan_un_ganador(
    sesiones_postgresql: sessionmaker[Session],
) -> None:
    with sesiones_postgresql.begin() as db:
        alumno = UsuarioPermitido(
            rol="alumno",
            nombre="PostgreSQL",
            apellidos="Concurrente",
            correo="postgresql-concurrencia@alu.uclm.es",
        )
        examen = Examen(
            titulo="Concurrencia PostgreSQL",
            duracion_segundos=3600,
            activo=True,
            estado="publicado",
            seleccion_json=json.dumps({"tipo_test": 2}),
        )
        db.add_all([alumno, examen])
        db.flush()
        for indice in range(4):
            db.add(
                Pregunta(
                    examen_id=examen.id,
                    clave=f"postgresql-concurrencia-{indice}",
                    tipo="tipo_test",
                    titulo=f"Pregunta {indice}",
                    enunciado="Selecciona A.",
                    opciones_json='["A", "B"]',
                    respuesta_correcta="A",
                    orden=indice + 1,
                    peso=1.0,
                    estado="publicada",
                )
            )
        alumno_id = alumno.id
        examen_id = examen.id

    cantidad = 20
    barrera = Barrier(cantidad)

    def iniciar(indice: int) -> tuple[int, tuple[int, ...]]:
        with sesiones_postgresql() as db:
            examen = get_examen_activo(db)
            assert examen is not None
            assert get_ultima_entrega(db, alumno_id, examen_id) is None
            preguntas = seleccionar_preguntas(examen, random.Random(indice))
            barrera.wait(timeout=30)
            entrega = crear_entrega(
                db,
                alumno_id=alumno_id,
                examen=examen,
                hora_inicio=utc_now(),
                consentimiento_version="q" * 64,
                acepta_grabacion=True,
                permisos_evidencia_verificados=True,
                preguntas=preguntas,
            )
            return entrega.id, tuple(
                asignacion.pregunta_id for asignacion in entrega.preguntas_asignadas
            )

    with ThreadPoolExecutor(max_workers=cantidad) as ejecutor:
        resultados = list(ejecutor.map(iniciar, range(cantidad)))

    assert len({entrega_id for entrega_id, _ in resultados}) == 1
    assert len({preguntas for _, preguntas in resultados}) == 1
