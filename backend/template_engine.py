BLANK_MARKER = "[BLANK]"
MAX_ANSWER_LENGTH = 10_000


def split_template(template_code: str) -> list[str]:
    return template_code.split(BLANK_MARKER)


def count_blanks(template_code: str) -> int:
    return template_code.count(BLANK_MARKER)


def validate_template(template_code: str) -> None:
    if count_blanks(template_code) != 1:
        raise ValueError("La plantilla debe contener exactamente un marcador [BLANK].")


def assemble_code(template_code: str, student_answer: str) -> str:
    validate_template(template_code)
    if len(student_answer) > MAX_ANSWER_LENGTH:
        raise ValueError(f"La respuesta supera {MAX_ANSWER_LENGTH} caracteres.")
    return template_code.replace(BLANK_MARKER, student_answer, 1)


MARCADOR_HUECO = BLANK_MARKER
LONGITUD_MAXIMA_RESPUESTA = MAX_ANSWER_LENGTH
dividir_plantilla = split_template
contar_huecos = count_blanks
validar_plantilla = validate_template
ensamblar_codigo = assemble_code
BLANK_TOKEN = BLANK_MARKER
parse_template = split_template
