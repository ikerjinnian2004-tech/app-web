from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import MetaData, inspect, text
from sqlalchemy.engine import Connection, Engine

VERSION_ESQUEMA = 4

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
COLUMNAS_ENTREGA_VERSIONADA = {
    "version_examen": "INTEGER NOT NULL DEFAULT 1",
    "titulo_examen": "VARCHAR(200) NOT NULL DEFAULT ''",
    "duracion_examen_segundos": "INTEGER NOT NULL DEFAULT 0",
    "modo_calificacion": ("VARCHAR(30) NOT NULL DEFAULT 'parcial_por_tests'"),
}
COLUMNAS_ENTREGA_CONCURRENTE = {
    "procesando": "BOOLEAN NOT NULL DEFAULT FALSE",
    "procesando_desde": "TIMESTAMP NULL",
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
    if tabla not in inspect(connection).get_table_names():
        return
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


def _aplicar_migracion_version_examen(connection: Connection) -> None:
    _agregar_columnas(connection, "entregas", COLUMNAS_ENTREGA_VERSIONADA)
    if "entregas" not in inspect(connection).get_table_names():
        return
    connection.execute(
        text(
            "UPDATE entregas SET "
            "titulo_examen = COALESCE((SELECT titulo FROM examenes "
            "WHERE examenes.id = entregas.examen_id), titulo_examen), "
            "duracion_examen_segundos = COALESCE((SELECT duracion_segundos "
            "FROM examenes WHERE examenes.id = entregas.examen_id), "
            "duracion_examen_segundos), "
            "modo_calificacion = COALESCE((SELECT modo_calificacion "
            "FROM examenes WHERE examenes.id = entregas.examen_id), "
            "modo_calificacion)"
        )
    )


def _aplicar_migracion_concurrencia(connection: Connection) -> None:
    _agregar_columnas(connection, "entregas", COLUMNAS_ENTREGA_CONCURRENTE)


MIGRACIONES = (
    (1, "banco_preguntas_versionado", _aplicar_migracion_banco),
    (2, "configuracion_examen_versionada", _aplicar_migracion_version_examen),
    (3, "revision_manual_trazable", lambda _: None),
    (4, "cierre_entrega_concurrente", _aplicar_migracion_concurrencia),
)


def _registrar_version(connection: Connection, version: int, nombre: str) -> None:
    aplicada_en = datetime.now(UTC).isoformat()
    connection.execute(
        text(
            "INSERT INTO migraciones_esquema (version, nombre, aplicada_en) "
            "VALUES (:version, :nombre, :aplicada_en)"
        ),
        {
            "version": version,
            "nombre": nombre,
            "aplicada_en": aplicada_en,
        },
    )


def preparar_esquema(engine: Engine, metadata: MetaData) -> None:
    """Migra esquemas previos y deja creadas todas las tablas actuales."""
    with engine.begin() as connection:
        tablas = set(inspect(connection).get_table_names())
        es_instalacion_previa = "examenes" in tablas
        _crear_registro_migraciones(connection)

        for version, nombre, aplicar in MIGRACIONES:
            if es_instalacion_previa and _version_aplicada(connection) < version:
                aplicar(connection)
                _registrar_version(connection, version, nombre)

        metadata.create_all(bind=connection)
        for version, nombre, _ in MIGRACIONES:
            if _version_aplicada(connection) < version:
                _registrar_version(connection, version, nombre)
