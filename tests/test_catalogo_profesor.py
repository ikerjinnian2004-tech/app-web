from sqlalchemy import select

from backend.models import Pregunta
from tests.conftest import acceder_alumno, acceder_profesor


def pregunta_tipo_test(examen_id: int) -> dict:
    return {
        "examen_id": examen_id,
        "clave": "operador-potencia",
        "tipo": "tipo_test",
        "titulo": "Operador de potencia",
        "enunciado": "¿Qué operador calcula una potencia en Python?",
        "opciones": ["^", "**", "pow="],
        "respuesta_correcta": "**",
        "orden": 20,
        "peso": 2.0,
        "estado": "publicada",
        "casos_prueba": [],
    }


def test_profesor_crea_filtra_y_versiona_pregunta(
    client, examen_activo, db_session
) -> None:
    headers = acceder_profesor(client)
    creacion = client.post(
        "/profesor/preguntas",
        headers=headers,
        json=pregunta_tipo_test(examen_activo.id),
    )
    assert creacion.status_code == 201
    creada = creacion.json()
    assert creada["version"] == 1
    assert creada["estado"] == "publicada"

    nueva_definicion = pregunta_tipo_test(examen_activo.id)
    nueva_definicion.pop("examen_id")
    nueva_definicion.pop("clave")
    nueva_definicion["titulo"] = "Potencias en Python"
    version = client.post(
        f"/profesor/preguntas/{creada['id']}/versiones",
        headers=headers,
        json=nueva_definicion,
    )
    assert version.status_code == 201
    assert version.json()["version"] == 2
    assert version.json()["titulo"] == "Potencias en Python"

    filtradas = client.get(
        "/profesor/preguntas",
        headers=headers,
        params={"tipo": "tipo_test", "estado": "publicada"},
    )
    assert filtradas.status_code == 200
    coincidencias = [
        pregunta
        for pregunta in filtradas.json()
        if pregunta["clave"] == "operador-potencia"
    ]
    assert [
        (pregunta["version"], pregunta["estado"]) for pregunta in coincidencias
    ] == [(2, "publicada")]
    anterior = db_session.scalar(select(Pregunta).where(Pregunta.id == creada["id"]))
    assert anterior is not None
    assert anterior.estado == "retirada"


def test_catalogo_rechaza_definicion_invalida_y_clave_duplicada(
    client, examen_activo
) -> None:
    headers = acceder_profesor(client)
    datos = pregunta_tipo_test(examen_activo.id)
    datos["respuesta_correcta"] = "//"
    invalida = client.post("/profesor/preguntas", headers=headers, json=datos)
    assert invalida.status_code == 400

    datos = pregunta_tipo_test(examen_activo.id)
    primera = client.post("/profesor/preguntas", headers=headers, json=datos)
    segunda = client.post("/profesor/preguntas", headers=headers, json=datos)
    assert primera.status_code == 201
    assert segunda.status_code == 409


def test_catalogo_docente_rechaza_alumnado(client, examen_activo) -> None:
    response = client.get("/profesor/preguntas", headers=acceder_alumno(client))
    assert response.status_code == 403


def test_publicar_version_retirada_despublica_la_otra(
    client, examen_activo, db_session
) -> None:
    headers = acceder_profesor(client)
    original = db_session.scalar(
        select(Pregunta).where(Pregunta.clave == "estructura-mutable")
    )
    assert original is not None
    definicion = {
        "tipo": original.tipo,
        "titulo": "Estructuras mutables",
        "enunciado": original.enunciado,
        "opciones": ["tuple", "list", "str", "range"],
        "respuesta_correcta": "list",
        "orden": original.orden,
        "peso": original.peso,
        "estado": "publicada",
        "casos_prueba": [],
    }
    version = client.post(
        f"/profesor/preguntas/{original.id}/versiones",
        headers=headers,
        json=definicion,
    ).json()

    republicar = client.post(
        f"/profesor/preguntas/{original.id}/estado",
        headers=headers,
        json={"estado": "publicada"},
    )
    assert republicar.status_code == 200
    nueva = db_session.get(Pregunta, version["id"])
    assert nueva is not None
    assert nueva.estado == "retirada"
