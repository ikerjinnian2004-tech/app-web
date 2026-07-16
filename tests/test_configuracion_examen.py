from tests.conftest import acceder_alumno, acceder_profesor
from tests.test_flujo_examen import iniciar_examen


def configuracion_actual(client, headers) -> dict:
    response = client.get("/profesor/examenes", headers=headers)
    assert response.status_code == 200
    examen = response.json()[0]
    return {
        "titulo": examen["titulo"],
        "descripcion": examen["descripcion"],
        "duracion_segundos": examen["duracion_segundos"],
        "estado": examen["estado"],
        "modo_calificacion": examen["modo_calificacion"],
        "seleccion_por_tipo": examen["seleccion_por_tipo"],
        "apertura_en": examen["apertura_en"],
        "cierre_en": examen["cierre_en"],
    }


def test_versionar_examen_preserva_la_configuracion_del_intento(
    client, examen_activo, db_session
) -> None:
    headers_alumno = acceder_alumno(client)
    intento_original = iniciar_examen(client, headers_alumno)
    headers_profesor = acceder_profesor(client)
    nueva = configuracion_actual(client, headers_profesor)
    nueva["titulo"] = "Evaluación versionada"
    nueva["duracion_segundos"] = 600
    nueva["modo_calificacion"] = "parcial_por_tests"

    response = client.post(
        f"/profesor/examenes/{examen_activo.id}/versiones",
        headers=headers_profesor,
        json=nueva,
    )

    assert response.status_code == 201
    assert response.json()["version"] == 2
    assert response.json()["titulo"] == "Evaluación versionada"
    reanudado = iniciar_examen(client, headers_alumno)
    assert reanudado["titulo"] == intento_original["titulo"]
    assert reanudado["duracion_segundos"] == intento_original["duracion_segundos"]

    versiones = client.get(
        f"/profesor/examenes/{examen_activo.id}/versiones",
        headers=headers_profesor,
    )
    assert versiones.status_code == 200
    assert [item["version"] for item in versiones.json()] == [1, 2]
    assert versiones.json()[0]["configuracion"]["titulo"] == intento_original["titulo"]
    assert versiones.json()[1]["configuracion"]["titulo"] == "Evaluación versionada"


def test_configuracion_rechaza_cantidades_no_disponibles(client, examen_activo) -> None:
    headers = acceder_profesor(client)
    datos = configuracion_actual(client, headers)
    datos["seleccion_por_tipo"] = {"tipo_test": 99}

    response = client.post(
        f"/profesor/examenes/{examen_activo.id}/versiones",
        headers=headers,
        json=datos,
    )

    assert response.status_code == 400


def test_alumnado_no_puede_versionar_configuracion(client, examen_activo) -> None:
    headers_profesor = acceder_profesor(client)
    datos = configuracion_actual(client, headers_profesor)
    response = client.post(
        f"/profesor/examenes/{examen_activo.id}/versiones",
        headers=acceder_alumno(client),
        json=datos,
    )
    assert response.status_code == 403
