import json
import random
from datetime import timedelta

from sqlalchemy import select

from backend.crud import seleccionar_preguntas
from backend.models import Examen, Pregunta, PreguntaAsignada
from backend.models import utc_now
from tests.conftest import acceder_alumno


def iniciar_examen(client, headers):
    consentimiento = client.get("/consentimiento").json()
    response = client.post(
        "/examen/iniciar",
        headers=headers,
        json={
            "consentimiento_version": consentimiento["version"],
            "acepta_grabacion": True,
        },
    )
    assert response.status_code == 200
    return response.json()


def respuestas_correctas(preguntas):
    respuestas_por_clave = {
        "suma-basica": "a + b",
        "suma-producto-dos-huecos": json.dumps(["a + b", "a * b"]),
        "maximo-dos-valores": (
            "def maximo(a, b):\n    if a >= b:\n        return a\n    return b"
        ),
        "clasificar-edad": (
            "def clasificar_edad(edad):\n"
            "    if 0 <= edad <= 12:\n"
            "        return 'niñez'\n"
            "    if 12 < edad < 18:\n"
            "        return 'adolescencia'\n"
            "    if edad >= 18:\n"
            "        return 'edad adulta'\n"
            "    raise ValueError('edad no válida')"
        ),
        "estructura-mutable": "list",
        "resultado-range": "[1, 3, 5]",
        "traza-acumulador": "Imprime 6 porque acumula 1, 2 y 3.",
        "acceso-diccionario": (
            "Se encadenan las claves del alumno, la asignatura y la nota."
        ),
    }
    respuestas = []
    for pregunta in preguntas:
        respuestas.append(
            {
                "pregunta_id": pregunta["id"],
                "contenido": respuestas_por_clave[pregunta["clave"]],
            }
        )
    return respuestas


def test_flujo_alumno_con_preguntas_mixtas(client, examen_activo) -> None:
    headers = acceder_alumno(client)
    examen = iniciar_examen(client, headers)

    assert len(examen["preguntas"]) == 4
    assert {pregunta["tipo"] for pregunta in examen["preguntas"]} == {
        "rellenar_huecos",
        "corregir_codigo",
        "tipo_test",
        "respuesta_corta",
    }
    assert "codigo_solucion" not in examen["preguntas"][0]
    pregunta_huecos = next(
        pregunta
        for pregunta in examen["preguntas"]
        if pregunta["tipo"] == "rellenar_huecos"
    )
    assert pregunta_huecos["numero_huecos"] in {1, 2}

    envio = client.post(
        "/entregas/enviar",
        headers=headers,
        json={
            "entrega_id": examen["entrega_id"],
            "respuestas": respuestas_correctas(examen["preguntas"]),
        },
    )
    assert envio.status_code == 200
    assert envio.json()["nota_global"] == 10.0
    assert envio.json()["preguntas_pendientes"] == 1

    resultado = client.get(
        f"/entregas/{examen['entrega_id']}/resultado", headers=headers
    )
    assert resultado.status_code == 200
    assert resultado.json()["desglose"][-1]["estado"] == "pendiente_revision"


def test_examen_exige_consentimiento(client, examen_activo) -> None:
    headers = acceder_alumno(client)
    consentimiento = client.get("/consentimiento").json()
    response = client.post(
        "/examen/iniciar",
        headers=headers,
        json={
            "consentimiento_version": consentimiento["version"],
            "acepta_grabacion": False,
        },
    )
    assert response.status_code == 400


def test_inicio_fija_preguntas_version_y_peso(
    client, examen_activo, db_session
) -> None:
    examen = iniciar_examen(client, acceder_alumno(client))
    asignaciones = list(
        db_session.scalars(
            select(PreguntaAsignada).where(
                PreguntaAsignada.entrega_id == examen["entrega_id"]
            )
        )
    )

    assert len(asignaciones) == len(examen["preguntas"])
    assert [asignacion.orden for asignacion in asignaciones] == [1, 2, 3, 4]
    assert all(asignacion.version_pregunta == 1 for asignacion in asignaciones)
    assert all(pregunta["clave"] for pregunta in examen["preguntas"])
    assert all(pregunta["peso"] > 0 for pregunta in examen["preguntas"])


