from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


RAIZ = Path(__file__).resolve().parents[1]
URL_PREDETERMINADA = (
    "postgresql+psycopg2://evaluador_test:evaluador_test_local"
    "@127.0.0.1:55432/evaluador_test"
)


def validar_destino_pruebas(database_url: str) -> None:
    url = make_url(database_url)
    if not url.drivername.startswith("postgresql"):
        raise ValueError("POSTGRES_TEST_URL debe apuntar a PostgreSQL.")
    if not (url.database or "").endswith("_test"):
        raise ValueError(
            "La base de datos debe terminar en '_test' para permitir el reinicio."
        )
    host = (url.host or "").lower()
    if host not in {"127.0.0.1", "localhost", "db_postgresql_test"}:
        raise ValueError(
            "El verificador solo reinicia la base local o el servicio dedicado de CI."
        )


def reiniciar_esquema(database_url: str) -> None:
    if os.environ.get("ALLOW_POSTGRES_TEST_RESET") != "1":
        raise RuntimeError(
            "Define ALLOW_POSTGRES_TEST_RESET=1 para confirmar el reinicio de la "
            "base PostgreSQL dedicada a pruebas."
        )
    engine = create_engine(database_url, future=True)
    try:
        with engine.begin() as connection:
            connection.execute(text("DROP SCHEMA public CASCADE"))
            connection.execute(text("CREATE SCHEMA public"))
    finally:
        engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reinicia la base PostgreSQL de pruebas y ejecuta su suite crítica."
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("POSTGRES_TEST_URL", URL_PREDETERMINADA),
    )
    parser.add_argument(
        "--salida-junit",
        type=Path,
        default=RAIZ
        / "artifacts"
        / "tfg-evidence"
        / "postgresql"
        / "postgresql-junit.xml",
    )
    args = parser.parse_args()
    validar_destino_pruebas(args.database_url)
    reiniciar_esquema(args.database_url)

    args.salida_junit.parent.mkdir(parents=True, exist_ok=True)
    entorno = os.environ.copy()
    entorno["POSTGRES_TEST_URL"] = args.database_url
    entorno["ALLOW_POSTGRES_TEST_RESET"] = "1"
    entorno["EVIDENCE_RUN_AT"] = datetime.now(UTC).isoformat()
    comando = [
        sys.executable,
        "-m",
        "pytest",
        "tests/integration/test_postgresql.py",
        "-q",
        f"--junitxml={args.salida_junit}",
    ]
    print("Ejecutando:", " ".join(comando), flush=True)
    resultado = subprocess.run(comando, cwd=RAIZ, env=entorno, check=False)
    return resultado.returncode


if __name__ == "__main__":
    raise SystemExit(main())
