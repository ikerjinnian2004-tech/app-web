from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import docker

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from backend.config import get_settings  # noqa: E402
from backend.sandbox.runner_docker import (  # noqa: E402
    comprobar_disponibilidad_docker,
    opciones_contenedor,
)


def inspeccionar_control(cliente) -> dict[str, object]:  # noqa: ANN001
    settings = get_settings()
    ejecucion_id = f"inspeccion-{uuid4()}"
    contenedor = cliente.containers.create(
        settings.sandbox_image,
        command=["python3", "-I", "-c", "print('inspeccion')"],
        **opciones_contenedor(ejecucion_id),
    )
    try:
        contenedor.reload()
        host = contenedor.attrs.get("HostConfig", {})
        config = contenedor.attrs.get("Config", {})
        return {
            "contenedor_id": contenedor.id,
            "imagen": config.get("Image"),
            "usuario": config.get("User"),
            "directorio_trabajo": config.get("WorkingDir"),
            "network_mode": host.get("NetworkMode"),
            "read_only": host.get("ReadonlyRootfs"),
            "cap_drop": host.get("CapDrop"),
            "security_opt": host.get("SecurityOpt"),
            "memoria": host.get("Memory"),
            "memoria_swap": host.get("MemorySwap"),
            "nano_cpus": host.get("NanoCpus"),
            "pids_limit": host.get("PidsLimit"),
            "tmpfs": host.get("Tmpfs"),
            "binds": host.get("Binds"),
            "mounts": contenedor.attrs.get("Mounts", []),
            "ulimits": host.get("Ulimits"),
            "init": host.get("Init"),
            "log_config": host.get("LogConfig"),
        }
    finally:
        contenedor.remove(force=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inspecciona y ensaya el sandbox en contenedores Docker reales."
    )
    parser.add_argument("--agresivas", action="store_true")
    parser.add_argument(
        "--salida",
        type=Path,
        default=RAIZ / "artifacts" / "tfg-evidence" / "docker",
    )
    args = parser.parse_args()
    if os.environ.get("RUN_DOCKER_SANDBOX_TESTS") != "1":
        print("BLOQUEADO: define RUN_DOCKER_SANDBOX_TESTS=1 para ejecutar la campaña.")
        return 2
    if args.agresivas and os.environ.get("ALLOW_DESTRUCTIVE_SANDBOX_TESTS") != "1":
        print(
            "BLOQUEADO: --agresivas requiere ALLOW_DESTRUCTIVE_SANDBOX_TESTS=1 "
            "y un host desechable."
        )
        return 2

    disponible, detalle = comprobar_disponibilidad_docker()
    if not disponible:
        print("BLOQUEADO:", detalle)
        return 2

    args.salida.mkdir(parents=True, exist_ok=True)
    cliente = docker.from_env()
    try:
        info = cliente.info()
        imagen = cliente.images.get(get_settings().sandbox_image)
        residuales_antes = cliente.containers.list(
            all=True, filters={"label": "app=evaluador-tfg"}
        )
        inspeccion = inspeccionar_control(cliente)
        informe = {
            "generado_en_utc": datetime.now(UTC).isoformat(),
            "detalle_disponibilidad": detalle,
            "docker": {
                "server_version": info.get("ServerVersion"),
                "os_type": info.get("OSType"),
                "operating_system": info.get("OperatingSystem"),
                "security_options": info.get("SecurityOptions"),
            },
            "imagen": {
                "id": imagen.id,
                "repo_digests": imagen.attrs.get("RepoDigests", []),
                "repo_tags": imagen.attrs.get("RepoTags", []),
            },
            "residuales_antes": [item.id for item in residuales_antes],
            "configuracion_inspeccionada": inspeccion,
            "agresivas": args.agresivas,
        }
        (args.salida / "inspeccion_sandbox.json").write_text(
            json.dumps(informe, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    finally:
        cliente.close()

    entorno = os.environ.copy()
    comando = [
        sys.executable,
        "-m",
        "pytest",
        "tests/docker/test_sandbox_real.py",
        "-q",
        f"--junitxml={args.salida / 'sandbox-docker-junit.xml'}",
    ]
    resultado = subprocess.run(comando, cwd=RAIZ, env=entorno, check=False)
    return resultado.returncode


if __name__ == "__main__":
    raise SystemExit(main())
