from tests.conftest import acceder_alumno, acceder_profesor
from tests.test_flujo_examen import iniciar_examen, respuestas_correctas


def crear_evento_con_evidencia(client, headers_alumno) -> int:
    response = client.post(
        "/auditoria/eventos",
        headers=headers_alumno,
        json={
            "tipo": "CAMBIO_PESTANA",
            "timestamp_cliente": "2026-07-07T10:00:00Z",
            "metadata": {},
        },
    )
    assert response.status_code == 200
    return response.json()["evento_id"]


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
    assert "ikerjinnian.blanco@alu.uclm.es" in csv.text


def test_panel_docente_rechaza_token_de_alumno(client, examen_activo) -> None:
    headers_alumno = acceder_alumno(client)
    response = client.get("/profesor/entregas", headers=headers_alumno)
    assert response.status_code == 403


def test_evidencia_rechaza_formato_vacio_y_exceso(
    client, examen_activo, monkeypatch
) -> None:
    headers = acceder_alumno(client)
    iniciar_examen(client, headers)
    evento_id = crear_evento_con_evidencia(client, headers)

    formato = client.post(
        "/auditoria/evidencias",
        headers=headers,
        data={"evento_id": evento_id, "tipo": "pantalla", "mime_type": "text/plain"},
        files={"archivo": ("evidencia.txt", b"texto", "text/plain")},
    )
    vacio = client.post(
        "/auditoria/evidencias",
        headers=headers,
        data={"evento_id": evento_id, "tipo": "pantalla", "mime_type": "video/webm"},
        files={"archivo": ("evidencia.webm", b"", "video/webm")},
    )
    monkeypatch.setattr("backend.routers.audit.settings.evidencia_max_bytes", 5)
    exceso = client.post(
        "/auditoria/evidencias",
        headers=headers,
        data={"evento_id": evento_id, "tipo": "pantalla", "mime_type": "video/webm"},
        files={"archivo": ("evidencia.webm", b"123456", "video/webm")},
    )

    assert formato.status_code == 400
    assert vacio.status_code == 400
    assert exceso.status_code == 413


def test_evidencia_rechaza_evento_no_grabable_y_entrega_cerrada(
    client, examen_activo
) -> None:
    headers = acceder_alumno(client)
    examen = iniciar_examen(client, headers)
    no_grabable = client.post(
        "/auditoria/eventos",
        headers=headers,
        json={
            "tipo": "ENVIO_MANUAL",
            "timestamp_cliente": "2026-07-07T10:00:00Z",
            "metadata": {},
        },
    ).json()["evento_id"]
    response = client.post(
        "/auditoria/evidencias",
        headers=headers,
        data={"evento_id": no_grabable, "tipo": "pantalla", "mime_type": "video/webm"},
        files={"archivo": ("evidencia.webm", b"webm", "video/webm")},
    )
    assert response.status_code == 400

    evento_id = crear_evento_con_evidencia(client, headers)
    client.post(
        "/entregas/enviar",
        headers=headers,
        json={
            "entrega_id": examen["entrega_id"],
            "respuestas": respuestas_correctas(examen["preguntas"]),
        },
    )
    cerrada = client.post(
        "/auditoria/evidencias",
        headers=headers,
        data={"evento_id": evento_id, "tipo": "pantalla", "mime_type": "video/webm"},
        files={"archivo": ("evidencia.webm", b"webm", "video/webm")},
    )
    assert cerrada.status_code == 403


def test_api_incluye_cabeceras_de_seguridad(client) -> None:
    response = client.get("/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["cache-control"] == "no-store"


def test_evento_rechaza_metadata_desproporcionada(client, examen_activo) -> None:
    headers = acceder_alumno(client)
    iniciar_examen(client, headers)
    response = client.post(
        "/auditoria/eventos",
        headers=headers,
        json={
            "tipo": "CAMBIO_PESTANA",
            "timestamp_cliente": "2026-07-07T10:00:00Z",
            "metadata": {"relleno": "x" * 5_001},
        },
    )
    assert response.status_code == 422
