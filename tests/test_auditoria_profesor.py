from tests.conftest import acceder_alumno, acceder_profesor
from tests.test_flujo_examen import iniciar_examen, respuestas_correctas


def test_auditoria_evidencia_y_panel_docente(client, examen_activo) -> None:
    headers_alumno = acceder_alumno(client)
    examen = iniciar_examen(client, headers_alumno)

    evento = client.post(
        "/auditoria/eventos",
        headers=headers_alumno,
        json={
            "tipo": "CAMBIO_PESTANA",
            "timestamp_cliente": "2026-07-07T10:00:00Z",
            "metadata": {"origen": "test"},
        },
    )
    assert evento.status_code == 200
    assert evento.json()["grabar_evidencia"] is True

    subida = client.post(
        "/auditoria/evidencias",
        headers=headers_alumno,
        data={
            "evento_id": str(evento.json()["evento_id"]),
            "tipo": "pantalla_camara_audio",
            "mime_type": "video/webm",
        },
        files={"archivo": ("evidencia.webm", b"webm-test", "video/webm")},
    )
    assert subida.status_code == 200

    client.post(
        "/entregas/enviar",
        headers=headers_alumno,
        json={
            "entrega_id": examen["entrega_id"],
            "respuestas": respuestas_correctas(examen["preguntas"]),
        },
    )

    headers_profesor = acceder_profesor(client)
    entregas = client.get("/profesor/entregas", headers=headers_profesor)
    assert entregas.status_code == 200
    evidencia_id = entregas.json()[0]["eventos"][0]["evidencias"][0]

    evidencia = client.get(
        f"/profesor/evidencias/{evidencia_id}", headers=headers_profesor
    )
    assert evidencia.status_code == 200
    assert evidencia.content == b"webm-test"

    csv = client.get("/profesor/exportar", headers=headers_profesor)
    assert csv.status_code == 200
    assert "ana.garcia@alu.uclm.es" in csv.text


def test_panel_docente_rechaza_token_de_alumno(client, examen_activo) -> None:
    headers_alumno = acceder_alumno(client)
    response = client.get("/profesor/entregas", headers=headers_alumno)
    assert response.status_code == 403
