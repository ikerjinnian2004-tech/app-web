from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class ResultadoComando:
    nombre: str
    comando: list[str]
    codigo_salida: int
    duracion_segundos: float
    stdout: str
    stderr: str
    obligatorio: bool


def ejecutar(
    nombre: str,
    comando: list[str],
    *,
    obligatorio: bool = True,
) -> ResultadoComando:
    inicio = time.monotonic()
    try:
        proceso = subprocess.run(
            comando,
            cwd=RAIZ,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            env=os.environ.copy(),
        )
        codigo_salida = proceso.returncode
        stdout = proceso.stdout
        stderr = proceso.stderr
    except OSError as exc:
        codigo_salida = 127
        stdout = ""
        stderr = f"{type(exc).__name__}: {exc}\n"
    return ResultadoComando(
        nombre=nombre,
        comando=comando,
        codigo_salida=codigo_salida,
        duracion_segundos=round(time.monotonic() - inicio, 3),
        stdout=stdout,
        stderr=stderr,
        obligatorio=obligatorio,
    )


def guardar_resultado(directorio: Path, resultado: ResultadoComando) -> None:
    prefijo = directorio / resultado.nombre
    (prefijo.with_suffix(".stdout.txt")).write_text(resultado.stdout, encoding="utf-8")
    (prefijo.with_suffix(".stderr.txt")).write_text(resultado.stderr, encoding="utf-8")
    (prefijo.with_suffix(".json")).write_text(
        json.dumps(asdict(resultado), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def commit_corto() -> str:
    resultado = ejecutar(
        "git_commit_para_ruta", ["git", "rev-parse", "--short=7", "HEAD"]
    )
    if resultado.codigo_salida != 0:
        return "sin-commit"
    return resultado.stdout.strip() or "sin-commit"


def comandos_baseline() -> list[tuple[str, list[str], bool]]:
    python = sys.executable
    return [
        ("01_git_status", ["git", "status", "--short"], True),
        ("02_git_diff", ["git", "diff", "--"], True),
        ("03_git_diff_cached", ["git", "diff", "--cached", "--"], True),
        ("04_git_log", ["git", "log", "-5", "--oneline"], True),
        ("05_git_commit", ["git", "rev-parse", "HEAD"], True),
        ("06_python_version", [python, "--version"], True),
        ("07_node_version", ["node", "--version"], False),
        ("08_docker_version", ["docker", "version"], False),
        ("09_compose_version", ["docker", "compose", "version"], False),
        ("10_docker_info", ["docker", "info"], False),
        ("11_pip_check", [python, "-m", "pip", "check"], True),
        (
            "12_compileall",
            [python, "-m", "compileall", "-q", "backend", "scripts", "tests"],
            True,
        ),
        ("13_pytest", [python, "-m", "pytest", "-q"], True),
        ("14_ruff_check", [python, "-m", "ruff", "check", "."], True),
        (
            "15_ruff_format",
            [python, "-m", "ruff", "format", "--check", "."],
            True,
        ),
        (
            "16_compose_config",
            ["docker", "compose", "config", "--quiet"],
            False,
        ),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Captura el baseline técnico sin ocultar fallos ni mezclar salidas."
    )
    parser.add_argument(
        "--salida",
        type=Path,
        help="Directorio de salida; por defecto usa artifacts/tfg-evidence/<commit>/baseline.",
    )
    args = parser.parse_args()

    salida = args.salida or (
        RAIZ / "artifacts" / "tfg-evidence" / commit_corto() / "baseline"
    )
    salida = salida.resolve()
    salida.mkdir(parents=True, exist_ok=True)

    resultados: list[ResultadoComando] = []
    for nombre, comando, obligatorio in comandos_baseline():
        print(f"[{nombre}] {' '.join(comando)}", flush=True)
        resultado = ejecutar(nombre, comando, obligatorio=obligatorio)
        guardar_resultado(salida, resultado)
        resultados.append(resultado)
        estado = "OK" if resultado.codigo_salida == 0 else "FALLO"
        print(
            f"[{nombre}] {estado} ({resultado.duracion_segundos:.3f} s)",
            flush=True,
        )

    resumen = {
        "generado_en_utc": datetime.now(UTC).isoformat(),
        "raiz": str(RAIZ),
        "salida": str(salida),
        "sistema": platform.platform(),
        "python": sys.version,
        "resultados": [asdict(resultado) for resultado in resultados],
    }
    (salida / "00_RESUMEN_BASELINE.json").write_text(
        json.dumps(resumen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    fallos_obligatorios = [
        resultado.nombre
        for resultado in resultados
        if resultado.obligatorio and resultado.codigo_salida != 0
    ]
    if fallos_obligatorios:
        print("Fallos obligatorios: " + ", ".join(fallos_obligatorios))
        return 1
    print(f"Baseline guardado en {salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
