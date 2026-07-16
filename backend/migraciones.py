from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import MetaData, inspect, text
from sqlalchemy.engine import Connection, Engine

VERSION_ESQUEMA = 1
NOMBRE_MIGRACION = "banco_preguntas_versionado"

COLUMNAS_EXAMEN = {
    "descripcion": "TEXT NOT NULL DEFAULT ''",
    "estado": "VARCHAR(20) NOT NULL DEFAULT 'publicado'",
    "modo_calificacion": ("VARCHAR(30) NOT NULL DEFAULT 'parcial_por_tests'"),
    "seleccion_json": "TEXT NOT NULL DEFAULT '{}'",
    "version": "INTEGER NOT NULL DEFAULT 1",
    "apertura_en": "TIMESTAMP NULL",
    "cierre_en": "TIMESTAMP NULL",
    "profesor_id": "INTEGER NULL",
}
COLUMNAS_PREGUNTA = {
    "clave": "VARCHAR(100) NULL",
    "version": "INTEGER NOT NULL DEFAULT 1",
    "estado": "VARCHAR(20) NOT NULL DEFAULT 'publicada'",
    "limites_caracteres_json": "TEXT NULL",
    "creada_por_id": "INTEGER NULL",
}
COLUMNAS_CASO_PRUEBA = {
    "visible": "BOOLEAN NOT NULL DEFAULT FALSE",
}


def _crear_registro_migraciones(connection: Connection) -> None:
    connection.execute(
        text(
            "CREATE TABLE IF NOT EXISTS migraciones_esquema ("
            "version INTEGER PRIMARY KEY, "
            "nombre VARCHAR(120) NOT NULL, "
            "aplicada_en VARCHAR(40) NOT NULL)"
        )
    )


def _version_aplicada(connection: Connection) -> int:
    resultado = connection.execute(
        text("SELECT COALESCE(MAX(version), 0) FROM migraciones_esquema")
    ).scalar_one()
    return int(resultado)


def _agregar_columnas(
    connection: Connection,
    tabla: str,
    columnas: dict[str, str],
) -> None:
    existentes = {columna["name"] for columna in inspect(connection).get_columns(tabla)}
    for nombre, definicion in columnas.items():
        if nombre not in existentes:
            connection.execute(
                text(f"ALTER TABLE {tabla} ADD COLUMN {nombre} {definicion}")
            )


def _aplicar_migracion_banco(connection: Connection) -> None:
    _agregar_columnas(connection, "examenes", COLUMNAS_EXAMEN)
    _agregar_columnas(connection, "preguntas", COLUMNAS_PREGUNTA)
    _agregar_columnas(connection, "casos_prueba", COLUMNAS_CASO_PRUEBA)
    connection.execute(
        text(
            "UPDATE preguntas SET clave = 'pregunta-' || id "
            "WHERE clave IS NULL OR clave = ''"
        )
    )
    connection.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_pregunta_clave_version_idx "
            "ON preguntas(clave, version)"
        )
    )
    connection.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_respuesta_entrega_idx "
            "ON respuestas_alumno(entrega_id, pregunta_id)"
        )
    )


def _registrar_version(connection: Connection) -> None:
    aplicada_en = datetime.now(UTC).isoformat()
    connection.execute(
        text(
            "INSERT INTO migraciones_esquema (version, nombre, aplicada_en) "
            "VALUES (:version, :nombre, :aplicada_en)"
        ),
        {
            "version": VERSION_ESQUEMA,
            "nombre": NOMBRE_MIGRACION,
            "aplicada_en": aplicada_en,
        },
    )


def preparar_esquema(engine: Engine, metadata: MetaData) -> None:
    """Migra esquemas previos y deja creadas todas las tablas actuales."""
    with engine.begin() as connection:
        tablas = set(inspect(connection).get_table_names())
        es_instalacion_previa = "examenes" in tablas
        _crear_registro_migraciones(connection)

        if es_instalacion_previa and _version_aplicada(connection) < VERSION_ESQUEMA:
            _aplicar_migracion_banco(connection)

        metadata.create_all(bind=connection)
        if _version_aplicada(connection) < VERSION_ESQUEMA:
            _registrar_version(connection)
