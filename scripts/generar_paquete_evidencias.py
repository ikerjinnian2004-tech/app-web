from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import zipfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_ROOT = ROOT / "artifacts" / "tfg-evidence"
REQUIRED_DIRECTORIES = (
    "entorno",
    "baseline",
    "atomicidad",
    "concurrencia",
    "postgresql",
    "docker",
    "sandbox_adversarial",
    "navegador",
    "multimedia",
    "capturas",
    "diagramas",
    "cobertura",
    "ci",
    "seguridad",
    "logs",
    "informes",
    "modelo_formal",
    "sql",
)
FORBIDDEN_SUFFIXES = {
    ".db",
    ".sqlite",
    ".sqlite3",
    ".pyc",
    ".pyo",
}
FORBIDDEN_NAMES = {
    ".env",
    ".coverage",
    "fallo_navegador.png",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def commit_base() -> tuple[str, str]:
    complete = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    return complete, complete[:7]


def allowed(source: Path) -> bool:
    lowered = {part.lower() for part in source.parts}
    return (
        source.is_file()
        and source.name not in FORBIDDEN_NAMES
        and source.suffix.lower() not in FORBIDDEN_SUFFIXES
        and "__pycache__" not in lowered
        and ".pytest_cache" not in lowered
        and ".ruff_cache" not in lowered
        and ".venv" not in lowered
    )


def copy_file(source: Path, destination: Path) -> None:
    if not allowed(source):
        raise ValueError(f"La lista blanca rechazo: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def copy_tree(source: Path, destination: Path) -> None:
    if not source.exists():
        return
    for item in sorted(source.rglob("*")):
        if allowed(item):
            copy_file(item, destination / item.relative_to(source))


def metadata(relative: str) -> tuple[str, str, str, str]:
    prefix = relative.split("/", maxsplit=1)[0]
    mapping = {
        "baseline": (
            "python scripts/capturar_baseline.py",
            "IMPLEMENTADO Y EJECUTADO",
            "Estado inicial sin manipular",
            "Es una instantanea local y puede contener rutas de la maquina",
        ),
        "atomicidad": (
            "python -m pytest tests/test_atomicidad_envio.py",
            "IMPLEMENTADO Y EJECUTADO",
            "Rollback, idempotencia, interrupcion y cierre atomico",
            "Ejecucion local SQLite; PostgreSQL se registra por separado",
        ),
        "concurrencia": (
            "python -m pytest tests/test_concurrencia.py",
            "IMPLEMENTADO Y EJECUTADO",
            "Unicidad en carreras de 2, 10 y 20 solicitudes",
            "Intercalados PostgreSQL pendientes",
        ),
        "postgresql": (
            "python scripts/verificar_postgresql.py",
            "CONFIGURADO, NO VALIDADO",
            "Ruta de integracion PostgreSQL",
            "Daemon Docker no disponible en esta ejecucion",
        ),
        "docker": (
            "python scripts/verificar_sandbox_docker.py",
            "BLOQUEADO",
            "Estado del runtime Docker",
            "No se crearon contenedores reales",
        ),
        "sandbox_adversarial": (
            "python scripts/verificar_sandbox_docker.py",
            "IMPLEMENTADO, NO EJECUTADO EN ESTE ENTORNO",
            "Campana de aislamiento real preparada",
            "Requiere daemon y maquina aislada con opt-in destructivo",
        ),
        "navegador": (
            "python scripts/capturar_recorrido_navegador.py",
            "IMPLEMENTADO Y EJECUTADO",
            "Recorrido de alumnado y profesorado en Brave",
            "Medios sinteticos; no prueba hardware ni identidad real",
        ),
        "multimedia": (
            "python scripts/capturar_recorrido_navegador.py",
            "IMPLEMENTADO Y EJECUTADO",
            "Evento y evidencia multimedia sintetica",
            "No contiene cara, voz ni pantalla personal",
        ),
        "capturas": (
            "python scripts/capturar_recorrido_navegador.py",
            "IMPLEMENTADO Y EJECUTADO",
            "Vistas reales del recorrido automatizado",
            "Las capturas de infraestructura bloqueada no se inventan",
        ),
        "diagramas": (
            "python scripts/generar_diagramas.py",
            "IMPLEMENTADO Y EJECUTADO",
            "Diagramas derivados del codigo final",
            "Son modelos explicativos simplificados",
        ),
        "cobertura": (
            "python scripts/verificar_tfg.py",
            "IMPLEMENTADO Y EJECUTADO",
            "Cobertura de lineas y ramas",
            "Cobertura no implica ausencia de defectos",
        ),
        "ci": (
            "inspeccion de .github/workflows/ci.yml",
            "CONFIGURADO, NO VALIDADO",
            "Jobs separados de calidad, datos, aislamiento y navegador",
            "No se ejecuto GitHub Actions durante este trabajo",
        ),
        "seguridad": (
            "python -m pip_audit -r requirements.txt",
            "IMPLEMENTADO Y EJECUTADO",
            "Controles, privacidad y auditoria de dependencias",
            "La base de vulnerabilidades cambia y no sustituye revision juridica",
        ),
        "logs": (
            "python scripts/verificar_tfg.py",
            "IMPLEMENTADO Y EJECUTADO",
            "Salida completa de la verificacion portable",
            "Los pasos opcionales tienen estado separado",
        ),
        "modelo_formal": (
            "python verification/submission_atomicity/modelo_estados.py",
            "IMPLEMENTADO Y EJECUTADO",
            "Exploracion exhaustiva del modelo acotado",
            "No es una prueba formal del codigo Python",
        ),
        "sql": (
            "ejecutar consultas sobre una base de prueba migrada",
            "CONFIGURADO, NO VALIDADO",
            "Consultas de inconsistencias persistentes",
            "No se ejecutaron sobre PostgreSQL local",
        ),
        "entorno": (
            "python scripts/capturar_baseline.py",
            "IMPLEMENTADO Y EJECUTADO",
            "Versiones y procedencia del entorno",
            "Foto temporal de una maquina",
        ),
        "informes": (
            "inspeccion documental",
            "IMPLEMENTADO Y EJECUTADO",
            "Trazabilidad, limites y reproduccion",
            "Las valoraciones academicas son orientativas",
        ),
    }
    return mapping.get(
        prefix,
        (
            "python scripts/generar_paquete_evidencias.py",
            "IMPLEMENTADO Y EJECUTADO",
            "Indice o metadato del paquete",
            "Describe las evidencias incluidas, no amplia su alcance",
        ),
    )


def write_package_documents(staging: Path, commit: str) -> None:
    (staging / "00_INDICE.md").write_text(
        "# Indice del paquete de evidencias\n\n"
        f"Commit base: `{commit}`.\n\n"
        "El contenido se organiza por propiedad. Consulte primero "
        "`01_RESUMEN_EJECUTIVO.md`, `02_MATRIZ_TRAZABILIDAD.csv` y "
        "`03_MANUAL_EVIDENCIAS_TFG.md`. Los directorios PostgreSQL y Docker "
        "conservan el bloqueo observado; no contienen resultados simulados. "
        "`EVIDENCE_MANIFEST.json` describe cada fichero y `SHA256SUMS.txt` "
        "permite verificarlo.\n",
        encoding="utf-8",
    )
    (staging / "01_RESUMEN_EJECUTIVO.md").write_text(
        "# Resumen ejecutivo de evidencias\n\n"
        "Se corrigieron la unidad transaccional del envio, la carrera de inicio, "
        "la recuperacion de borradores, el cierre seguro de produccion y el "
        "tratamiento de evidencias. Se ejecutaron las pruebas portables, el "
        "recorrido Brave con medios sinteticos, la auditoria de dependencias y "
        "un modelo de estados acotado.\n\n"
        "PostgreSQL real, construccion Docker y campana adversaria quedaron "
        "preparados pero bloqueados por ausencia de daemon. La CI quedo "
        "configurada, no ejecutada. No se afirma aislamiento absoluto, "
        "identidad institucional ni cumplimiento juridico.\n",
        encoding="utf-8",
    )


def populate(staging: Path, source: Path, commit: str) -> None:
    for directory in REQUIRED_DIRECTORIES:
        (staging / directory).mkdir(parents=True, exist_ok=True)

    copy_tree(source / "baseline", staging / "baseline")
    copy_tree(source / "atomicidad", staging / "atomicidad")
    copy_tree(source / "concurrencia", staging / "concurrencia")
    copy_tree(source / "cobertura", staging / "cobertura")
    copy_tree(source / "navegador", staging / "navegador")
    copy_tree(source / "navegador" / "capturas", staging / "capturas")
    copy_tree(source / "seguridad", staging / "seguridad")
    copy_tree(source / "compose", staging / "entorno" / "compose")
    copy_tree(source / "verificacion", staging / "logs")
    copy_tree(source / "limpieza", staging / "informes" / "limpieza")
    copy_tree(source / "modelo_formal", staging / "modelo_formal" / "resultados")
    copy_tree(
        ROOT / "verification" / "submission_atomicity",
        staging / "modelo_formal" / "fuentes",
    )
    copy_tree(ROOT / "docs" / "figuras_simplificadas", staging / "diagramas")
    copy_tree(ROOT / "docs" / "seguridad", staging / "seguridad" / "documentos")
    copy_tree(ROOT / "docs" / "auditoria", staging / "informes" / "auditoria")

    for name in ("Dockerfile.backend", "Dockerfile.sandbox", "docker-compose.yml"):
        copy_file(ROOT / name, staging / "ci" / name)
    copy_file(
        ROOT / "docker-compose.postgresql.yml",
        staging / "ci" / "docker-compose.postgresql.yml",
    )
    copy_file(ROOT / ".github" / "workflows" / "ci.yml", staging / "ci" / "ci.yml")
    copy_file(ROOT / "requirements.txt", staging / "entorno" / "requirements.txt")
    copy_file(
        ROOT / "requirements-dev.txt", staging / "entorno" / "requirements-dev.txt"
    )
    copy_file(
        ROOT / "docs" / "auditoria" / "ESTADO_INFRAESTRUCTURA.md",
        staging / "postgresql" / "ESTADO_INFRAESTRUCTURA.md",
    )
    copy_file(
        ROOT / "docs" / "auditoria" / "ESTADO_INFRAESTRUCTURA.md",
        staging / "docker" / "ESTADO_INFRAESTRUCTURA.md",
    )
    copy_file(
        ROOT / "docs" / "auditoria" / "ESTADO_INFRAESTRUCTURA.md",
        staging / "sandbox_adversarial" / "ESTADO_INFRAESTRUCTURA.md",
    )
    copy_file(
        ROOT / "docs" / "auditoria" / "CONSULTAS_INTEGRIDAD.sql",
        staging / "sql" / "CONSULTAS_INTEGRIDAD.sql",
    )
    copy_file(
        ROOT / "docs" / "auditoria" / "MATRIZ_TRAZABILIDAD.csv",
        staging / "02_MATRIZ_TRAZABILIDAD.csv",
    )
    copy_file(
        ROOT / "MANUAL_EVIDENCIAS_TFG.md",
        staging / "03_MANUAL_EVIDENCIAS_TFG.md",
    )
    (staging / "informes" / "INFORME_FINAL_UBICACION.md").write_text(
        "# Informe final y hash del ZIP\n\n"
        "El informe final se conserva junto al repositorio como "
        "`INFORME_FINAL_ENDURECIMIENTO.md`. No se inserta en este ZIP porque "
        "publica el SHA-256 y el tamano del propio archivo: incluirlo produciria "
        "una referencia circular y un digest interno obsoleto. El hash exacto "
        "esta en el fichero externo `.zip.sha256` generado y verificado por el "
        "mismo script.\n",
        encoding="utf-8",
    )
    multimedia_sources = (
        source / "navegador" / "resultado_navegador.json",
        source / "navegador" / "capturas" / "18_evento_y_evidencia_sintetica.png",
    )
    for item in multimedia_sources:
        if item.exists():
            copy_file(item, staging / "multimedia" / item.name)
    write_package_documents(staging, commit)


def write_manifest(staging: Path) -> None:
    generated = datetime.now(UTC).isoformat()
    entries = []
    for item in sorted(staging.rglob("*")):
        if not item.is_file() or item.name in {
            "EVIDENCE_MANIFEST.json",
            "SHA256SUMS.txt",
        }:
            continue
        relative = item.relative_to(staging).as_posix()
        command, status, property_name, limitations = metadata(relative)
        entries.append(
            {
                "ruta": relative,
                "sha256": sha256(item),
                "fecha_utc": datetime.fromtimestamp(
                    item.stat().st_mtime, UTC
                ).isoformat(),
                "comando": command,
                "estado": status,
                "propiedad": property_name,
                "limitaciones": limitations,
            }
        )
    manifest = {
        "esquema": 1,
        "generado_en_utc": generated,
        "entradas": entries,
    }
    (staging / "EVIDENCE_MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    checksum_lines = []
    for item in sorted(staging.rglob("*")):
        if item.is_file() and item.name != "SHA256SUMS.txt":
            checksum_lines.append(
                f"{sha256(item)}  {item.relative_to(staging).as_posix()}"
            )
    (staging / "SHA256SUMS.txt").write_text(
        "\n".join(checksum_lines) + "\n", encoding="utf-8"
    )


def create_zip(staging: Path, archive: Path) -> None:
    with zipfile.ZipFile(
        archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as package:
        for item in sorted(staging.rglob("*")):
            if item.is_file():
                package.write(item, item.relative_to(staging).as_posix())


def verify_zip(archive: Path) -> tuple[int, int]:
    with zipfile.ZipFile(archive) as package:
        corrupt = package.testzip()
        if corrupt:
            raise RuntimeError(f"Entrada ZIP corrupta: {corrupt}")
        names = set(package.namelist())
        required = {
            "00_INDICE.md",
            "01_RESUMEN_EJECUTIVO.md",
            "02_MATRIZ_TRAZABILIDAD.csv",
            "03_MANUAL_EVIDENCIAS_TFG.md",
            "EVIDENCE_MANIFEST.json",
            "SHA256SUMS.txt",
        }
        missing = required - names
        if missing:
            raise RuntimeError(f"Faltan entradas obligatorias: {sorted(missing)}")
        checksum_text = package.read("SHA256SUMS.txt").decode("utf-8")
        checked = 0
        for line in checksum_text.splitlines():
            expected, name = line.split("  ", maxsplit=1)
            actual = hashlib.sha256(package.read(name)).hexdigest()
            if actual != expected:
                raise RuntimeError(f"Hash interno incorrecto: {name}")
            checked += 1
        return len(names), checked


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Genera un ZIP autocontenido y verifica todos sus hashes."
    )
    parser.add_argument(
        "--conservar-directorio",
        action="store_true",
        help="Conserva tambien la carpeta de preparacion junto al ZIP.",
    )
    args = parser.parse_args()
    commit, short_commit = commit_base()
    source = EVIDENCE_ROOT / short_commit
    if not source.exists():
        raise SystemExit(f"No existe la evidencia base: {source}")
    staging = EVIDENCE_ROOT / f"paquete_{short_commit}"
    archive = EVIDENCE_ROOT / f"tfg_evidencias_{short_commit}.zip"
    if staging.exists():
        shutil.rmtree(staging)
    if archive.exists():
        archive.unlink()
    staging.mkdir(parents=True)
    populate(staging, source, commit)
    write_manifest(staging)
    create_zip(staging, archive)
    entries, hashes = verify_zip(archive)
    digest = sha256(archive)
    sidecar = archive.with_suffix(".zip.sha256")
    sidecar.write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
    summary = {
        "generado_en_utc": datetime.now(UTC).isoformat(),
        "commit_base": commit,
        "zip": str(archive.relative_to(ROOT)),
        "sha256": digest,
        "tamano_bytes": archive.stat().st_size,
        "entradas_zip": entries,
        "hashes_internos_verificados": hashes,
        "zip_integro": True,
    }
    (EVIDENCE_ROOT / f"tfg_evidencias_{short_commit}.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if not args.conservar_directorio:
        shutil.rmtree(staging)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
