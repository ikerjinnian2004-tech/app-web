from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import urlopen

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BRAVE = Path(r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe")
COMMIT = subprocess.check_output(
    ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True
).strip()
MEDIA_SINTETICA = """
(() => {
  const crearVideo = () => {
    const canvas = document.createElement('canvas');
    canvas.width = 640;
    canvas.height = 360;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#0f766e';
    ctx.fillRect(0, 0, 640, 360);
    ctx.fillStyle = 'white';
    ctx.font = '28px sans-serif';
    ctx.fillText('Medio sintetico TFG', 150, 180);
    return canvas.captureStream(10);
  };
  const crearAudio = () => {
    const contexto = new (window.AudioContext || window.webkitAudioContext)();
    const destino = contexto.createMediaStreamDestination();
    const oscilador = contexto.createOscillator();
    const ganancia = contexto.createGain();
    ganancia.gain.value = 0.01;
    oscilador.connect(ganancia).connect(destino);
    oscilador.start();
    return destino.stream;
  };
  const camara = () => new MediaStream([
    ...crearVideo().getVideoTracks(),
    ...crearAudio().getAudioTracks(),
  ]);
  const pantalla = () => crearVideo();
  Object.defineProperty(navigator, 'mediaDevices', {
    configurable: true,
    value: {
      getUserMedia: async () => camara(),
      getDisplayMedia: async () => pantalla(),
      enumerateDevices: async () => [{
        kind: 'videoinput',
        deviceId: 'camara-sintetica',
        label: 'Camara sintetica de pruebas',
      }],
    },
  });
})();
"""


def esperar_url(url: str, segundos: int = 30) -> None:
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        try:
            with urlopen(url, timeout=1) as response:  # noqa: S310
                if response.status < 500:
                    return
        except OSError:
            time.sleep(0.25)
    raise RuntimeError(f"El servicio no respondio a tiempo: {url}")


def entorno_demo() -> dict[str, str]:
    entorno = os.environ.copy()
    entorno.update(
        {
            "DATABASE_URL": "sqlite:///./tmp/e2e_navegador.db",
            "SECRET_KEY": "e2e-secret-key-minimo-32-caracteres-abcdefgh",
            "IDENTITY_HMAC_KEY": "e2e-hmac-key-minimo-32-caracteres-abcdefgh",
            "APP_ENVIRONMENT": "test",
            "DEMO_AUTH_ENABLED": "true",
            "SANDBOX_USE_DOCKER": "false",
            "ALLOWED_ORIGINS": "http://127.0.0.1:5500",
        }
    )
    return entorno


def opciones_proceso() -> dict[str, int]:
    if sys.platform == "win32":
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {}


def captura(page: Page, directorio: Path, numero: int, nombre: str) -> None:
    page.screenshot(
        path=directorio / f"{numero:02d}_{nombre}.png",
        full_page=True,
    )


def ejecutar_recorrido(
    page: Page, capturas: Path, red: list[dict[str, object]]
) -> None:
    page.on(
        "response",
        lambda response: red.append(
            {
                "metodo": response.request.method,
                "url": response.url,
                "status": response.status,
            }
        )
        if ":8000" in response.url
        else None,
    )
    page.goto("http://127.0.0.1:5500/index.html")
    page.wait_for_selector("#texto-consentimiento:not(:empty)")
    captura(page, capturas, 2, "acceso")
    page.locator("#acepta-grabacion").check()
    captura(page, capturas, 3, "consentimiento")
    page.locator("#correo").fill("alumna.demo@alu.uclm.es")
    page.locator("button[type=submit]").click()
    page.wait_for_selector("#formulario-examen")
    page.wait_for_selector("#estado-permisos[data-estado=ok]")
    captura(page, capturas, 4, "permisos_sinteticos")
    captura(page, capturas, 5, "inicio_examen")

    for indice, pregunta in enumerate(page.locator(".pregunta").all(), start=6):
        pregunta.scroll_into_view_if_needed()
        pregunta.screenshot(path=capturas / f"{indice:02d}_pregunta.png")

    for textarea in page.locator("textarea").all():
        textarea.fill(
            "a + b"
            if "hueco" in (textarea.get_attribute("id") or "")
            else "respuesta demo"
        )
    for selector in page.locator("select[data-pregunta-id]").all():
        selector.select_option(index=1)
    page.wait_for_selector(
        "#estado-autosalvado:not([data-estado=guardando])", timeout=15_000
    )
    page.wait_for_timeout(3000)
    captura(page, capturas, 10, "autosalvado")

    page.reload()
    page.wait_for_selector("#estado-autosalvado")
    page.wait_for_selector(
        "#contador-respuestas:has-text('4 respuestas')", timeout=15_000
    )
    captura(page, capturas, 11, "borradores_recuperados")
    page.locator("#reactivar-permisos").click()
    page.wait_for_selector("#estado-permisos[data-estado=ok]")
    page.evaluate("window.dispatchEvent(new Event('blur'))")
    page.wait_for_timeout(17_000)
    captura(page, capturas, 18, "evento_y_evidencia_sintetica")

    page.locator("#formulario-examen").evaluate(
        "formulario => formulario.requestSubmit()"
    )
    page.wait_for_selector("#resultado .nota-final", timeout=30_000)
    captura(page, capturas, 14, "resultado_desglose")

    page.goto("http://127.0.0.1:5500/index.html")
    page.locator("input[value=profesor]").check()
    page.locator("#correo").fill("docente.demo@uclm.es")
    page.locator("button[type=submit]").click()
    page.wait_for_selector("#entregas table", timeout=15_000)
    captura(page, capturas, 15, "panel_docente")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "artifacts" / "tfg-evidence" / COMMIT / "navegador",
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    capturas = args.output / "capturas"
    capturas.mkdir(exist_ok=True)
    (ROOT / "tmp").mkdir(exist_ok=True)
    entorno = entorno_demo()
    subprocess.run(
        [sys.executable, "scripts/reset_db.py"],
        cwd=ROOT,
        env=entorno,
        check=True,
        **opciones_proceso(),
    )
    subprocess.run(
        [sys.executable, "backend/data/seed_questions.py"],
        cwd=ROOT,
        env=entorno,
        check=True,
        **opciones_proceso(),
    )
    api_log = (args.output / "api.log").open("w", encoding="utf-8")
    frontend_log = (args.output / "frontend.log").open("w", encoding="utf-8")
    api = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app", "--port", "8000"],
        cwd=ROOT,
        env=entorno,
        stdout=api_log,
        stderr=subprocess.STDOUT,
        **opciones_proceso(),
    )
    frontend = subprocess.Popen(
        [sys.executable, "-m", "http.server", "5500", "--directory", "frontend"],
        cwd=ROOT,
        env=entorno,
        stdout=frontend_log,
        stderr=subprocess.STDOUT,
        **opciones_proceso(),
    )
    red: list[dict[str, object]] = []
    try:
        esperar_url("http://127.0.0.1:8000/health")
        esperar_url("http://127.0.0.1:5500/index.html")
        with sync_playwright() as playwright:
            opciones_lanzamiento: dict[str, object] = {
                "headless": True,
                "args": ["--autoplay-policy=no-user-gesture-required"],
            }
            if BRAVE.exists():
                opciones_lanzamiento["executable_path"] = str(BRAVE)
            navegador = playwright.chromium.launch(**opciones_lanzamiento)
            contexto = navegador.new_context(viewport={"width": 1440, "height": 900})
            contexto.add_init_script(MEDIA_SINTETICA)
            page = contexto.new_page()
            eventos_navegador: list[str] = []
            page.on(
                "console",
                lambda mensaje: eventos_navegador.append(
                    f"console.{mensaje.type}: {mensaje.text}"
                ),
            )
            page.on(
                "pageerror",
                lambda error: eventos_navegador.append(f"pageerror: {error}"),
            )
            try:
                ejecutar_recorrido(page, capturas, red)
            except Exception:
                page.screenshot(
                    path=args.output / "fallo_navegador.png", full_page=True
                )
                estado = page.locator("#estado-permisos")
                if estado.count():
                    eventos_navegador.append(
                        f"estado_permisos: {estado.inner_text()} / {estado.get_attribute('data-estado')}"
                    )
                raise
            finally:
                (args.output / "eventos_navegador.log").write_text(
                    "\n".join(eventos_navegador) + "\n", encoding="utf-8"
                )
            navegador.close()
    finally:
        for proceso in (frontend, api):
            proceso.terminate()
            try:
                proceso.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proceso.kill()
        api_log.close()
        frontend_log.close()
    informe = {
        "estado": "IMPLEMENTADO Y EJECUTADO",
        "fecha_utc": datetime.now(UTC).isoformat(),
        "commit_base": COMMIT,
        "navegador": str(BRAVE) if BRAVE.exists() else "Chromium de Playwright",
        "viewport": "1440x900",
        "multimedia": "flujos sinteticos inyectados; no captura de persona real",
        "red": red,
    }
    (args.output / "resultado_navegador.json").write_text(
        json.dumps(informe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(informe, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
