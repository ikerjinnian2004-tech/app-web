from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMIT = subprocess.check_output(
    ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True
).strip()


def git(*arguments: str) -> dict[str, object]:
    result = subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    return {
        "comando": ["git", *arguments],
        "codigo_salida": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def describe(path: Path) -> dict[str, object]:
    exists = path.exists()
    size = 0
    if exists and path.is_file():
        size = path.stat().st_size
    elif exists and path.is_dir():
        size = sum(item.stat().st_size for item in path.rglob("*") if item.is_file())
    return {
        "ruta": str(path.relative_to(ROOT)),
        "existe": exists,
        "tamano_bytes": size,
        "modificado_en_utc": (
            datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat()
            if exists
            else None
        ),
        "estado_git": "no versionado preexistente",
        "posible_proposito": "entregable academico previo del usuario",
        "referencias_encontradas": "registrado en el baseline inicial",
        "recomendacion": "conservar; revisar y versionar por separado si procede",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Auditoria de limpieza de solo lectura."
    )
    parser.add_argument("--etapa", choices=("antes", "despues"), required=True)
    args = parser.parse_args()
    destination = ROOT / "artifacts" / "tfg-evidence" / COMMIT / "limpieza"
    destination.mkdir(parents=True, exist_ok=True)
    commands = {
        "git_status": git("status", "--untracked-files=all"),
        "git_clean_dry_run": git("clean", "-ndx"),
        "git_untracked": git("ls-files", "--others", "--exclude-standard"),
        "git_diff_check": git("diff", "--check"),
        "git_diff_stat": git("diff", "--stat"),
        "gitignore_diff": git("diff", "--", ".gitignore"),
    }
    report = {
        "generado_en_utc": datetime.now(UTC).isoformat(),
        "commit_base": COMMIT,
        "etapa": args.etapa,
        "comandos": commands,
        "cuarentena": [
            describe(ROOT / "EVIDENCIAS_MEMORIA_TFG"),
            describe(ROOT / "EVIDENCIAS_MEMORIA_TFG.zip"),
            describe(ROOT / "Entregable TFG.pdf"),
        ],
    }
    output = destination / f"auditoria_{args.etapa}.json"
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(output.relative_to(ROOT))
    return 0 if all(item["codigo_salida"] == 0 for item in commands.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
