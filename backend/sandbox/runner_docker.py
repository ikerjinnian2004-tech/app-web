from __future__ import annotations

import docker
from docker.errors import ContainerError, DockerException
from requests.exceptions import ReadTimeout

from backend.config import get_settings
from backend.sandbox.policy import validar_fragmento

configuracion = get_settings()


def _separar_logs(logs: bytes, salida_maxima: int) -> tuple[str, str]:
    texto = logs.decode("utf-8", errors="replace")[:salida_maxima]
    # Docker SDK, usado así, no distingue bien stdout y stderr.
    # Para el MVP nos basta con no perder el contenido principal.
    return texto, ""


def _ejecutar_codigo_docker(
    codigo: str, timeout: int, salida_maxima: int, validar_estaticamente: bool
) -> dict[str, object]:
    if validar_estaticamente:
        es_seguro, motivo = validar_fragmento(codigo)
        if not es_seguro:
            return {
                "stdout": "",
                "stderr": motivo,
                "returncode": 1,
                "timed_out": False,
            }

    cliente = None
    contenedor = None
    try:
        cliente = docker.from_env()
        contenedor = cliente.containers.run(
            configuracion.sandbox_image,
            command=["python3", "-I", "-c", codigo],
            detach=True,
            network_mode="none",
            read_only=True,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges:true"],
            mem_limit=f"{configuracion.sandbox_mem_limit_mb}m",
            nano_cpus=int(configuracion.sandbox_cpu * 1e9),
            pids_limit=configuracion.sandbox_pids_limit,
            remove=False,
            stdout=True,
            stderr=True,
            user="65534:65534",
            working_dir="/tmp",
            tmpfs={"/tmp": "rw,noexec,nosuid,size=16m"},
        )

        try:
            resultado_espera = contenedor.wait(timeout=timeout)
            codigo_retorno = int(resultado_espera.get("StatusCode", 1))
            stdout, stderr = _separar_logs(
                contenedor.logs(stdout=True, stderr=True), salida_maxima
            )
            return {
                "stdout": stdout,
                "stderr": stderr,
                "returncode": codigo_retorno,
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
            stderr = (exc.stderr or b"").decode("utf-8", errors="replace")[
                :salida_maxima
            ]
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
        if contenedor is not None:
            try:
                contenedor.remove(force=True)
            except DockerException:
                pass
        if cliente is not None:
            cliente.close()


def ejecutar_codigo_docker(
    codigo: str, timeout: int, max_output: int
) -> dict[str, object]:
    return _ejecutar_codigo_docker(
        codigo, timeout, max_output, validar_estaticamente=True
    )


def ejecutar_codigo_interno_docker(
    codigo: str, timeout: int, max_output: int
) -> dict[str, object]:
    return _ejecutar_codigo_docker(
        codigo, timeout, max_output, validar_estaticamente=False
    )


run_code_docker = ejecutar_codigo_docker
run_internal_code_docker = ejecutar_codigo_interno_docker
