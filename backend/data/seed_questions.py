from __future__ import annotations

import os
import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def bootstrap_python_path() -> None:
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))


def bootstrap_local_environment() -> None:
    os.environ.setdefault("DATABASE_URL", "sqlite:///./dev.db")
    os.environ.setdefault("SECRET_KEY", "clave-local-seed-1234567890-abcdefghijkl")
    os.environ.setdefault(
        "IDENTITY_HMAC_KEY", "clave-hmac-local-seed-minimo-32-caracteres"
    )
    os.environ.setdefault(
        "ALLOWED_ORIGINS", "http://localhost:5500,http://127.0.0.1:5500"
    )


def main() -> int:
    bootstrap_python_path()
    bootstrap_local_environment()

    from backend.crud import obtener_o_crear_usuario_permitido
    from backend.database import SessionLocal, create_tables
    from backend.datos_iniciales import (
        cargar_datos_iniciales,
        iterar_preguntas_iniciales,
        iterar_usuarios_iniciales,
        normalizar_correo,
    )
    from backend.models import CasoPrueba, Examen, Pregunta
    from backend.template_engine import validar_plantilla

    create_tables()
    datos = cargar_datos_iniciales()

    db = SessionLocal()
    try:
        usuarios_creados = {}
        for rol, usuario in iterar_usuarios_iniciales(datos):
            creado = obtener_o_crear_usuario_permitido(
                db,
                {
                    "rol": rol,
                    "nombre": usuario["nombre"],
                    "apellidos": usuario.get("apellidos", ""),
                    "correo": normalizar_correo(usuario["correo"]),
                },
            )
            usuarios_creados[creado.correo] = creado

        if db.query(Examen).count() > 0:
            print("Usuarios revisados; el examen ya estaba sembrado.")
            return 0

        examen_data = datos["examen"]
        examen = Examen(
            titulo=examen_data["titulo"],
            descripcion=examen_data.get("descripcion", ""),
            duracion_segundos=int(examen_data["duracion_minutos"]) * 60,
            activo=examen_data.get("estado", "publicado") == "publicado",
            estado=examen_data.get("estado", "publicado"),
            modo_calificacion=examen_data.get("modo_calificacion", "parcial_por_tests"),
            seleccion_json=json.dumps(
                examen_data.get("seleccion_por_tipo", {}), ensure_ascii=False
            ),
            version=examen_data.get("version", 1),
            profesor_id=usuarios_creados[
                normalizar_correo(examen_data["profesor_principal"])
            ].id,
        )
        db.add(examen)
        db.flush()

        for pregunta_data in iterar_preguntas_iniciales(datos):
            plantilla = pregunta_data.get("codigo_plantilla")
            if pregunta_data["tipo"] == "rellenar_huecos" and plantilla:
                validar_plantilla(plantilla)

            pregunta = Pregunta(
                examen_id=examen.id,
                clave=pregunta_data["clave"],
                version=pregunta_data.get("version", 1),
                estado=pregunta_data.get("estado", "publicada"),
                tipo=pregunta_data["tipo"],
                titulo=pregunta_data["titulo"],
                enunciado=pregunta_data["enunciado"],
                codigo_plantilla=plantilla,
                codigo_solucion=pregunta_data.get("codigo_solucion"),
                opciones_json=(
                    json.dumps(pregunta_data["opciones"], ensure_ascii=False)
                    if "opciones" in pregunta_data
                    else None
                ),
                respuesta_correcta=pregunta_data.get("respuesta_correcta"),
                limites_caracteres_json=(
                    json.dumps(pregunta_data["limites_caracteres"], ensure_ascii=False)
                    if "limites_caracteres" in pregunta_data
                    else None
                ),
                orden=pregunta_data["orden"],
                peso=pregunta_data["peso"],
                creada_por_id=examen.profesor_id,
            )
            db.add(pregunta)
            db.flush()

            for caso_data in pregunta_data.get("casos_prueba", []):
                db.add(
                    CasoPrueba(
                        pregunta_id=pregunta.id,
                        descripcion=caso_data["descripcion"],
                        codigo_test=caso_data["codigo_test"],
                        salida_esperada=caso_data.get("salida_esperada", ""),
                        peso=caso_data.get("peso", 1.0),
                        visible=caso_data.get("visible", False),
                    )
                )

        db.commit()
        print(f"Examen cargado: {examen.titulo}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
