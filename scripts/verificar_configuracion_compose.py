from __future__ import annotations

import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMIT = subprocess.check_output(
    ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True
).strip()


def ejecutar(nombre: str, comando: list[str], destino: Path) -> dict[str, object]:
    entorno = os.environ.copy()
    entorno["ENV_FILE"] = ".env.example"
    resultado = subprocess.run(
        comando,
        cwd=ROOT,
        env=entorno,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    (destino / f"{nombre}.stdout.txt").write_text(resultado.stdout, encoding="utf-8")
    (destino / f"{nombre}.stderr.txt").write_text(resultado.stderr, encoding="utf-8")
    return {
        "nombre": nombre,
        "comando": comando,
        "codigo_salida": resultado.returncode,
        "estado": (
            "CONFIGURADO, NO VALIDADO" if resultado.returncode == 0 else "BLOQUEADO"
        ),
        "nota": "La validacion estatica no inicia contenedores ni conecta servicios.",
    }


def main() -> int:
    destino = ROOT / "artifacts" / "tfg-evidence" / COMMIT / "compose"
    destino.mkdir(parents=True, exist_ok=True)
    resultados = [
        ejecutar(
            "compose_aplicacion",
            ["docker", "compose", "-f", "docker-compose.yml", "config", "--quiet"],
            destino,
        ),
        ejecutar(
            "compose_postgresql",
            [
                "docker",
                "compose",
                "-f",
                "docker-compose.postgresql.yml",
                "config",
                "--quiet",
            ],
            destino,
        ),
    ]
    informe = {
        "generado_en_utc": datetime.now(UTC).isoformat(),
        "commit_base": COMMIT,
        "resultados": resultados,
    }
    (destino / "resumen.json").write_text(
        json.dumps(informe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(informe, ensure_ascii=False, indent=2))
    return 0 if all(item["codigo_salida"] == 0 for item in resultados) else 1


if __name__ == "__main__":
    raise SystemExit(main())
