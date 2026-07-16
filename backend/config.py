from functools import lru_cache
from pathlib import Path
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from typing_extensions import Annotated

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Configuración leída desde el entorno o desde ``.env``."""

    database_url: str = Field(alias="DATABASE_URL")
    secret_key: str = Field(alias="SECRET_KEY")
    identity_hmac_key: str = Field(alias="IDENTITY_HMAC_KEY")

    exam_duration_minutes: int = Field(
        default=90, ge=1, le=480, alias="EXAM_DURATION_MINUTES"
    )
    database_pool_size: int = Field(
        default=10, ge=1, le=100, alias="DATABASE_POOL_SIZE"
    )
    database_max_overflow: int = Field(
        default=20, ge=0, le=200, alias="DATABASE_MAX_OVERFLOW"
    )
    database_pool_timeout_seconds: int = Field(
        default=30, ge=1, le=300, alias="DATABASE_POOL_TIMEOUT_SECONDS"
    )
    database_pool_recycle_seconds: int = Field(
        default=1800, ge=60, le=86_400, alias="DATABASE_POOL_RECYCLE_SECONDS"
    )

    sandbox_timeout_seconds: int = Field(
        default=3, ge=1, le=30, alias="SANDBOX_TIMEOUT_SECONDS"
    )
    sandbox_max_output_chars: int = Field(
        default=5000, ge=100, le=100_000, alias="SANDBOX_MAX_OUTPUT_CHARS"
    )
    sandbox_use_docker: bool = Field(default=False, alias="SANDBOX_USE_DOCKER")
    sandbox_image: str = Field(default="evaluador-sandbox:local", alias="SANDBOX_IMAGE")
    sandbox_mem_limit_mb: int = Field(
        default=64, ge=32, le=1024, alias="SANDBOX_MEM_LIMIT_MB"
    )
    sandbox_cpu: float = Field(default=0.5, ge=0.1, le=4, alias="SANDBOX_CPU")
    sandbox_pids_limit: int = Field(
        default=50, ge=1, le=256, alias="SANDBOX_PIDS_LIMIT"
    )
    evidencia_max_bytes: int = Field(
        default=15_000_000,
        ge=1024,
        le=100_000_000,
        alias="EVIDENCIA_MAX_BYTES",
    )
    evidencia_duracion_segundos: int = Field(
        default=15, ge=1, le=120, alias="EVIDENCIA_DURACION_SEGUNDOS"
    )

    allowed_origins: Annotated[list[str], NoDecode] = Field(alias="ALLOWED_ORIGINS")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    healthcheck_interval_seconds: int = Field(
        default=30, ge=5, le=300, alias="HEALTHCHECK_INTERVAL_SECONDS"
    )

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: str | list[str]) -> list[str]:
        origins = value if isinstance(value, list) else str(value).split(",")
        cleaned = [origin.strip() for origin in origins if origin and origin.strip()]
        if "*" in cleaned:
            raise ValueError("ALLOWED_ORIGINS no puede contener '*'.")
        return cleaned

    @field_validator("secret_key", "identity_hmac_key")
    @classmethod
    def validate_secret(cls, value: str) -> str:
        if len(value) < 32 or "cambia-esto" in value:
            raise ValueError(
                "La clave debe tener al menos 32 caracteres y no usar el ejemplo."
            )
        return value

    @property
    def exam_duration_seconds(self) -> int:
        return self.exam_duration_minutes * 60


@lru_cache
def get_settings() -> Settings:
    return Settings()
