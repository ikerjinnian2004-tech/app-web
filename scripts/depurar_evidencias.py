from __future__ import annotations

import argparse
import sys
from datetime import timedelta
from pathlib import Path

from sqlalchemy import delete, func, select

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from backend.config import get_settings  # noqa: E402
from backend.database import SessionLocal  # noqa: E402
from backend.models import EvidenciaAuditoria, utc_now  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Lista o elimina evidencias vencidas segun la politica tecnica."
    )
    parser.add_argument(
        "--aplicar",
        action="store_true",
        help="Confirma el borrado; sin este indicador solo se informa.",
    )
    args = parser.parse_args()
    limite = utc_now() - timedelta(days=get_settings().evidencia_retencion_dias)
    with SessionLocal() as db:
        cantidad = db.scalar(
            select(func.count(EvidenciaAuditoria.id)).where(
                EvidenciaAuditoria.creada_en < limite
            )
        )
        print(f"Evidencias vencidas antes de {limite.isoformat()}: {cantidad}")
        if args.aplicar and cantidad:
            db.execute(
                delete(EvidenciaAuditoria).where(EvidenciaAuditoria.creada_en < limite)
            )
            db.commit()
            print(f"Evidencias eliminadas: {cantidad}")
        else:
            print("Modo consulta: no se ha eliminado ningun contenido.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