def test_envio_rechaza_respuestas_incompletas(client, examen_activo) -> None:
    headers = acceder_alumno(client)
    examen = iniciar_examen(client, headers)
    response = client.post(
        "/entregas/enviar",
        headers=headers,
        json={
            "entrega_id": examen["entrega_id"],
            "respuestas": respuestas_correctas(examen["preguntas"])[:-1],
        },
    )
    assert response.status_code == 400


def test_seleccion_aleatoria_respeta_cantidad_y_publicacion() -> None:
    examen = Examen(
        id=1,
        titulo="Banco",
        duracion_segundos=3600,
        seleccion_json=json.dumps({"rellenar_huecos": 2, "tipo_test": 1}),
    )
    examen.preguntas = [
        Pregunta(
            id=indice,
            examen_id=1,
            clave=f"pregunta-{indice}",
            tipo=tipo,
            titulo=f"Pregunta {indice}",
            enunciado="",
            orden=indice,
            peso=1.0,
            estado=estado,
        )
        for indice, (tipo, estado) in enumerate(
            [
                ("rellenar_huecos", "publicada"),
                ("rellenar_huecos", "publicada"),
                ("rellenar_huecos", "publicada"),
                ("tipo_test", "publicada"),
                ("tipo_test", "borrador"),
            ],
            start=1,
        )
    ]

    elegidas = seleccionar_preguntas(examen, random.Random(7))

    assert len(elegidas) == 3
    assert sum(pregunta.tipo == "rellenar_huecos" for pregunta in elegidas) == 2
    assert sum(pregunta.tipo == "tipo_test" for pregunta in elegidas) == 1
    assert all(pregunta.estado == "publicada" for pregunta in elegidas)


def test_reintento_de_envio_devuelve_la_calificacion_existente(
    client, examen_activo
) -> None:
    headers = acceder_alumno(client)
    examen = iniciar_examen(client, headers)
    datos = {
        "entrega_id": examen["entrega_id"],
        "respuestas": respuestas_correctas(examen["preguntas"]),
    }

    primero = client.post("/entregas/enviar", headers=headers, json=datos)
    segundo = client.post("/entregas/enviar", headers=headers, json=datos)

    assert primero.status_code == 200
    assert segundo.status_code == 200
    assert segundo.json() == primero.json()


def test_examen_fuera_de_ventana_no_puede_iniciarse(
    client, examen_activo, db_session
) -> None:
    examen_activo.apertura_en = utc_now() + timedelta(hours=1)
    db_session.commit()
    headers = acceder_alumno(client)
    consentimiento = client.get("/consentimiento").json()

    response = client.post(
        "/examen/iniciar",
        headers=headers,
        json={
            "consentimiento_version": consentimiento["version"],
            "acepta_grabacion": True,
        },
    )

    assert response.status_code == 404


def test_respuesta_incluye_reloj_y_trazabilidad_de_calculo(
    client, examen_activo
) -> None:
    headers = acceder_alumno(client)
    examen = iniciar_examen(client, headers)
    assert examen["hora_actual_servidor"].endswith("Z")
    assert examen["hora_limite_servidor"].endswith("Z")

    envio = client.post(
        "/entregas/enviar",
        headers=headers,
        json={
            "entrega_id": examen["entrega_id"],
            "respuestas": respuestas_correctas(examen["preguntas"]),
        },
    )
    assert envio.status_code == 200
    assert all(item["peso"] > 0 for item in envio.json()["desglose"])
    assert all(item["version_pregunta"] == 1 for item in envio.json()["desglose"])
