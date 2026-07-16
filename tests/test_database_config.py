from backend.config import Settings
import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect, text

from backend.database import Base, build_engine_kwargs, is_sqlite_url
from backend.migraciones import preparar_esquema
import backend.models  # noqa: F401


def make_settings(database_url: str) -> Settings:
    """Construye settings mínimos para probar la política de conexión."""
    return Settings.model_validate(
        {
            "DATABASE_URL": database_url,
            "SECRET_KEY": "clave-de-tests-1234567890-abcdefghijkl",
            "IDENTITY_HMAC_KEY": "clave-hmac-de-tests-minimo-32-caracteres",
            "ALLOWED_ORIGINS": "http://localhost:5500",
        }
    )


def test_is_sqlite_url_detecta_sqlite() -> None:
    """Una URL sqlite debe detectarse como tal."""
    assert is_sqlite_url("sqlite:///./dev.db") is True


def test_is_sqlite_url_descarta_postgresql() -> None:
    """Una URL PostgreSQL no debe confundirse con SQLite."""
    assert is_sqlite_url("postgresql+psycopg2://user:pass@db:5432/app") is False


def test_sqlite_engine_kwargs_incluye_connect_args() -> None:
    """SQLite necesita argumentos de conexión distintos a PostgreSQL."""
    kwargs = build_engine_kwargs(make_settings("sqlite:///./dev.db"))
    assert kwargs["future"] is True
    assert kwargs["connect_args"]["check_same_thread"] is False
    assert kwargs["connect_args"]["timeout"] == 30


def test_postgresql_engine_kwargs_incluye_pooling() -> None:
    """PostgreSQL debe activar parámetros de pool apropiados para concurrencia."""
    kwargs = build_engine_kwargs(
        make_settings("postgresql+psycopg2://user:pass@db:5432/app")
    )
    assert kwargs["future"] is True
    assert kwargs["pool_size"] == 10
    assert kwargs["max_overflow"] == 20
    assert kwargs["pool_pre_ping"] is True
    assert kwargs["pool_timeout"] == 30
    assert kwargs["pool_recycle"] == 1800


def test_configuracion_rechaza_limites_inseguros() -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate(
            {
                "DATABASE_URL": "sqlite:///./dev.db",
                "SECRET_KEY": "clave-de-tests-1234567890-abcdefghijkl",
                "IDENTITY_HMAC_KEY": "clave-hmac-de-tests-minimo-32-caracteres",
                "ALLOWED_ORIGINS": "http://localhost:5500",
                "SANDBOX_TIMEOUT_SECONDS": 0,
                "SANDBOX_MEM_LIMIT_MB": 8,
            }
        )


def test_migracion_actualiza_un_esquema_sqlite_anterior() -> None:
    engine = create_engine("sqlite://", future=True)
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE examenes ("
                "id INTEGER PRIMARY KEY, titulo VARCHAR(200) NOT NULL, "
                "duracion_segundos INTEGER NOT NULL, activo BOOLEAN NOT NULL, "
                "creado_en TIMESTAMP NOT NULL)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE preguntas ("
                "id INTEGER PRIMARY KEY, examen_id INTEGER NOT NULL, "
                "tipo VARCHAR(40) NOT NULL, titulo VARCHAR(200) NOT NULL, "
                "enunciado TEXT NOT NULL, codigo_plantilla TEXT, "
                "codigo_solucion TEXT, opciones_json TEXT, "
                "respuesta_correcta TEXT, orden INTEGER NOT NULL, "
                "peso FLOAT NOT NULL)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE casos_prueba ("
                "id INTEGER PRIMARY KEY, pregunta_id INTEGER NOT NULL, "
                "descripcion VARCHAR(200) NOT NULL, codigo_test TEXT NOT NULL, "
                "salida_esperada TEXT NOT NULL, peso FLOAT NOT NULL)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE respuestas_alumno ("
                "id INTEGER PRIMARY KEY, entrega_id INTEGER NOT NULL, "
                "pregunta_id INTEGER NOT NULL, contenido TEXT NOT NULL)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE entregas ("
                "id INTEGER PRIMARY KEY, alumno_id INTEGER NOT NULL, "
                "examen_id INTEGER NOT NULL, hora_inicio TIMESTAMP NOT NULL, "
                "hora_entrega TIMESTAMP, consentimiento_version VARCHAR(64) NOT NULL, "
                "acepta_grabacion BOOLEAN NOT NULL, "
                "entregado_automaticamente BOOLEAN NOT NULL, "
                "cerrada BOOLEAN NOT NULL)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO examenes "
                "(id, titulo, duracion_segundos, activo, creado_en) "
                "VALUES (1, 'Examen legado', 3600, TRUE, CURRENT_TIMESTAMP)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO preguntas "
                "(id, examen_id, tipo, titulo, enunciado, orden, peso) "
                "VALUES (7, 1, 'tipo_test', 'Legado', '', 1, 1.0)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO entregas "
                "(id, alumno_id, examen_id, hora_inicio, consentimiento_version, "
                "acepta_grabacion, entregado_automaticamente, cerrada) "
                "VALUES (3, 1, 1, CURRENT_TIMESTAMP, 'version', TRUE, FALSE, FALSE)"
            )
        )

    preparar_esquema(engine, Base.metadata)
    preparar_esquema(engine, Base.metadata)

    inspector = inspect(engine)
    assert "preguntas_asignadas" in inspector.get_table_names()
    assert "clave" in {
        columna["name"] for columna in inspector.get_columns("preguntas")
    }
    with engine.connect() as connection:
        clave = connection.execute(
            text("SELECT clave FROM preguntas WHERE id = 7")
        ).scalar_one()
        versiones = connection.execute(
            text("SELECT COUNT(*) FROM migraciones_esquema")
        ).scalar_one()
        versiones_examen = connection.execute(
            text("SELECT COUNT(*) FROM versiones_examen WHERE examen_id = 1")
        ).scalar_one()
        instantanea = connection.execute(
            text(
                "SELECT titulo_examen, duracion_examen_segundos "
                "FROM entregas WHERE id = 3"
            )
        ).one()
    assert clave == "pregunta-7"
    assert versiones == 6
    assert versiones_examen == 1
    assert instantanea == ("Examen legado", 3600)
