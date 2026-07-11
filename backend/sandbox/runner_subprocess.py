from __future__ import annotations

import subprocess
import sys
import tempfile
from textwrap import dedent

from backend.config import get_settings
from backend.sandbox.policy import check_static

settings = get_settings()

try:
    import resource
except ImportError:  # pragma: no cover - Windows no expone este módulo.
    resource = None


def _truncate(text: str, max_output: int) -> str:
    """Recorta stdout o stderr al tamaño máximo permitido."""
    return text[:max_output]


def _preexec_limits() -> None:
    """Aplica límites modestos de CPU y memoria en sistemas Unix."""
    if resource is None:
        return

    mem_bytes = settings.sandbox_mem_limit_mb * 1024 * 1024
    cpu_seconds = max(1, int(settings.sandbox_timeout_seconds))
    resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 1))


def _wrap_code(codigo: str) -> str:
    """Inyecta un preámbulo mínimo para bloquear open() en desarrollo."""
    prelude = dedent(
        """
        import builtins as __safe_builtins__

        def __blocked_open__(*args, **kwargs):
            raise PermissionError("open() está bloqueado en el sandbox de desarrollo")

        __safe_builtins__.open = __blocked_open__
        """
    )
    return f"{prelude}\n{codigo}"


def _run_code(
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

    try:
        compile(codigo, "<codigo-alumno>", "exec")
    except SyntaxError as exc:
        return {
            "stdout": "",
            "stderr": f"SyntaxError: {exc.msg}",
            "returncode": 1,
            "timed_out": False,
        }

    # Lanzamos Python en modo aislado (-I) para reducir herencia del entorno.
    # Aun así, seguimos hablando de un runner de desarrollo, no de producción.
    entorno_minimo = {"PYTHONIOENCODING": "utf-8"}
    comando = [sys.executable, "-I", "-c", _wrap_code(codigo)]

    try:
        with tempfile.TemporaryDirectory(prefix="sandbox-dev-") as temp_dir:
            result = subprocess.run(
                comando,
                capture_output=True,
                timeout=timeout,
                text=True,
                check=False,
                cwd=temp_dir,
                env=entorno_minimo,
                preexec_fn=_preexec_limits if resource is not None else None,
            )
    except subprocess.TimeoutExpired as exc:
        return {
            "stdout": _truncate(exc.stdout or "", max_output),
            "stderr": _truncate(exc.stderr or "", max_output),
            "returncode": -9,
            "timed_out": True,
        }

    return {
        "stdout": _truncate(result.stdout, max_output),
        "stderr": _truncate(result.stderr, max_output),
        "returncode": int(result.returncode),
        "timed_out": False,
    }


def run_code(codigo: str, timeout: int, max_output: int) -> dict[str, object]:
    """Ejecuta código de alumno en un subproceso local de desarrollo."""
    return _run_code(codigo, timeout, max_output, validate_static=True)


def run_internal_code(codigo: str, timeout: int, max_output: int) -> dict[str, object]:
    """Ejecuta el script generado por el corrector en un subproceso local."""
    return _run_code(codigo, timeout, max_output, validate_static=False)
