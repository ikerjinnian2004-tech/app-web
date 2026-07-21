from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMIT = subprocess.check_output(
    ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True
).strip()


def ejecutar(
    nombre: str,
    comando: list[str],
    salida: Path,
    entorno: dict[str, str] | None = None,
) -> dict[str, object]:
    inicio = datetime.now(UTC)
    entorno_proceso = os.environ.copy()
    entorno_proceso["PYTHONUTF8"] = "1"
    if entorno:
        entorno_proceso.update(entorno)
    resultado = subprocess.run(
        comando,
        cwd=ROOT,
        env=entorno_proceso,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    fin = datetime.now(UTC)
    salida.write_text(
        f"$ {' '.join(comando)}\n\nSTDOUT\n{resultado.stdout}\nSTDERR\n{resultado.stderr}",
        encoding="utf-8",
    )
    estado = "IMPLEMENTADO Y EJECUTADO" if resultado.returncode == 0 else "BLOQUEADO"
    print(f"[{estado}] {nombre} (codigo {resultado.returncode})")
    return {
        "nombre": nombre,
        "comando": comando,
        "codigo_salida": resultado.returncode,
        "estado": estado,
        "duracion_segundos": round((fin - inicio).total_seconds(), 3),
        "log": str(salida.relative_to(ROOT)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verificacion reproducible del TFG.")
    parser.add_argument("--postgresql", action="store_true")
    parser.add_argument("--docker", action="store_true")
    parser.add_argument("--navegador", action="store_true")
    parser.add_argument("--seguridad", action="store_true")
    parser.add_argument(
        "--todo",
        action="store_true",
        help="Activa PostgreSQL, Docker, navegador y auditoria de dependencias.",
    )
    args = parser.parse_args()
    if args.todo:
        args.postgresql = args.docker = args.navegador = args.seguridad = True

    destino = ROOT / "artifacts" / "tfg-evidence" / COMMIT / "verificacion"
    cobertura = ROOT / "artifacts" / "tfg-evidence" / COMMIT / "cobertura"
    destino.mkdir(parents=True, exist_ok=True)
    cobertura.mkdir(parents=True, exist_ok=True)
    python = sys.executable
    pasos: list[tuple[str, list[str]]] = [
        (
            "compilacion",
            [
                python,
                "-m",
                "compileall",
                "-q",
                "backend",
                "scripts",
                "tests",
                "verification",
            ],
        ),
        ("ruff", [python, "-m", "ruff", "check", "."]),
        ("formato", [python, "-m", "ruff", "format", "--check", "."]),
        ("dependencias", [python, "-m", "pip", "check"]),
        (
            "suite_y_cobertura",
            [
                python,
                "-m",
                "pytest",
                "tests",
                "-q",
                "--cov=backend",
                "--cov-branch",
                f"--cov-report=xml:{cobertura / 'coverage.xml'}",
                f"--cov-report=html:{cobertura / 'html'}",
                "--cov-report=term",
                f"--junitxml={destino / 'pytest-junit.xml'}",
            ],
        ),
        (
            "modelo_estados",
            [
                python,
                "verification/submission_atomicity/modelo_estados.py",
                "--output",
                str(
                    ROOT
                    / "artifacts"
                    / "tfg-evidence"
                    / COMMIT
                    / "modelo_formal"
                    / "salida_modelo.json"
                ),
            ],
        ),
        (
            "simulacion_integral",
            [python, "scripts/simular_flujo_demo.py"],
        ),
    ]
    if args.postgresql:
        pasos.append(("postgresql", [python, "scripts/verificar_postgresql.py"]))
    if args.docker:
        pasos.extend(
            [
                (
                    "construccion_sandbox",
                    [
                        "docker",
                        "build",
                        "-f",
                        "Dockerfile.sandbox",
                        "-t",
                        "evaluador-sandbox:local",
                        ".",
                    ],
                ),
                ("sandbox_real", [python, "scripts/verificar_sandbox_docker.py"]),
            ]
        )
    if args.navegador:
        pasos.append(("navegador", [python, "scripts/capturar_recorrido_navegador.py"]))
    if args.seguridad:
        pasos.append(
            (
                "auditoria_dependencias",
                [python, "-m", "pip_audit", "-r", "requirements.txt"],
            )
        )

    resultados = [
        ejecutar(nombre, comando, destino / f"{indice:02d}_{nombre}.log")
        for indice, (nombre, comando) in enumerate(pasos, start=1)
    ]
    informe = {
        "generado_en_utc": datetime.now(UTC).isoformat(),
        "commit_base": COMMIT,
        "argumentos": vars(args),
        "resultados": resultados,
    }
    (destino / "resumen.json").write_text(
        json.dumps(informe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0 if all(item["codigo_salida"] == 0 for item in resultados) else 1


if __name__ == "__main__":
    raise SystemExit(main())
