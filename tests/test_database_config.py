from backend.config import Settings
from backend.database import build_engine_kwargs, is_sqlite_url


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
