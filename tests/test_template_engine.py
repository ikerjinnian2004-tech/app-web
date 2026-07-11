import pytest

from backend.template_engine import (
    LONGITUD_MAXIMA_RESPUESTA,
    contar_huecos,
    dividir_plantilla,
    ensamblar_codigo,
    validar_plantilla,
)


def test_dividir_plantilla_devuelve_fragmentos_fijos() -> None:
    assert dividir_plantilla("a = [BLANK]") == ["a = ", ""]


def test_contar_huecos_cuenta_bien() -> None:
    assert contar_huecos("a[BLANK]b[BLANK]c") == 2


def test_ensamblar_codigo_sustituye_el_unico_hueco() -> None:
    assert ensamblar_codigo("a = [BLANK]", "5") == "a = 5"


def test_ensamblar_codigo_respeta_indentacion() -> None:
    assert (
        ensamblar_codigo("def f():\n    return [BLANK]", "x + 1")
        == "def f():\n    return x + 1"
    )


@pytest.mark.parametrize("plantilla", ["sin huecos", "x = [BLANK] + [BLANK]"])
def test_plantilla_requiere_un_solo_hueco(plantilla: str) -> None:
    with pytest.raises(ValueError, match="exactamente un marcador"):
        validar_plantilla(plantilla)


def test_respuesta_demasiado_larga_se_rechaza() -> None:
    with pytest.raises(ValueError, match="supera"):
        ensamblar_codigo(
            "a = [BLANK]", "a" * (LONGITUD_MAXIMA_RESPUESTA + 1)
        )
