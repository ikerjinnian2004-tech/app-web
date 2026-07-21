from __future__ import annotations

import time
from uuid import uuid4

import docker
from docker.errors import ContainerError, DockerException
from requests.exceptions import ReadTimeout

from backend.config import get_settings
from backend.sandbox.policy import validar_fragmento

configuracion = get_settings()


def _decodificar_logs(logs: bytes, salida_maxima: int) -> tuple[str, bool]:
    texto = logs.decode("utf-8", errors="replace")
    return texto[:salida_maxima], len(texto) > salida_maxima


def comprobar_disponibilidad_docker() -> tuple[bool, str]:
    cliente = None
    try:
        cliente = docker.from_env()
        cliente.ping()
        cliente.images.get(configuracion.sandbox_image)
        return True, f"Docker e imagen {configuracion.sandbox_image} disponibles."
    except DockerException as exc:
        return False, f"Docker o la imagen del sandbox no están disponibles: {exc}"
    finally:
        if cliente is not None:
            cliente.close()


def opciones_contenedor(ejecucion_id: str) -> dict[str, object]:
    return {
        "network_mode": "none",
        "read_only": True,
        "cap_drop": ["ALL"],
        "security_opt": ["no-new-privileges:true"],
        "mem_limit": f"{configuracion.sandbox_mem_limit_mb}m",
        "nano_cpus": int(configuracion.sandbox_cpu * 1e9),
        "pids_limit": configuracion.sandbox_pids_limit,
        "remove": False,
        "stdout": True,
        "stderr": True,
        "user": "65534:65534",
        "working_dir": "/tmp",
        "tmpfs": {"/tmp": "rw,noexec,nosuid,size=16m"},
        "environment": {
            "PYTHONIOENCODING": "utf-8",
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        "init": True,
        "stdin_open": False,
        "tty": False,
        "memswap_limit": f"{configuracion.sandbox_mem_limit_mb}m",
        "ulimits": [docker.types.Ulimit(name="nofile", soft=64, hard=64)],
        "log_config": docker.types.LogConfig(
            type="local", config={"max-size": "1m", "max-file": "1"}
        ),
        "labels": {"app": "evaluador-tfg", "ejecucion_id": ejecucion_id},
    }


def _ejecutar_codigo_docker(
    codigo: str, timeout: int, salida_maxima: int, validar_estaticamente: bool
) -> dict[str, object]:
    inicio = time.monotonic()
    ejecucion_id = str(uuid4())
    if validar_estaticamente:
        es_seguro, motivo = validar_fragmento(codigo)
        if not es_seguro:
            return {
                "ejecucion_id": ejecucion_id,
                "stdout": "",
                "stderr": motivo,
                "returncode": 1,
                "timed_out": False,
                "motivo_terminacion": "politica_ast",
                "duracion_ms": round((time.monotonic() - inicio) * 1000, 3),
                "imagen": configuracion.sandbox_image,
                "contenedor_id": None,
                "limpieza_completada": True,
                "stdout_truncado": False,
                "stderr_truncado": False,
            }

    cliente = None
    contenedor = None
    resultado: dict[str, object] = {
        "ejecucion_id": ejecucion_id,
        "stdout": "",
        "stderr": "Fallo de infraestructura del sandbox Docker.",
        "returncode": 1,
        "timed_out": False,
        "motivo_terminacion": "infraestructura",
        "duracion_ms": 0.0,
        "imagen": configuracion.sandbox_image,
        "contenedor_id": None,
        "limpieza_completada": False,
        "stdout_truncado": False,
        "stderr_truncado": False,
        "oom_killed": False,
    }
    try:
        cliente = docker.from_env()
        contenedor = cliente.containers.run(
            configuracion.sandbox_image,
            command=["python3", "-I", "-c", codigo],
            detach=True,
            **opciones_contenedor(ejecucion_id),
        )
        resultado["contenedor_id"] = getattr(contenedor, "id", None)

        try:
            resultado_espera = contenedor.wait(timeout=timeout)
            codigo_retorno = int(resultado_espera.get("StatusCode", 1))
            stdout, stdout_truncado = _decodificar_logs(
                contenedor.logs(stdout=True, stderr=False), salida_maxima
            )
            stderr, stderr_truncado = _decodificar_logs(
                contenedor.logs(stdout=False, stderr=True), salida_maxima
            )
            if hasattr(contenedor, "reload"):
                contenedor.reload()
                estado = getattr(contenedor, "attrs", {}).get("State", {})
                resultado["oom_killed"] = bool(estado.get("OOMKilled", False))
            resultado.update(
                {
                    "stdout": stdout,
                    "stderr": stderr,
                    "returncode": codigo_retorno,
                    "timed_out": False,
                    "motivo_terminacion": (
                        "oom"
                        if resultado["oom_killed"]
                        else ("completada" if codigo_retorno == 0 else "proceso")
                    ),
                    "stdout_truncado": stdout_truncado,
                    "stderr_truncado": stderr_truncado,
                }
            )
        except ReadTimeout:
            resultado.update(
                {
                    "stderr": "Tiempo de ejecución agotado en Docker.",
                    "returncode": -9,
                    "timed_out": True,
                    "motivo_terminacion": "timeout",
                }
            )
        except ContainerError as exc:
            stderr, stderr_truncado = _decodificar_logs(
                exc.stderr or b"", salida_maxima
            )
            resultado.update(
                {
                    "stderr": stderr,
                    "returncode": int(exc.exit_status),
                    "motivo_terminacion": "proceso",
                    "stderr_truncado": stderr_truncado,
                }
            )
    except DockerException as exc:
        resultado["stderr"] = (
            "Docker no disponible o imagen ausente. "
            f"Revisa el daemon y {configuracion.sandbox_image}: {exc}"
        )
    finally:
        if contenedor is not None:
            try:
                contenedor.remove(force=True)
                resultado["limpieza_completada"] = True
            except DockerException as exc:
                resultado["stderr"] = (
                    f"{resultado['stderr']} Error al limpiar el contenedor: {exc}"
                ).strip()
        if cliente is not None:
            cliente.close()
        resultado["duracion_ms"] = round((time.monotonic() - inicio) * 1000, 3)
    return resultado


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
