from pathlib import Path


def test_script_de_navegador_conserva_medios_sinteticos() -> None:
    contenido = Path("scripts/capturar_recorrido_navegador.py").read_text(
        encoding="utf-8"
    )
    assert "MEDIA_SINTETICA" in contenido
    assert "alumna.demo@alu.uclm.es" in contenido
    assert "getDisplayMedia" in contenido
    assert "1440" in contenido and "900" in contenido
