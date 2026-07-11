import pytest

from backend.template_engine import (
    MAX_ANSWER_LENGTH,
    assemble_code,
    count_blanks,
    parse_template,
    validate_template,
)


def test_parse_template_devuelve_fragmentos_fijos() -> None:
    assert parse_template("a = [BLANK]") == ["a = ", ""]


def test_count_blanks_cuenta_bien() -> None:
    assert count_blanks("a[BLANK]b[BLANK]c") == 2


def test_assemble_code_sustituye_el_unico_blank() -> None:
    assert assemble_code("a = [BLANK]", "5") == "a = 5"


def test_assemble_code_respeta_indentacion() -> None:
    assert (
        assemble_code("def f():\n    return [BLANK]", "x + 1")
        == "def f():\n    return x + 1"
    )


@pytest.mark.parametrize("plantilla", ["sin huecos", "x = [BLANK] + [BLANK]"])
def test_plantilla_requiere_un_solo_hueco(plantilla: str) -> None:
    with pytest.raises(ValueError, match="exactamente un marcador"):
        validate_template(plantilla)


def test_respuesta_demasiado_larga_se_rechaza() -> None:
    with pytest.raises(ValueError, match="supera"):
        assemble_code("a = [BLANK]", "a" * (MAX_ANSWER_LENGTH + 1))
