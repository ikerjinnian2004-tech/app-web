MARCADOR_HUECO = "[BLANK]"
LONGITUD_MAXIMA_RESPUESTA = 10_000


def dividir_plantilla(codigo_plantilla: str) -> list[str]:
    return codigo_plantilla.split(MARCADOR_HUECO)


def contar_huecos(codigo_plantilla: str) -> int:
    return codigo_plantilla.count(MARCADOR_HUECO)


def validar_plantilla(codigo_plantilla: str) -> None:
    if contar_huecos(codigo_plantilla) != 1:
        raise ValueError("La plantilla debe contener exactamente un marcador [BLANK].")


def ensamblar_codigo(codigo_plantilla: str, respuesta_alumno: str) -> str:
    validar_plantilla(codigo_plantilla)
    if len(respuesta_alumno) > LONGITUD_MAXIMA_RESPUESTA:
        raise ValueError(
            f"La respuesta supera {LONGITUD_MAXIMA_RESPUESTA} caracteres."
        )
    return codigo_plantilla.replace(MARCADOR_HUECO, respuesta_alumno, 1)


# Compatibilidad para consumidores que importen la API anterior del módulo.
BLANK_TOKEN = MARCADOR_HUECO
MAX_ANSWER_LENGTH = LONGITUD_MAXIMA_RESPUESTA
parse_template = dividir_plantilla
count_blanks = contar_huecos
validate_template = validar_plantilla
assemble_code = ensamblar_codigo
