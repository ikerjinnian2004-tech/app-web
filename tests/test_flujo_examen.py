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
    respuestas = []
    for pregunta in preguntas:
        if pregunta["tipo"] == "rellenar_huecos":
            contenido = "a + b"
        elif pregunta["tipo"] == "corregir_codigo":
            contenido = (
                "def maximo(a, b):\n    if a >= b:\n        return a\n    return b"
            )
        elif pregunta["tipo"] == "tipo_test":
            contenido = "list"
        else:
            contenido = "Imprime 6 porque acumula 1, 2 y 3."
        respuestas.append({"pregunta_id": pregunta["id"], "contenido": contenido})
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
