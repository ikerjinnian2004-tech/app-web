from collections.abc import Sequence

BLANK_MARKER = "[BLANK]"
MAX_ANSWER_LENGTH = 10_000


def split_template(template_code: str) -> list[str]:
    return template_code.split(BLANK_MARKER)


def count_blanks(template_code: str) -> int:
    return template_code.count(BLANK_MARKER)


def validate_template(template_code: str) -> None:
    if count_blanks(template_code) == 0:
        raise ValueError("La plantilla debe contener al menos un marcador [BLANK].")


def assemble_code(template_code: str, student_answer: str | Sequence[str]) -> str:
    validate_template(template_code)
    respuestas = (
        [student_answer] if isinstance(student_answer, str) else list(student_answer)
    )
    numero_huecos = count_blanks(template_code)
    if len(respuestas) != numero_huecos:
        raise ValueError(f"La plantilla requiere {numero_huecos} respuestas.")
    if any(len(respuesta) > MAX_ANSWER_LENGTH for respuesta in respuestas):
        raise ValueError(f"La respuesta supera {MAX_ANSWER_LENGTH} caracteres.")

    fragmentos = split_template(template_code)
    partes = [fragmentos[0]]
    for respuesta, fragmento in zip(respuestas, fragmentos[1:], strict=True):
        partes.extend((respuesta, fragmento))
    return "".join(partes)


MARCADOR_HUECO = BLANK_MARKER
LONGITUD_MAXIMA_RESPUESTA = MAX_ANSWER_LENGTH
dividir_plantilla = split_template
contar_huecos = count_blanks
validar_plantilla = validate_template
ensamblar_codigo = assemble_code
BLANK_TOKEN = BLANK_MARKER
parse_template = split_template
