from sqlalchemy import select

from backend.models import RevisionManual
from tests.conftest import acceder_alumno, acceder_profesor
from tests.test_flujo_examen import (
    iniciar_examen,
    respuestas_correctas,
)


def entregar_examen(client) -> tuple[dict[str, str], dict, dict]:
    headers = acceder_alumno(client)
    examen = iniciar_examen(client, headers)
    envio = client.post(
        "/entregas/enviar",
        headers=headers,
        json={
            "entrega_id": examen["entrega_id"],
            "respuestas": respuestas_correctas(examen["preguntas"]),
        },
    )
    assert envio.status_code == 200
    return headers, examen, envio.json()


def test_revision_manual_recalcula_nota_y_conserva_autoria(
    client, examen_activo, db_session
) -> None:
    headers_alumno, examen, resultado_inicial = entregar_examen(client)
    pregunta_corta = next(
        pregunta
        for pregunta in examen["preguntas"]
        if pregunta["tipo"] == "respuesta_corta"
    )
    assert resultado_inicial["preguntas_pendientes"] == 1

    revision = client.post(
        f"/profesor/entregas/{examen['entrega_id']}/revisiones/{pregunta_corta['id']}",
        headers=acceder_profesor(client),
        json={"nota": 8, "comentario": "Explicación correcta y concisa."},
    )

    assert revision.status_code == 200
    assert revision.json()["nota_global"] == 9.6
    assert revision.json()["preguntas_pendientes"] == 0
    item = next(
        elemento
        for elemento in revision.json()["desglose"]
        if elemento["pregunta_id"] == pregunta_corta["id"]
    )
    assert item["revision_manual"]["comentario"] == "Explicación correcta y concisa."

    resultado_alumno = client.get(
        f"/entregas/{examen['entrega_id']}/resultado", headers=headers_alumno
    )
    assert resultado_alumno.status_code == 200
    assert resultado_alumno.json()["nota_global"] == 9.6
    registro = db_session.scalar(select(RevisionManual))
    assert registro is not None
    assert registro.profesor_id is not None
    assert registro.nota == 8


def test_alumnado_no_puede_realizar_revision_manual(client, examen_activo) -> None:
    headers_alumno, examen, _ = entregar_examen(client)
    pregunta_corta = next(
        pregunta
        for pregunta in examen["preguntas"]
        if pregunta["tipo"] == "respuesta_corta"
    )
    response = client.post(
        f"/profesor/entregas/{examen['entrega_id']}/revisiones/{pregunta_corta['id']}",
        headers=headers_alumno,
        json={"nota": 10, "comentario": ""},
    )
    assert response.status_code == 403


def test_revision_rechaza_pregunta_no_asignada(client, examen_activo) -> None:
    _, examen, _ = entregar_examen(client)
    response = client.post(
        f"/profesor/entregas/{examen['entrega_id']}/revisiones/99999",
        headers=acceder_profesor(client),
        json={"nota": 5, "comentario": ""},
    )
    assert response.status_code == 400
