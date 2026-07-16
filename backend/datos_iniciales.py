from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent / "data"
DATOS_INICIALES_PATH = DATA_DIR / "datos_iniciales.json"
CONSENTIMIENTO_PATH = DATA_DIR / "consentimiento-grabacion.md"
COLECCION_POR_ROL = {"alumno": "alumnado", "profesor": "profesorado"}


@lru_cache
def cargar_datos_iniciales() -> dict[str, Any]:
    return json.loads(DATOS_INICIALES_PATH.read_text(encoding="utf-8"))


def normalizar_correo(correo: str) -> str:
    return correo.strip().lower()


def buscar_usuario_en_semilla(rol: str, correo: str) -> dict[str, str] | None:
    correo_normalizado = normalizar_correo(correo)
    clave = COLECCION_POR_ROL[rol]
    usuarios = cargar_datos_iniciales()["usuarios"].get(clave, [])
    for usuario in usuarios:
        if normalizar_correo(usuario["correo"]) == correo_normalizado:
            return {
                "rol": rol,
                "nombre": usuario["nombre"],
                "apellidos": usuario.get("apellidos", ""),
                "correo": correo_normalizado,
            }
    return None


def iterar_usuarios_iniciales(
    datos: dict[str, Any],
) -> Iterator[tuple[str, dict[str, str]]]:
    for rol, coleccion in COLECCION_POR_ROL.items():
        for usuario in datos["usuarios"].get(coleccion, []):
            yield rol, usuario


def iterar_preguntas_iniciales(datos: dict[str, Any]) -> Iterator[dict[str, Any]]:
    orden = 0
    for tipo, preguntas in datos["banco_preguntas"].items():
        for pregunta in preguntas:
            orden += 1
            yield {**pregunta, "tipo": tipo, "orden": orden}


def validar_dominio_institucional(rol: str, correo: str) -> bool:
    correo_normalizado = normalizar_correo(correo)
    if rol == "alumno":
        return correo_normalizado.endswith("@alu.uclm.es")
    return correo_normalizado.endswith("@uclm.es")


def obtener_texto_consentimiento() -> str:
    return CONSENTIMIENTO_PATH.read_text(encoding="utf-8")


def obtener_version_consentimiento() -> str:
    texto = obtener_texto_consentimiento().encode("utf-8")
    return hashlib.sha256(texto).hexdigest()
