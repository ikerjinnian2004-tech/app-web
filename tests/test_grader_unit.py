import json

from backend.grader import grade_code_answer, grade_entrega
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


def test_corrector_compone_varios_huecos() -> None:
    pregunta = Pregunta(
        id=1,
        examen_id=1,
        tipo="rellenar_huecos",
        titulo="suma y producto",
        enunciado="",
        codigo_plantilla=("def operaciones(a, b):\n    return [BLANK], [BLANK]"),
        orden=1,
        peso=1.0,
    )
    casos = [
        CasoPrueba(
            id=1,
            pregunta_id=1,
            descripcion="basico",
            codigo_test="assert operaciones(2, 3) == (5, 6)",
            salida_esperada="",
            peso=1.0,
        )
    ]

    resultado = grade_code_answer(
        pregunta,
        json.dumps(["a + b", "a * b"]),
        casos,
    )

    assert resultado.nota == 10.0
    assert resultado.tests_ok == 1


def test_modo_todo_o_nada_no_concede_puntuacion_parcial() -> None:
    pregunta = Pregunta(
        id=1,
        examen_id=1,
        clave="identidad",
        tipo="corregir_codigo",
        titulo="Identidad",
        enunciado="",
        orden=1,
        peso=1.0,
    )
    casos = [
        CasoPrueba(
            id=1,
            pregunta_id=1,
            descripcion="Valor positivo",
            codigo_test="assert identidad(2) == 2",
            salida_esperada="",
            peso=1.0,
            visible=True,
        ),
        CasoPrueba(
            id=2,
            pregunta_id=1,
            descripcion="Valor negativo",
            codigo_test="assert identidad(-2) == -2",
            salida_esperada="",
            peso=1.0,
            visible=False,
        ),
    ]

    parcial = grade_code_answer(pregunta, "def identidad(x): return abs(x)", casos)
    todo_o_nada = grade_code_answer(
        pregunta,
        "def identidad(x): return abs(x)",
        casos,
        modo_calificacion="todo_o_nada_por_pregunta",
    )

    assert parcial.nota == 5.0
    assert todo_o_nada.nota == 0.0
    assert todo_o_nada.casos == [
        {
            "caso_id": 1,
            "descripcion": "Valor positivo",
            "visible": True,
            "correcto": True,
            "error_type": None,
        },
        {
            "caso_id": 2,
            "descripcion": "Valor negativo",
            "visible": False,
            "correcto": False,
            "error_type": "RUNTIME_ERROR",
        },
    ]


def test_nota_global_usa_el_peso_fijado_en_la_entrega() -> None:
    preguntas = [
        Pregunta(
            id=1,
            examen_id=1,
            clave="test-uno",
            tipo="tipo_test",
            titulo="Uno",
            enunciado="",
            respuesta_correcta="sí",
            orden=1,
            peso=99,
        ),
        Pregunta(
            id=2,
            examen_id=1,
            clave="test-dos",
            tipo="tipo_test",
            titulo="Dos",
            enunciado="",
            respuesta_correcta="sí",
            orden=2,
            peso=99,
        ),
    ]
    respuestas = [
        RespuestaAlumno(entrega_id=1, pregunta_id=1, contenido="sí"),
        RespuestaAlumno(entrega_id=1, pregunta_id=2, contenido="no"),
    ]

    resultado = grade_entrega(
        respuestas,
        preguntas,
        {},
        pesos_por_pregunta={1: 3.0, 2: 1.0},
    )

    assert resultado["nota_global"] == 7.5
    assert [item["peso"] for item in resultado["desglose"]] == [3.0, 1.0]
