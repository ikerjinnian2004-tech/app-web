import subprocess
import sys
import time

import pytest

from backend.sandbox.policy import (
    LONGITUD_MAXIMA_CODIGO,
    clasificar_error,
    validar_fragmento,
)
from backend.sandbox.runner_subprocess import ejecutar_codigo, ejecutar_codigo_interno


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
    es_valido, motivo = validar_fragmento(codigo)
    assert es_valido is False
    assert motivo


def test_syntax_error_se_identifica_en_la_politica() -> None:
    es_valido, motivo = validar_fragmento("def f(:\n    pass")
    assert es_valido is False
    assert motivo.startswith("SyntaxError:")


def test_timeout_en_bucle_infinito() -> None:
    inicio = time.time()
    resultado = ejecutar_codigo("while True: pass", 1, 5000)
    assert resultado["timed_out"] is True
    assert time.time() - inicio <= 6


def test_salida_se_recorta() -> None:
    resultado = ejecutar_codigo("print('x' * 100)", 1, 10)
    assert len(str(resultado["stdout"])) == 10


def test_codigo_demasiado_largo_se_rechaza() -> None:
    resultado = ejecutar_codigo("a" * (LONGITUD_MAXIMA_CODIGO + 1), 1, 5000)
    assert "demasiado largo" in str(resultado["stderr"])


def test_runner_interno_crea_un_subproceso(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[list[str], dict]] = []

    def fake_run(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, "ok", "")

    monkeypatch.setattr("backend.sandbox.runner_subprocess.subprocess.run", fake_run)
    resultado = ejecutar_codigo_interno("print('ok')", 1, 5000)

    assert calls
    assert calls[0][0][0] == sys.executable
    assert resultado["returncode"] == 0


def test_clasificacion_de_errores_publicos() -> None:
    assert clasificar_error(1, "SyntaxError: invalid syntax") == "SYNTAX_ERROR"
    assert clasificar_error(-9, "") == "TIMEOUT"
    assert clasificar_error(1, "Llamada no permitida: open.") == "SECURITY_BLOCKED"
    assert clasificar_error(1, "ValueError: fallo") == "RUNTIME_ERROR"
