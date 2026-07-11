BLANK_TOKEN = "[BLANK]"
MAX_ANSWER_LENGTH = 10_000


def parse_template(codigo_plantilla: str) -> list[str]:
    """Divide la plantilla por el marcador de huecos."""
    return codigo_plantilla.split(BLANK_TOKEN)


def count_blanks(codigo_plantilla: str) -> int:
    """Cuenta cuántos huecos contiene la plantilla."""
    return codigo_plantilla.count(BLANK_TOKEN)


def validate_template(codigo_plantilla: str) -> None:
    if count_blanks(codigo_plantilla) != 1:
        raise ValueError("La plantilla debe contener exactamente un marcador [BLANK].")


def assemble_code(codigo_plantilla: str, respuesta_alumno: str) -> str:
    """Inserta el único bloque editable que admite el MVP."""
    validate_template(codigo_plantilla)
    if len(respuesta_alumno) > MAX_ANSWER_LENGTH:
        raise ValueError(f"La respuesta supera {MAX_ANSWER_LENGTH} caracteres.")
    return codigo_plantilla.replace(BLANK_TOKEN, respuesta_alumno, 1)
