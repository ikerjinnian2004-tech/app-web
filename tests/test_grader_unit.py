from backend.grader import grade_entrega
from backend.models import CasoPrueba, Pregunta, RespuestaAlumno


def test_corrector_mixto_calcula_nota_y_pendientes() -> None:
    preguntas = [
        Pregunta(
            id=1,
            examen_id=1,
            tipo="rellenar_huecos",
            titulo="suma",
            enunciado="",
            codigo_plantilla="def suma(a, b):\n    return [BLANK]",
            codigo_solucion="a + b",
            orden=1,
            peso=1.0,
        ),
        Pregunta(
            id=2,
            examen_id=1,
            tipo="tipo_test",
            titulo="mutable",
            enunciado="",
            respuesta_correcta="list",
            orden=2,
            peso=1.0,
        ),
        Pregunta(
            id=3,
            examen_id=1,
            tipo="respuesta_corta",
            titulo="traza",
            enunciado="",
            orden=3,
            peso=1.0,
        ),
    ]
    respuestas = [
        RespuestaAlumno(entrega_id=1, pregunta_id=1, contenido="a + b"),
        RespuestaAlumno(entrega_id=1, pregunta_id=2, contenido="list"),
        RespuestaAlumno(entrega_id=1, pregunta_id=3, contenido="explicacion"),
    ]
    casos = {
        1: [
            CasoPrueba(
                id=1,
                pregunta_id=1,
                descripcion="basico",
                codigo_test="assert suma(2, 3) == 5",
                salida_esperada="",
                peso=1.0,
            )
        ]
    }

    resultado = grade_entrega(respuestas, preguntas, casos)
    assert resultado["nota_global"] == 10.0
    assert resultado["preguntas_pendientes"] == 1
