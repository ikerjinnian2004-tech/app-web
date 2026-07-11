from __future__ import annotations

import csv
import io
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from backend.crud import listar_entregas_para_profesor, obtener_evidencia
from backend.database import get_db
from backend.errors import not_found
from backend.models import Entrega, UsuarioPermitido
from backend.schemas import EntregaProfesor, EventoProfesor
from backend.security import exigir_rol

router = APIRouter()


def fecha_publica(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC).isoformat().replace("+00:00", "Z")


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
        examen=entrega.examen.titulo,
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
                entrega.examen.titulo,
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
