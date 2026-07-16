from collections.abc import Generator
from typing import Any

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from backend.config import Settings, get_settings


def is_sqlite_url(database_url: str) -> bool:
    """Detecta si una URL de SQLAlchemy apunta a SQLite."""
    return database_url.startswith("sqlite")


def build_engine_kwargs(settings: Settings) -> dict[str, Any]:
    """Construye los kwargs del engine a partir de la configuración."""
    # Esta función existe por dos motivos:
    # 1) hace más legible la creación del engine;
    # 2) permite probar la política de conexión sin depender de un servidor real.
    if is_sqlite_url(settings.database_url):
        return {
            "future": True,
            "connect_args": {
                "check_same_thread": False,
                "timeout": 30,
            },
        }

    return {
        "future": True,
        "pool_size": settings.database_pool_size,
        "max_overflow": settings.database_max_overflow,
        "pool_pre_ping": True,
        "pool_timeout": settings.database_pool_timeout_seconds,
        "pool_recycle": settings.database_pool_recycle_seconds,
    }


def attach_sqlite_pragmas(engine: Engine, database_url: str) -> None:
    """Activa pragmas útiles cuando el engine trabaja contra SQLite."""
    if not is_sqlite_url(database_url):
        return

    # El listener se registra sobre este engine concreto, no sobre la clase
    # global Engine. Así evitamos que una configuración pensada para SQLite
    # interfiera con motores de PostgreSQL creados en tests o scripts.
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record) -> None:  # noqa: ANN001, ARG001
        """Ajusta SQLite para que se parezca un poco más a un uso real."""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()


def create_project_engine(settings: Settings) -> Engine:
    """Crea el engine principal del proyecto según el backend configurado."""
    engine = create_engine(settings.database_url, **build_engine_kwargs(settings))
    attach_sqlite_pragmas(engine, settings.database_url)
    return engine


settings = get_settings()
engine = create_project_engine(settings)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)

# Base común de todos los modelos ORM.
Base = declarative_base()


def create_tables() -> None:
    """Actualiza el esquema y crea las tablas declaradas por los modelos."""
    # El import local evita ciclos durante el arranque.
    # Lo importante aquí es que Base.metadata solo conoce las tablas
    # una vez que los modelos han sido importados.
    import backend.models  # noqa: F401
    from backend.migraciones import preparar_esquema

    preparar_esquema(engine, Base.metadata)


def get_db() -> Generator[Session, None, None]:
    """Abre una sesión por request y la cierra siempre al terminar."""
    # FastAPI entregará esta sesión al router que la pida como dependencia.
    # El bloque finally garantiza el cierre incluso si la petición termina con
    # una excepción, algo importante para no ir dejando conexiones abiertas.
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def check_db_health() -> bool:
    """Comprueba que la base de datos responde a un SELECT 1."""
    session = SessionLocal()
    try:
        session.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False
    finally:
        session.close()
