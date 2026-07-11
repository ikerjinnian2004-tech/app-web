import subprocess
import sys
import time

import pytest

from backend.sandbox.policy import MAX_CODE_LENGTH, check_static, classify_error
from backend.sandbox.runner_subprocess import run_code, run_internal_code


@pytest.mark.parametrize(
    "codigo",
    [
        "import os",
        "import os.path",
        "from os import system",
        '__import__("os")',
        'eval("1 + 1")',
        'exec("print(1)")',
        'open("x.txt", "w")',
        "object.__subclasses__()",
        'getattr(object, "__subclasses__")()',
    ],
)
def test_ast_bloquea_operaciones_peligrosas(codigo: str) -> None:
    ok, motivo = check_static(codigo)
    assert ok is False
    assert motivo


def test_syntax_error_se_identifica_en_la_politica() -> None:
    ok, motivo = check_static("def f(:\n    pass")
    assert ok is False
    assert motivo.startswith("SyntaxError:")


def test_timeout_en_bucle_infinito() -> None:
    start = time.time()
    result = run_code("while True: pass", 1, 5000)
    assert result["timed_out"] is True
    assert time.time() - start <= 6


def test_salida_se_recorta() -> None:
    result = run_code("print('x' * 100)", 1, 10)
    assert len(str(result["stdout"])) == 10


def test_codigo_demasiado_largo_se_rechaza() -> None:
    result = run_code("a" * (MAX_CODE_LENGTH + 1), 1, 5000)
    assert "demasiado largo" in str(result["stderr"])


def test_runner_interno_crea_un_subproceso(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[list[str], dict]] = []

    def fake_run(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, "ok", "")

    monkeypatch.setattr("backend.sandbox.runner_subprocess.subprocess.run", fake_run)
    result = run_internal_code("print('ok')", 1, 5000)

    assert calls
    assert calls[0][0][0] == sys.executable
    assert result["returncode"] == 0


def test_clasificacion_de_errores_publicos() -> None:
    assert classify_error(1, "SyntaxError: invalid syntax") == "SYNTAX_ERROR"
    assert classify_error(-9, "") == "TIMEOUT"
    assert classify_error(1, "Llamada no permitida: open.") == "SECURITY_BLOCKED"
    assert classify_error(1, "ValueError: fallo") == "RUNTIME_ERROR"
