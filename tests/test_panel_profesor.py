from tests.conftest import acceder_alumno, acceder_profesor
from tests.test_flujo_examen import iniciar_examen, respuestas_correctas


def crear_entrega_pendiente(client) -> tuple[dict, dict[str, str]]:
    headers_alumno = acceder_alumno(client)
    examen = iniciar_examen(client, headers_alumno)
    response = client.post(
        "/entregas/enviar",
        headers=headers_alumno,
        json={
            "entrega_id": examen["entrega_id"],
            "respuestas": respuestas_correctas(examen["preguntas"]),
        },
    )
    assert response.status_code == 200
    return examen, acceder_profesor(client)


def test_panel_filtra_muestra_detalle_y_estadisticas(client, examen_activo) -> None:
    examen, headers = crear_entrega_pendiente(client)

    pendientes = client.get(
        "/profesor/entregas", headers=headers, params={"estado": "pendiente"}
    )
    corregidas = client.get(
        "/profesor/entregas", headers=headers, params={"estado": "corregida"}
    )
    ajenas = client.get(
        "/profesor/entregas",
        headers=headers,
        params={"correo": "persona-inexistente@alu.uclm.es"},
    )
    detalle = client.get(f"/profesor/entregas/{examen['entrega_id']}", headers=headers)
    estadisticas = client.get("/profesor/estadisticas", headers=headers)

    assert pendientes.status_code == 200
    assert len(pendientes.json()) == 1
    assert corregidas.json() == []
    assert ajenas.json() == []
    assert detalle.status_code == 200
    assert detalle.json()["version_examen"] == 1
    assert detalle.json()["acepta_grabacion"] is True
    assert detalle.json()["permisos_evidencia_verificados"] is True
    assert len(detalle.json()["preguntas"]) == 4
    assert all("respuesta" in pregunta for pregunta in detalle.json()["preguntas"])
    casos = [
        caso
        for pregunta in detalle.json()["preguntas"]
        for caso in pregunta["casos_prueba"]
    ]
    assert any(not caso["visible"] for caso in casos)
    assert all("codigo_test" in caso for caso in casos)
    assert estadisticas.json() == {
        "total_entregas": 1,
        "abiertas": 0,
        "corregidas": 0,
        "pendientes_revision": 1,
        "nota_media": 10.0,
    }


def test_exportacion_aplica_filtros_y_anade_trazabilidad(client, examen_activo) -> None:
    _, headers = crear_entrega_pendiente(client)
    csv = client.get(
        "/profesor/exportar",
        headers=headers,
        params={"estado": "pendiente", "correo": "ikerjinnian"},
    )
    vacio = client.get(
        "/profesor/exportar",
        headers=headers,
        params={"correo": "inexistente"},
    )

    assert csv.status_code == 200
    assert "version_examen" in csv.text
    assert "todo_o_nada_por_pregunta" in csv.text
    assert "ikerjinnian.blanco@alu.uclm.es" in csv.text
    assert "ikerjinnian.blanco@alu.uclm.es" not in vacio.text


def test_detalle_y_filtros_rechazan_acceso_o_valores_invalidos(
    client, examen_activo
) -> None:
    examen, _ = crear_entrega_pendiente(client)
    headers_alumno = acceder_alumno(client)
    detalle = client.get(
        f"/profesor/entregas/{examen['entrega_id']}", headers=headers_alumno
    )
    filtro = client.get(
        "/profesor/entregas",
        headers=acceder_profesor(client),
        params={"estado": "inventado"},
    )
    assert detalle.status_code == 403
    assert filtro.status_code == 422
