from __future__ import annotations

import csv
import io
import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm import joinedload

from backend.crud import listar_entregas_para_profesor, obtener_evidencia
from backend.database import get_db
from backend.errors import bad_request, conflict, not_found
from backend.models import (
    CasoPrueba,
    Entrega,
    Examen,
    Pregunta,
    UsuarioPermitido,
    VersionExamen,
)
from backend.schemas import (
    CasoPruebaDocente,
    ConfiguracionExamenActualizar,
    DefinicionPreguntaDocente,
    EntregaProfesor,
    EstadoPregunta,
    EstadoPreguntaActualizar,
    EventoProfesor,
    ExamenDocente,
    PreguntaCrear,
    PreguntaDocente,
    PreguntaVersionar,
    TipoPregunta,
    VersionExamenDocente,
)
from backend.security import exigir_rol
from backend.template_engine import contar_huecos, validar_plantilla

router = APIRouter()


def _fecha_utc_naive(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _configuracion_examen(examen: Examen) -> dict[str, object]:
    return {
        "titulo": examen.titulo,
        "descripcion": examen.descripcion,
        "duracion_segundos": examen.duracion_segundos,
        "estado": examen.estado,
        "modo_calificacion": examen.modo_calificacion,
        "seleccion_por_tipo": json.loads(examen.seleccion_json or "{}"),
        "apertura_en": fecha_publica(examen.apertura_en),
        "cierre_en": fecha_publica(examen.cierre_en),
    }


def _examen_docente(examen: Examen) -> ExamenDocente:
    return ExamenDocente(
        id=examen.id,
        version=examen.version,
        activo=examen.activo,
        profesor_id=examen.profesor_id,
        titulo=examen.titulo,
        descripcion=examen.descripcion,
        duracion_segundos=examen.duracion_segundos,
        estado=examen.estado,
        modo_calificacion=examen.modo_calificacion,
        seleccion_por_tipo=json.loads(examen.seleccion_json or "{}"),
        apertura_en=examen.apertura_en,
        cierre_en=examen.cierre_en,
    )


def _validar_configuracion_examen(
    db: Session,
    examen: Examen,
    datos: ConfiguracionExamenActualizar,
) -> tuple[datetime | None, datetime | None]:
    apertura = _fecha_utc_naive(datos.apertura_en)
    cierre = _fecha_utc_naive(datos.cierre_en)
    if apertura is not None and cierre is not None and apertura >= cierre:
        raise bad_request("La fecha de cierre debe ser posterior a la apertura.")
    if not datos.seleccion_por_tipo or sum(datos.seleccion_por_tipo.values()) < 1:
        raise bad_request("La selección debe incluir al menos una pregunta.")
    for tipo, cantidad in datos.seleccion_por_tipo.items():
        if cantidad < 0:
            raise bad_request("Las cantidades de preguntas no pueden ser negativas.")
        disponibles = db.scalar(
            select(func.count(Pregunta.id)).where(
                Pregunta.examen_id == examen.id,
                Pregunta.tipo == tipo,
                Pregunta.estado == "publicada",
            )
        )
        if int(disponibles or 0) < cantidad:
            raise bad_request(
                f"No hay {cantidad} preguntas publicadas disponibles del tipo {tipo}."
            )
    return apertura, cierre


def _anadir_instantanea_examen(
    db: Session,
    examen: Examen,
    profesor_id: int,
) -> None:
    existente = db.scalar(
        select(VersionExamen.id).where(
            VersionExamen.examen_id == examen.id,
            VersionExamen.version == examen.version,
        )
    )
    if existente is None:
        db.add(
            VersionExamen(
                examen_id=examen.id,
                version=examen.version,
                configuracion_json=json.dumps(
                    _configuracion_examen(examen), ensure_ascii=False
                ),
                creada_por_id=profesor_id,
            )
        )


def _pregunta_docente(pregunta: Pregunta) -> PreguntaDocente:
    return PreguntaDocente(
        id=pregunta.id,
        examen_id=pregunta.examen_id,
        clave=pregunta.clave,
        version=pregunta.version,
        tipo=pregunta.tipo,
        titulo=pregunta.titulo,
        enunciado=pregunta.enunciado,
        codigo_plantilla=pregunta.codigo_plantilla,
        codigo_solucion=pregunta.codigo_solucion,
        opciones=(
            json.loads(pregunta.opciones_json) if pregunta.opciones_json else None
        ),
        respuesta_correcta=pregunta.respuesta_correcta,
        limites_caracteres=(
            json.loads(pregunta.limites_caracteres_json)
            if pregunta.limites_caracteres_json
            else None
        ),
        orden=pregunta.orden,
        peso=pregunta.peso,
        estado=pregunta.estado,
        creada_por_id=pregunta.creada_por_id,
        casos_prueba=[
            CasoPruebaDocente(
                id=caso.id,
                descripcion=caso.descripcion,
                codigo_test=caso.codigo_test,
                salida_esperada=caso.salida_esperada,
                peso=caso.peso,
                visible=caso.visible,
            )
            for caso in pregunta.casos_prueba
        ],
    )


def _validar_definicion_pregunta(datos: DefinicionPreguntaDocente) -> None:
    if datos.tipo == "rellenar_huecos":
        if not datos.codigo_plantilla:
            raise bad_request("Una pregunta de huecos necesita una plantilla.")
        try:
            validar_plantilla(datos.codigo_plantilla)
        except ValueError as exc:
            raise bad_request(str(exc)) from exc
        numero_huecos = contar_huecos(datos.codigo_plantilla)
        if (
            datos.limites_caracteres is not None
            and len(datos.limites_caracteres) != numero_huecos
        ):
            raise bad_request("Debe existir un límite por cada hueco.")
        if not datos.casos_prueba:
            raise bad_request("Una pregunta de huecos necesita casos de prueba.")
    elif datos.tipo == "corregir_codigo":
        if not datos.codigo_plantilla or not datos.codigo_solucion:
            raise bad_request("La corrección de código necesita plantilla y solución.")
        if not datos.casos_prueba:
            raise bad_request("La corrección de código necesita casos de prueba.")
    elif datos.tipo == "tipo_test":
        if not datos.opciones or len(datos.opciones) < 2:
            raise bad_request("Una pregunta tipo test necesita al menos dos opciones.")
        if datos.respuesta_correcta not in datos.opciones:
            raise bad_request("La respuesta correcta debe pertenecer a las opciones.")

    if datos.limites_caracteres is not None and any(
        limite < 1 or limite > 20_000 for limite in datos.limites_caracteres
    ):
        raise bad_request("Los límites deben estar entre 1 y 20000 caracteres.")


def _crear_modelo_pregunta(
    datos: DefinicionPreguntaDocente,
    *,
    examen_id: int,
    clave: str,
    version: int,
    profesor_id: int,
) -> Pregunta:
    pregunta = Pregunta(
        examen_id=examen_id,
        clave=clave,
        version=version,
        estado=datos.estado,
        tipo=datos.tipo,
        titulo=datos.titulo,
        enunciado=datos.enunciado,
        codigo_plantilla=datos.codigo_plantilla,
        codigo_solucion=datos.codigo_solucion,
        opciones_json=(
            json.dumps(datos.opciones, ensure_ascii=False)
            if datos.opciones is not None
            else None
        ),
        respuesta_correcta=datos.respuesta_correcta,
        limites_caracteres_json=(
            json.dumps(datos.limites_caracteres)
            if datos.limites_caracteres is not None
            else None
        ),
        orden=datos.orden,
        peso=datos.peso,
        creada_por_id=profesor_id,
    )
    pregunta.casos_prueba = [
        CasoPrueba(
            descripcion=caso.descripcion,
            codigo_test=caso.codigo_test,
            salida_esperada=caso.salida_esperada,
            peso=caso.peso,
            visible=caso.visible,
        )
        for caso in datos.casos_prueba
    ]
    return pregunta


def fecha_publica(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC).isoformat().replace("+00:00", "Z")


@router.get("/examenes", response_model=list[ExamenDocente])
def listar_examenes(
    _: UsuarioPermitido = Depends(exigir_rol("profesor")),
    db: Session = Depends(get_db),
) -> list[ExamenDocente]:
    examenes = db.scalars(select(Examen).order_by(Examen.id.desc())).all()
    return [_examen_docente(examen) for examen in examenes]


@router.get(
    "/examenes/{examen_id}/versiones", response_model=list[VersionExamenDocente]
)
def listar_versiones_examen(
    examen_id: int,
    _: UsuarioPermitido = Depends(exigir_rol("profesor")),
    db: Session = Depends(get_db),
) -> list[VersionExamenDocente]:
    if db.get(Examen, examen_id) is None:
        raise not_found("El examen solicitado no existe.")
    versiones = db.scalars(
        select(VersionExamen)
        .where(VersionExamen.examen_id == examen_id)
        .order_by(VersionExamen.version)
    ).all()
    return [
        VersionExamenDocente(
            version=version.version,
            configuracion=json.loads(version.configuracion_json),
            creada_por_id=version.creada_por_id,
            creada_en=version.creada_en,
        )
        for version in versiones
    ]


@router.post(
    "/examenes/{examen_id}/versiones", response_model=ExamenDocente, status_code=201
)
def versionar_configuracion_examen(
    examen_id: int,
    datos: ConfiguracionExamenActualizar,
    profesor: UsuarioPermitido = Depends(exigir_rol("profesor")),
    db: Session = Depends(get_db),
) -> ExamenDocente:
    examen = db.get(Examen, examen_id)
    if examen is None:
        raise not_found("El examen solicitado no existe.")
    apertura, cierre = _validar_configuracion_examen(db, examen, datos)
    _anadir_instantanea_examen(db, examen, profesor.id)

    examen.version += 1
    examen.titulo = datos.titulo
    examen.descripcion = datos.descripcion
    examen.duracion_segundos = datos.duracion_segundos
    examen.estado = datos.estado
    examen.activo = datos.estado == "publicado"
    examen.modo_calificacion = datos.modo_calificacion
    examen.seleccion_json = json.dumps(datos.seleccion_por_tipo, ensure_ascii=False)
    examen.apertura_en = apertura
    examen.cierre_en = cierre
    _anadir_instantanea_examen(db, examen, profesor.id)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("No se pudo crear la versión del examen.") from exc
    db.refresh(examen)
    return _examen_docente(examen)


@router.get("/preguntas", response_model=list[PreguntaDocente])
def listar_preguntas(
    tipo: TipoPregunta | None = None,
    estado: EstadoPregunta | None = None,
    _: UsuarioPermitido = Depends(exigir_rol("profesor")),
    db: Session = Depends(get_db),
) -> list[PreguntaDocente]:
    consulta = select(Pregunta).options(joinedload(Pregunta.casos_prueba))
    if tipo is not None:
        consulta = consulta.where(Pregunta.tipo == tipo)
    if estado is not None:
        consulta = consulta.where(Pregunta.estado == estado)
    consulta = consulta.order_by(Pregunta.clave, Pregunta.version.desc())
    preguntas = db.execute(consulta).unique().scalars().all()
    return [_pregunta_docente(pregunta) for pregunta in preguntas]


@router.get("/preguntas/{pregunta_id}", response_model=PreguntaDocente)
def obtener_pregunta(
    pregunta_id: int,
    _: UsuarioPermitido = Depends(exigir_rol("profesor")),
    db: Session = Depends(get_db),
) -> PreguntaDocente:
    pregunta = db.scalar(
        select(Pregunta)
        .where(Pregunta.id == pregunta_id)
        .options(joinedload(Pregunta.casos_prueba))
    )
    if pregunta is None:
        raise not_found("La pregunta solicitada no existe.")
    return _pregunta_docente(pregunta)


@router.post("/preguntas", response_model=PreguntaDocente, status_code=201)
def crear_pregunta(
    datos: PreguntaCrear,
    profesor: UsuarioPermitido = Depends(exigir_rol("profesor")),
    db: Session = Depends(get_db),
) -> PreguntaDocente:
    _validar_definicion_pregunta(datos)
    if db.get(Examen, datos.examen_id) is None:
        raise not_found("El examen indicado no existe.")
    if db.scalar(select(Pregunta.id).where(Pregunta.clave == datos.clave)):
        raise conflict("Ya existe una pregunta con esa clave.")

    pregunta = _crear_modelo_pregunta(
        datos,
        examen_id=datos.examen_id,
        clave=datos.clave,
        version=1,
        profesor_id=profesor.id,
    )
    db.add(pregunta)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict(
            "No se pudo crear la pregunta por un conflicto de datos."
        ) from exc
    db.refresh(pregunta)
    return _pregunta_docente(pregunta)


@router.post(
    "/preguntas/{pregunta_id}/versiones",
    response_model=PreguntaDocente,
    status_code=201,
)
def crear_version_pregunta(
    pregunta_id: int,
    datos: PreguntaVersionar,
    profesor: UsuarioPermitido = Depends(exigir_rol("profesor")),
    db: Session = Depends(get_db),
) -> PreguntaDocente:
    _validar_definicion_pregunta(datos)
    anterior = db.get(Pregunta, pregunta_id)
    if anterior is None:
        raise not_found("La pregunta que quieres versionar no existe.")
    ultima_version = db.scalar(
        select(func.max(Pregunta.version)).where(Pregunta.clave == anterior.clave)
    )
    nueva = _crear_modelo_pregunta(
        datos,
        examen_id=anterior.examen_id,
        clave=anterior.clave,
        version=int(ultima_version or 0) + 1,
        profesor_id=profesor.id,
    )
    versiones_anteriores = db.scalars(
        select(Pregunta).where(Pregunta.clave == anterior.clave)
    ).all()
    for version_anterior in versiones_anteriores:
        version_anterior.estado = "retirada"
    db.add(nueva)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("No se pudo crear la nueva versión.") from exc
    db.refresh(nueva)
    return _pregunta_docente(nueva)


@router.post("/preguntas/{pregunta_id}/estado", response_model=PreguntaDocente)
def actualizar_estado_pregunta(
    pregunta_id: int,
    datos: EstadoPreguntaActualizar,
    _: UsuarioPermitido = Depends(exigir_rol("profesor")),
    db: Session = Depends(get_db),
) -> PreguntaDocente:
    pregunta = db.get(Pregunta, pregunta_id)
    if pregunta is None:
        raise not_found("La pregunta solicitada no existe.")
    if datos.estado == "publicada":
        otras_versiones = db.scalars(
            select(Pregunta).where(
                Pregunta.clave == pregunta.clave,
                Pregunta.id != pregunta.id,
            )
        ).all()
        for otra_version in otras_versiones:
            otra_version.estado = "retirada"
    pregunta.estado = datos.estado
    db.commit()
    db.refresh(pregunta)
    return _pregunta_docente(pregunta)


def entrega_profesor(entrega: Entrega) -> EntregaProfesor:
    eventos = [
        EventoProfesor(
            id=evento.id,
            tipo=evento.tipo,
            timestamp_cliente=evento.timestamp_cliente,
            registrado_en=fecha_publica(evento.registrado_en) or "",
            evidencias=[evidencia.id for evidencia in evento.evidencias],
        )
        for evento in sorted(entrega.eventos, key=lambda item: item.registrado_en)
    ]
    return EntregaProfesor(
        entrega_id=entrega.id,
        alumno=f"{entrega.alumno.nombre} {entrega.alumno.apellidos}".strip(),
        correo=entrega.alumno.correo,
        examen=entrega.titulo_examen or entrega.examen.titulo,
        nota_global=entrega.calificacion.nota_global if entrega.calificacion else None,
        preguntas_pendientes=(
            entrega.calificacion.preguntas_pendientes if entrega.calificacion else 0
        ),
        cerrada=entrega.cerrada,
        hora_inicio=fecha_publica(entrega.hora_inicio) or "",
        hora_entrega=fecha_publica(entrega.hora_entrega),
        eventos=eventos,
    )


@router.get("/entregas", response_model=list[EntregaProfesor])
def listar_entregas(
    _: UsuarioPermitido = Depends(exigir_rol("profesor")),
    db: Session = Depends(get_db),
) -> list[EntregaProfesor]:
    return [entrega_profesor(entrega) for entrega in listar_entregas_para_profesor(db)]


@router.get("/evidencias/{evidencia_id}")
def descargar_evidencia(
    evidencia_id: int,
    _: UsuarioPermitido = Depends(exigir_rol("profesor")),
    db: Session = Depends(get_db),
) -> Response:
    evidencia = obtener_evidencia(db, evidencia_id)
    if evidencia is None:
        raise not_found("La evidencia solicitada no existe.")
    return Response(
        content=evidencia.contenido,
        media_type=evidencia.mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{evidencia.nombre_archivo}"'
        },
    )


@router.get("/exportar")
def exportar_csv(
    _: UsuarioPermitido = Depends(exigir_rol("profesor")),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "entrega_id",
            "alumno",
            "correo",
            "examen",
            "nota_global",
            "preguntas_pendientes",
            "cerrada",
            "eventos",
            "evidencias",
        ]
    )

    for entrega in listar_entregas_para_profesor(db):
        eventos = "|".join(evento.tipo for evento in entrega.eventos)
        evidencias = sum(len(evento.evidencias) for evento in entrega.eventos)
        writer.writerow(
            [
                entrega.id,
                f"{entrega.alumno.nombre} {entrega.alumno.apellidos}".strip(),
                entrega.alumno.correo,
                entrega.titulo_examen or entrega.examen.titulo,
                entrega.calificacion.nota_global if entrega.calificacion else "",
                entrega.calificacion.preguntas_pendientes
                if entrega.calificacion
                else "",
                entrega.cerrada,
                eventos,
                evidencias,
            ]
        )

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="entregas_tfg.csv"'},
    )
