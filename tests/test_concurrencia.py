from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.crud import liberar_entrega, reclamar_entrega
from backend.database import Base
from backend.models import Entrega, Examen, UsuarioPermitido, utc_now


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
        db.commit()

    with sesiones() as db:
        assert reclamar_entrega(db, entrega_id, utc_now()) is True
        liberar_entrega(db, entrega_id)
        entrega = db.get(Entrega, entrega_id)
        assert entrega is not None
        assert entrega.procesando is False
        assert entrega.procesando_desde is None
