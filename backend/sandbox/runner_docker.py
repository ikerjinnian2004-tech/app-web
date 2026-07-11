from __future__ import annotations

import docker
from docker.errors import ContainerError, DockerException
from requests.exceptions import ReadTimeout

from backend.config import get_settings
from backend.sandbox.policy import check_static

settings = get_settings()


def _split_logs(raw_logs: bytes, max_output: int) -> tuple[str, str]:
    """Convierte los logs del contenedor en texto recortado."""
    text = raw_logs.decode("utf-8", errors="replace")[:max_output]
    # Docker SDK, usado así, no distingue bien stdout y stderr.
    # Para el MVP nos basta con no perder el contenido principal.
    return text, ""


def _run_code_docker(
    codigo: str, timeout: int, max_output: int, validate_static: bool
) -> dict[str, object]:
    if validate_static:
        es_seguro, motivo = check_static(codigo)
        if not es_seguro:
            return {
                "stdout": "",
                "stderr": motivo,
                "returncode": 1,
                "timed_out": False,
            }

    client = None
    container = None
    try:
        client = docker.from_env()
        container = client.containers.run(
            settings.sandbox_image,
            command=["python3", "-I", "-c", codigo],
            detach=True,
            network_mode="none",
            read_only=True,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges:true"],
            mem_limit=f"{settings.sandbox_mem_limit_mb}m",
            nano_cpus=int(settings.sandbox_cpu * 1e9),
            pids_limit=settings.sandbox_pids_limit,
            remove=False,
            stdout=True,
            stderr=True,
            user="65534:65534",
            working_dir="/tmp",
            tmpfs={"/tmp": "rw,noexec,nosuid,size=16m"},
        )

        try:
            wait_result = container.wait(timeout=timeout)
            returncode = int(wait_result.get("StatusCode", 1))
            stdout, stderr = _split_logs(
                container.logs(stdout=True, stderr=True), max_output
            )
            return {
                "stdout": stdout,
                "stderr": stderr,
                "returncode": returncode,
                "timed_out": False,
            }
        except ReadTimeout:
            return {
                "stdout": "",
                "stderr": "Tiempo de ejecución agotado en Docker.",
                "returncode": -9,
                "timed_out": True,
            }
        except ContainerError as exc:
            stderr = (exc.stderr or b"").decode("utf-8", errors="replace")[:max_output]
            return {
                "stdout": "",
                "stderr": stderr,
                "returncode": int(exc.exit_status),
                "timed_out": False,
            }
    except DockerException:
        return {
            "stdout": "",
            "stderr": "Docker no disponible. Revisa el daemon o desactiva SANDBOX_USE_DOCKER.",
            "returncode": 1,
            "timed_out": False,
        }
    finally:
        # Aunque el contenedor sea efímero, limpiarlo explícitamente deja el flujo
        # más robusto y evita basura si algo falla a mitad de ejecución.
        if container is not None:
            try:
                container.remove(force=True)
            except DockerException:
                pass
        if client is not None:
            client.close()


def run_code_docker(codigo: str, timeout: int, max_output: int) -> dict[str, object]:
    """Ejecuta código de alumno en el contenedor Docker configurado."""
    return _run_code_docker(codigo, timeout, max_output, validate_static=True)


def run_internal_code_docker(
    codigo: str, timeout: int, max_output: int
) -> dict[str, object]:
    """Ejecuta el script generado por el corrector dentro de Docker."""
    return _run_code_docker(codigo, timeout, max_output, validate_static=False)
