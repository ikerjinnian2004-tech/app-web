from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_ROOTS = {
    ROOT / ".git",
    ROOT / "artifacts",
    ROOT / "EVIDENCIAS_MEMORIA_TFG",
}
EXACT_TARGETS = (
    ROOT / ".venv",
    ROOT / ".pytest_cache",
    ROOT / ".ruff_cache",
    ROOT / ".mypy_cache",
    ROOT / ".hypothesis",
    ROOT / ".tox",
    ROOT / ".nox",
    ROOT / ".coverage",
    ROOT / "coverage.xml",
    ROOT / "htmlcov",
    ROOT / "dev.db",
    ROOT / "dev.db-shm",
    ROOT / "dev.db-wal",
    ROOT / "test_runtime.db",
    ROOT / "tmp",
)


def inside_root(path: Path) -> bool:
    try:
        path.resolve().relative_to(ROOT.resolve())
    except ValueError:
        return False
    return True


def discover() -> list[Path]:
    targets = {path for path in EXACT_TARGETS if path.exists()}
    for top in (
        ROOT / "backend",
        ROOT / "scripts",
        ROOT / "tests",
        ROOT / "verification",
    ):
        if not top.exists():
            continue
        targets.update(path for path in top.rglob("__pycache__") if path.is_dir())
        targets.update(path for path in top.rglob("*.pyc") if path.is_file())
        targets.update(path for path in top.rglob("*.pyo") if path.is_file())
    safe_targets = []
    for path in targets:
        if not inside_root(path):
            raise RuntimeError(f"Ruta fuera del repositorio: {path}")
        if any(
            path == excluded or excluded in path.parents for excluded in EXCLUDED_ROOTS
        ):
            raise RuntimeError(f"Ruta excluida de la limpieza: {path}")
        safe_targets.append(path)
    return sorted(safe_targets, key=lambda item: len(item.parts), reverse=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Limpia solo caches, bases demo y entornos regenerables."
    )
    parser.add_argument("--aplicar", action="store_true")
    args = parser.parse_args()
    targets = discover()
    for path in targets:
        print(f"{'ELIMINAR' if args.aplicar else 'BORRARIA'} {path.relative_to(ROOT)}")
        if not args.aplicar or not path.exists():
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    if not args.aplicar:
        print("Modo informativo. Use --aplicar para confirmar esta lista cerrada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
