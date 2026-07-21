from concurrent.futures import ThreadPoolExecutor
import json
import random
from datetime import timedelta
from threading import Barrier

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.crud import (
    crear_entrega,
    get_examen_activo,
    get_ultima_entrega,
    liberar_entrega,
    reclamar_entrega,
    seleccionar_preguntas,
)
from backend.database import Base
from backend.models import Entrega, Examen, Pregunta, UsuarioPermitido, utc_now


def crear_entrega_compartida(tmp_path) -> tuple[sessionmaker, int]:
    ruta = (tmp_path / "concurrencia.db").as_posix()
    engine = create_engine(
        f"sqlite:///{ruta}",
        connect_args={"check_same_thread": False, "timeout": 30},
        future=True,
    )
    Base.metadata.create_all(engine)
    sesiones = sessionmaker(bind=engine, autoflush=False, future=True)
    with sesiones() as db:
        alumno = UsuarioPermitido(
            rol="alumno",
            nombre="Prueba",
            apellidos="Concurrente",
            correo="concurrencia@alu.uclm.es",
        )
        examen = Examen(
            titulo="Concurrencia",
            duracion_segundos=3600,
            activo=True,
        )
        db.add_all([alumno, examen])
        db.flush()
        entrega = Entrega(
            alumno_id=alumno.id,
            examen_id=examen.id,
            version_examen=1,
            titulo_examen=examen.titulo,
            duracion_examen_segundos=3600,
            modo_calificacion="parcial_por_tests",
            hora_inicio=utc_now(),
            consentimiento_version="x" * 64,
            acepta_grabacion=True,
        )
        db.add(entrega)
        db.commit()
        return sesiones, entrega.id


def test_solo_una_peticion_reclama_la_entrega(tmp_path) -> None:
    sesiones, entrega_id = crear_entrega_compartida(tmp_path)
    barrera = Barrier(2)

    def intentar_reserva() -> bool:
        with sesiones() as db:
            barrera.wait(timeout=5)
            return reclamar_entrega(db, entrega_id, utc_now())

    with ThreadPoolExecutor(max_workers=2) as ejecutor:
        resultados = list(ejecutor.map(lambda _: intentar_reserva(), range(2)))

    assert sorted(resultados) == [False, True]


def test_reserva_caducada_se_recupera_y_puede_liberarse(tmp_path) -> None:
    sesiones, entrega_id = crear_entrega_compartida(tmp_path)
    with sesiones() as db:
        entrega = db.get(Entrega, entrega_id)
        assert entrega is not None
        entrega.procesando = True
        entrega.procesando_desde = utc_now() - timedelta(minutes=5)
        entrega.reserva_id = "reserva-caducada"
        entrega.reserva_expira_en = utc_now() - timedelta(minutes=4)
        db.commit()

    with sesiones() as db:
        assert reclamar_entrega(db, entrega_id, utc_now()) is True
        liberar_entrega(db, entrega_id)
        entrega = db.get(Entrega, entrega_id)
        assert entrega is not None
        assert entrega.procesando is False
        assert entrega.procesando_desde is None
        assert entrega.reserva_id is None
        assert entrega.reserva_expira_en is None


def preparar_inicio_concurrente(tmp_path, cantidad: int):
    ruta = (tmp_path / f"inicio-{cantidad}.db").as_posix()
    engine = create_engine(
        f"sqlite:///{ruta}",
        connect_args={"check_same_thread": False, "timeout": 30},
        pool_size=cantidad,
        max_overflow=0,
        future=True,
    )
    Base.metadata.create_all(engine)
    sesiones = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with sesiones.begin() as db:
        alumno = UsuarioPermitido(
            rol="alumno",
            nombre="Inicio",
            apellidos="Concurrente",
            correo=f"inicio-{cantidad}@alu.uclm.es",
        )
        examen = Examen(
            titulo="Inicio concurrente",
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
                    clave=f"inicio-{cantidad}-{indice}",
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
    return sesiones, alumno_id, examen_id


@pytest.mark.parametrize("cantidad", [2, 10, 20])
def test_inicio_concurrente_crea_un_solo_intento_y_recupera_el_ganador(
    tmp_path, cantidad: int
) -> None:
    sesiones, alumno_id, examen_id = preparar_inicio_concurrente(tmp_path, cantidad)
    barrera = Barrier(cantidad)

    def iniciar(indice: int) -> tuple[int, tuple[int, ...]]:
        with sesiones() as db:
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
                consentimiento_version="c" * 64,
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
    with sesiones() as db:
        entregas = list(db.query(Entrega).all())
        assert len(entregas) == 1
