from __future__ import annotations

import subprocess
import sys
import tempfile
from textwrap import dedent

from backend.config import get_settings
from backend.sandbox.policy import validar_fragmento

configuracion = get_settings()
INTERPRETE_SANDBOX = getattr(sys, "_base_executable", sys.executable) or sys.executable

try:
    import resource
except ImportError:  # pragma: no cover - Windows no expone este módulo.
    resource = None


def _recortar(texto: str, salida_maxima: int) -> str:
    return texto[:salida_maxima]


def _aplicar_limites_preexec() -> None:
    if resource is None:
        return

    memoria_bytes = configuracion.sandbox_mem_limit_mb * 1024 * 1024
    segundos_cpu = max(1, int(configuracion.sandbox_timeout_seconds))
    resource.setrlimit(resource.RLIMIT_AS, (memoria_bytes, memoria_bytes))
    resource.setrlimit(resource.RLIMIT_CPU, (segundos_cpu, segundos_cpu + 1))


def _envolver_codigo(codigo: str) -> str:
    preambulo = dedent(
        """
        import builtins as __safe_builtins__

        def __blocked_open__(*args, **kwargs):
            raise PermissionError("open() está bloqueado en el sandbox de desarrollo")

        __safe_builtins__.open = __blocked_open__
        """
    )
    return f"{preambulo}\n{codigo}"


def _ejecutar_codigo(
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
    comando = [INTERPRETE_SANDBOX, "-I", "-c", _envolver_codigo(codigo)]

    try:
        with tempfile.TemporaryDirectory(prefix="sandbox-dev-") as directorio_temporal:
            resultado = subprocess.run(
                comando,
                capture_output=True,
                timeout=timeout,
                text=True,
                check=False,
                cwd=directorio_temporal,
                env=entorno_minimo,
                preexec_fn=_aplicar_limites_preexec if resource is not None else None,
            )
    except subprocess.TimeoutExpired as exc:
        return {
            "stdout": _recortar(exc.stdout or "", salida_maxima),
            "stderr": _recortar(exc.stderr or "", salida_maxima),
            "returncode": -9,
            "timed_out": True,
        }

    return {
        "stdout": _recortar(resultado.stdout, salida_maxima),
        "stderr": _recortar(resultado.stderr, salida_maxima),
        "returncode": int(resultado.returncode),
        "timed_out": False,
    }


def ejecutar_codigo(codigo: str, timeout: int, max_output: int) -> dict[str, object]:
    return _ejecutar_codigo(codigo, timeout, max_output, validar_estaticamente=True)


def ejecutar_codigo_interno(
    codigo: str, timeout: int, max_output: int
) -> dict[str, object]:
    return _ejecutar_codigo(codigo, timeout, max_output, validar_estaticamente=False)


run_code = ejecutar_codigo
run_internal_code = ejecutar_codigo_interno
