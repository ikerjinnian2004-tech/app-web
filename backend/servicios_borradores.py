from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.models import BorradorRespuesta, Entrega, PreguntaAsignada


class BorradorNoEncontrado(RuntimeError):
    pass


class BorradorNoAutorizado(RuntimeError):
    pass


class BorradorNoDisponible(RuntimeError):
    pass


class ConflictoVersionBorrador(RuntimeError):
    pass


def _validar_entrega(
    entrega: Entrega | None, alumno_id: int, ahora: datetime
) -> Entrega:
    if entrega is None:
        raise BorradorNoEncontrado("La entrega no existe.")
    if entrega.alumno_id != alumno_id:
        raise BorradorNoAutorizado("No puedes acceder a borradores de otra persona.")
    if entrega.cerrada:
        raise BorradorNoDisponible("La entrega ya está cerrada.")
    limite = entrega.hora_inicio + timedelta(seconds=entrega.duracion_examen_segundos)
    if ahora > limite:
        raise BorradorNoDisponible(
            "El tiempo del intento ha terminado; el borrador no se ha guardado."
        )
    return entrega


def listar_borradores(
    db: Session, entrega_id: int, alumno_id: int, ahora: datetime
) -> list[BorradorRespuesta]:
    entrega = db.scalar(select(Entrega).where(Entrega.id == entrega_id))
    _validar_entrega(entrega, alumno_id, ahora)
    return list(
        db.scalars(
            select(BorradorRespuesta)
            .join(
                PreguntaAsignada,
                and_(
                    PreguntaAsignada.entrega_id == BorradorRespuesta.entrega_id,
                    PreguntaAsignada.pregunta_id == BorradorRespuesta.pregunta_id,
                ),
            )
            .where(BorradorRespuesta.entrega_id == entrega_id)
            .order_by(PreguntaAsignada.orden.asc())
        )
    )


def guardar_borrador(
    db: Session,
    *,
    entrega_id: int,
    alumno_id: int,
    pregunta_id: int,
    contenido: str,
    version_esperada: int,
    ahora: datetime,
) -> BorradorRespuesta:
    if db.in_transaction():
        db.rollback()
    try:
        with db.begin():
            entrega = db.scalar(
                select(Entrega).where(Entrega.id == entrega_id).with_for_update()
            )
            _validar_entrega(entrega, alumno_id, ahora)
            asignada = db.scalar(
                select(PreguntaAsignada.id).where(
                    PreguntaAsignada.entrega_id == entrega_id,
                    PreguntaAsignada.pregunta_id == pregunta_id,
                )
            )
            if asignada is None:
                raise BorradorNoDisponible("La pregunta no pertenece a esta entrega.")

            borrador = db.scalar(
                select(BorradorRespuesta).where(
                    BorradorRespuesta.entrega_id == entrega_id,
                    BorradorRespuesta.pregunta_id == pregunta_id,
                )
            )
            if borrador is None:
                if version_esperada != 0:
                    raise ConflictoVersionBorrador(
                        "El borrador no existe con la versión indicada."
                    )
                borrador = BorradorRespuesta(
                    entrega_id=entrega_id,
                    pregunta_id=pregunta_id,
                    contenido=contenido,
                    version=1,
                    actualizado_en=ahora,
                )
                db.add(borrador)
            else:
                if borrador.version != version_esperada:
                    raise ConflictoVersionBorrador(
                        "El borrador fue modificado en otra pestaña o sesión; "
                        f"la versión actual es {borrador.version}."
                    )
                borrador.contenido = contenido
                borrador.version += 1
                borrador.actualizado_en = ahora
            db.flush()
    except IntegrityError as exc:
        raise ConflictoVersionBorrador(
            "Otra petición creó o actualizó el borrador simultáneamente."
        ) from exc
    db.refresh(borrador)
    return borrador
