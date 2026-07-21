from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select

from backend.models import BorradorRespuesta, Entrega, RespuestaAlumno, utc_now
from tests.conftest import acceder_alumno
from tests.test_flujo_examen import (
    iniciar_examen,
    respuestas_correctas,
)


def guardar(
    client,
    headers: dict[str, str],
    entrega_id: int,
    pregunta_id: int,
    contenido: str,
    version: int = 0,
):
    return client.post(
        f"/borradores/{entrega_id}",
        headers=headers,
        json={
            "pregunta_id": pregunta_id,
            "contenido": contenido,
            "version_esperada": version,
        },
    )


def test_borrador_se_guarda_actualiza_y_recupera_tras_recarga(
    client, examen_activo
) -> None:
    headers = acceder_alumno(client)
    examen = iniciar_examen(client, headers)
    pregunta_id = examen["preguntas"][0]["id"]

    primero = guardar(client, headers, examen["entrega_id"], pregunta_id, "uno")
    segundo = guardar(
        client,
        headers,
        examen["entrega_id"],
        pregunta_id,
        "dos",
        version=primero.json()["version"],
    )
    recuperados = client.get(f"/borradores/{examen['entrega_id']}", headers=headers)

    assert primero.status_code == 200
    assert primero.json()["version"] == 1
    assert segundo.status_code == 200
    assert segundo.json()["version"] == 2
    assert segundo.json()["actualizado_en"]
    assert recuperados.status_code == 200
    assert recuperados.json() == [segundo.json()]


def test_dos_pestanas_no_pueden_sobrescribir_una_version_mas_nueva(
    client, examen_activo
) -> None:
    headers = acceder_alumno(client)
    examen = iniciar_examen(client, headers)
    pregunta_id = examen["preguntas"][0]["id"]
    inicial = guardar(client, headers, examen["entrega_id"], pregunta_id, "base")
    version_compartida = inicial.json()["version"]

    ganadora = guardar(
        client,
        headers,
        examen["entrega_id"],
        pregunta_id,
        "pestaña uno",
        version_compartida,
    )
    obsoleta = guardar(
        client,
        headers,
        examen["entrega_id"],
        pregunta_id,
        "pestaña dos",
        version_compartida,
    )

    assert ganadora.status_code == 200
    assert obsoleta.status_code == 409
    assert "otra pestaña" in obsoleta.json()["detail"]


def test_borrador_no_es_respuesta_calificable(
    client, examen_activo, db_session
) -> None:
    headers = acceder_alumno(client)
    examen = iniciar_examen(client, headers)
    pregunta_id = examen["preguntas"][0]["id"]

    respuesta = guardar(
        client, headers, examen["entrega_id"], pregunta_id, "solo borrador"
    )

    assert respuesta.status_code == 200
    assert (db_session.scalar(select(func.count(RespuestaAlumno.id))) or 0) == 0
    resultado = client.get(
        f"/entregas/{examen['entrega_id']}/resultado", headers=headers
    )
    assert resultado.status_code == 404


def test_envio_elimina_borradores_en_la_misma_transaccion(
    client, examen_activo, db_session
) -> None:
    headers = acceder_alumno(client)
    examen = iniciar_examen(client, headers)
    pregunta_id = examen["preguntas"][0]["id"]
    assert (
        guardar(
            client, headers, examen["entrega_id"], pregunta_id, "temporal"
        ).status_code
        == 200
    )

    envio = client.post(
        "/entregas/enviar",
        headers=headers,
        json={
            "entrega_id": examen["entrega_id"],
            "respuestas": respuestas_correctas(examen["preguntas"]),
        },
    )

    assert envio.status_code == 200
    assert (db_session.scalar(select(func.count(BorradorRespuesta.id))) or 0) == 0
    posterior = guardar(
        client, headers, examen["entrega_id"], pregunta_id, "demasiado tarde"
    )
    assert posterior.status_code == 409


def test_borrador_rechaza_pregunta_no_asignada(client, examen_activo) -> None:
    headers = acceder_alumno(client)
    examen = iniciar_examen(client, headers)

    respuesta = guardar(client, headers, examen["entrega_id"], 999_999, "ajena")

    assert respuesta.status_code == 409


def test_borrador_rechaza_contenido_excesivo(client, examen_activo) -> None:
    headers = acceder_alumno(client)
    examen = iniciar_examen(client, headers)
    pregunta_id = examen["preguntas"][0]["id"]

    respuesta = guardar(
        client,
        headers,
        examen["entrega_id"],
        pregunta_id,
        "x" * 20_001,
    )

    assert respuesta.status_code == 422


def test_borrador_rechaza_intento_fuera_de_tiempo(
    client, examen_activo, db_session
) -> None:
    headers = acceder_alumno(client)
    examen = iniciar_examen(client, headers)
    entrega = db_session.get(Entrega, examen["entrega_id"])
    assert entrega is not None
    entrega.hora_inicio = utc_now() - timedelta(hours=2)
    entrega.duracion_examen_segundos = 60
    db_session.commit()

    respuesta = guardar(
        client,
        headers,
        examen["entrega_id"],
        examen["preguntas"][0]["id"],
        "fuera de tiempo",
    )

    assert respuesta.status_code == 408
