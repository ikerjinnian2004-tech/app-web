from __future__ import annotations

import os
import sys
from pathlib import Path

from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def bootstrap_python_path() -> None:
    """Asegura que el paquete backend se pueda importar desde este script."""
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))


def bootstrap_local_environment() -> None:
    """Define un entorno mínimo para poder resetear la base sin un .env real."""
    # Si no existe un .env todavía, el script sigue pudiendo funcionar con
    # valores seguros de ejemplo. Si sí existe, esas variables reales tendrán
    # prioridad.
    os.environ.setdefault("DATABASE_URL", "sqlite:///./dev.db")
    os.environ.setdefault("SECRET_KEY", "clave-local-reset-1234567890-abcdefghijkl")
    os.environ.setdefault(
        "IDENTITY_HMAC_KEY", "clave-hmac-local-reset-minimo-32-caracteres"
    )
    os.environ.setdefault(
        "ALLOWED_ORIGINS", "http://localhost:5500,http://127.0.0.1:5500"
    )


def reset_sqlite_database(database_url: str) -> None:
    """Borra el fichero SQLite y recrea el esquema vacío."""
    from backend.database import create_tables

    db_path = database_url.replace("sqlite:///", "", 1)
    file_path = (
        PROJECT_ROOT / db_path if not Path(db_path).is_absolute() else Path(db_path)
    )

    # SQLite puede dejar ficheros auxiliares WAL/SHM junto al .db principal.
    # Si no se limpian también, parece que la base "se reseteó", pero el
    # directorio sigue arrastrando artefactos de ejecuciones anteriores.
    for candidate in (file_path, Path(f"{file_path}-wal"), Path(f"{file_path}-shm")):
        if candidate.exists():
            candidate.unlink()

    create_tables()


def reset_postgresql_database() -> None:
    """Vacía el esquema público de PostgreSQL y lo recrea limpio."""
    from backend.database import create_tables, engine

    # En el MVP mantener la limpieza del esquema público deja el script corto y
    # suficientemente claro. Para una evolución mayor lo natural sería Alembic.
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        connection.execute(text("CREATE SCHEMA public AUTHORIZATION CURRENT_USER"))
        connection.execute(text("GRANT ALL ON SCHEMA public TO CURRENT_USER"))
    create_tables()


def main() -> int:
    """Resetea la base de datos detectando automáticamente SQLite o PostgreSQL."""
    bootstrap_python_path()
    bootstrap_local_environment()

    from backend.config import get_settings
    from backend.database import is_sqlite_url

    settings = get_settings()

    if is_sqlite_url(settings.database_url):
        reset_sqlite_database(settings.database_url)
    else:
        reset_postgresql_database()

    print(f"Base de datos reseteada en: {settings.database_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
