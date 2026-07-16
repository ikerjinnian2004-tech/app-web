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


def test_ensamblar_codigo_admite_varios_huecos() -> None:
    codigo = ensamblar_codigo(
        "resultado = ([BLANK], [BLANK])",
        ["a + b", "a * b"],
    )
    assert codigo == "resultado = (a + b, a * b)"


def test_plantilla_requiere_al_menos_un_hueco() -> None:
    with pytest.raises(ValueError, match="al menos un marcador"):
        validar_plantilla("sin huecos")


def test_numero_de_respuestas_debe_coincidir_con_los_huecos() -> None:
    with pytest.raises(ValueError, match="requiere 2 respuestas"):
        ensamblar_codigo("[BLANK] + [BLANK]", ["a"])


def test_respuesta_demasiado_larga_se_rechaza() -> None:
    with pytest.raises(ValueError, match="supera"):
        ensamblar_codigo("a = [BLANK]", "a" * (LONGITUD_MAXIMA_RESPUESTA + 1))
