from __future__ import annotations

import os

import docker
import pytest

from backend.config import get_settings
from backend.sandbox.runner_docker import (
    comprobar_disponibilidad_docker,
    ejecutar_codigo_interno_docker,
)


pytestmark = pytest.mark.docker_real
settings = get_settings()


@pytest.fixture(scope="module", autouse=True)
def daemon_e_imagen_disponibles() -> None:
    if os.environ.get("RUN_DOCKER_SANDBOX_TESTS") != "1":
        pytest.skip("RUN_DOCKER_SANDBOX_TESTS=1 no está definido.")
    disponible, detalle = comprobar_disponibilidad_docker()
    if not disponible:
        pytest.fail(detalle)


def ejecutar(codigo: str, timeout: int = 3, salida: int = 5000):
    return ejecutar_codigo_interno_docker(codigo, timeout, salida)


def test_raiz_de_solo_lectura_bloquea_escritura() -> None:
    resultado = ejecutar("open('/fuera-tmpfs', 'w').write('no')")
    assert resultado["returncode"] != 0
    assert resultado["limpieza_completada"] is True


def test_red_desactivada_bloquea_conexion_tcp_y_dns() -> None:
    resultado = ejecutar(
        "import socket; socket.create_connection(('example.com', 443), timeout=1)"
    )
    assert resultado["returncode"] != 0
    assert resultado["motivo_terminacion"] in {"proceso", "timeout"}


def test_tmpfs_no_persiste_entre_ejecuciones() -> None:
    primero = ejecutar("open('/tmp/canario', 'w').write('primero'); print('creado')")
    segundo = ejecutar("import os; print(os.path.exists('/tmp/canario'))")
    assert primero["returncode"] == 0
    assert str(segundo["stdout"]).strip() == "False"


def test_entorno_no_hereda_secretos_del_host() -> None:
    resultado = ejecutar("import os; print('\\n'.join(sorted(os.environ)))")
    salida = str(resultado["stdout"]).upper()
    assert resultado["returncode"] == 0
    assert "SECRET_KEY" not in salida
    assert "IDENTITY_HMAC_KEY" not in salida
    assert "TOKEN" not in salida


def test_timeout_fuerza_terminacion_y_limpieza() -> None:
    resultado = ejecutar("while True: pass", timeout=1)
    assert resultado["timed_out"] is True
    assert resultado["motivo_terminacion"] == "timeout"
    assert resultado["limpieza_completada"] is True


def test_salida_se_trunca_y_stdout_se_separa_de_stderr() -> None:
    resultado = ejecutar(
        "import sys; print('o' * 200); print('e' * 200, file=sys.stderr)",
        salida=50,
    )
    assert resultado["returncode"] == 0
    assert str(resultado["stdout"]) == "o" * 50
    assert str(resultado["stderr"]) == "e" * 50
    assert resultado["stdout_truncado"] is True
    assert resultado["stderr_truncado"] is True


@pytest.mark.sandbox_adversarial
def test_limite_de_procesos_en_contenedor() -> None:
    if os.environ.get("ALLOW_DESTRUCTIVE_SANDBOX_TESTS") != "1":
        pytest.skip("La campaña agresiva requiere ALLOW_DESTRUCTIVE_SANDBOX_TESTS=1.")
    codigo = """
import os
import time

children = []
try:
    for _ in range(200):
        pid = os.fork()
        if pid == 0:
            time.sleep(10)
            os._exit(0)
        children.append(pid)
except OSError:
    print(f'limite_aplicado:{len(children)}')
    raise SystemExit(0)
raise SystemExit('el limite de procesos no se aplico')
"""
    resultado = ejecutar(codigo, timeout=5)
    assert resultado["returncode"] == 0
    assert "limite_aplicado:" in str(resultado["stdout"])


def test_no_quedan_contenedores_residuales() -> None:
    cliente = docker.from_env()
    try:
        residuales = cliente.containers.list(
            all=True, filters={"label": "app=evaluador-tfg"}
        )
    finally:
        cliente.close()
    assert residuales == []
