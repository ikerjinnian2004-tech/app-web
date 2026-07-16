from __future__ import annotations

from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, LargeBinary
from sqlalchemy import String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


def utc_now() -> datetime:
    """Marca temporal UTC naive compatible con SQLite y PostgreSQL."""
    return datetime.now(UTC).replace(tzinfo=None)


class UsuarioPermitido(Base):
    """Persona autorizada a usar el prototipo como alumno o profesor."""

    __tablename__ = "usuarios_permitidos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    apellidos: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    correo: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )

    entregas: Mapped[list["Entrega"]] = relationship("Entrega", back_populates="alumno")
    eventos: Mapped[list["EventoAuditoria"]] = relationship(
        "EventoAuditoria", back_populates="usuario"
    )


class Examen(Base):
    """Examen activo o histórico preparado por el profesorado."""

    __tablename__ = "examenes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    descripcion: Mapped[str] = mapped_column(Text, nullable=False, default="")
    duracion_segundos: Mapped[int] = mapped_column(Integer, nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    estado: Mapped[str] = mapped_column(String(20), default="publicado", nullable=False)
    modo_calificacion: Mapped[str] = mapped_column(
        String(30), default="parcial_por_tests", nullable=False
    )
    seleccion_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    apertura_en: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    cierre_en: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    profesor_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("usuarios_permitidos.id"), nullable=True
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )

    preguntas: Mapped[list["Pregunta"]] = relationship(
        "Pregunta",
        back_populates="examen",
        cascade="all, delete-orphan",
    )
    entregas: Mapped[list["Entrega"]] = relationship("Entrega", back_populates="examen")
    versiones: Mapped[list["VersionExamen"]] = relationship(
        "VersionExamen",
        back_populates="examen",
        cascade="all, delete-orphan",
        order_by="VersionExamen.version",
    )


class VersionExamen(Base):
    """Instantánea auditable de una configuración publicada del examen."""

    __tablename__ = "versiones_examen"
    __table_args__ = (
        UniqueConstraint("examen_id", "version", name="uq_examen_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    examen_id: Mapped[int] = mapped_column(
        ForeignKey("examenes.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    configuracion_json: Mapped[str] = mapped_column(Text, nullable=False)
    creada_por_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("usuarios_permitidos.id"), nullable=True
    )
    creada_en: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )

    examen: Mapped["Examen"] = relationship("Examen", back_populates="versiones")


class Pregunta(Base):
    """Pregunta del examen con estrategia de corrección explícita."""

    __tablename__ = "preguntas"
    __table_args__ = (
        UniqueConstraint("clave", "version", name="uq_pregunta_clave_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    examen_id: Mapped[int] = mapped_column(
        ForeignKey("examenes.id", ondelete="CASCADE"), nullable=False
    )
    clave: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    estado: Mapped[str] = mapped_column(String(20), default="publicada", nullable=False)
    tipo: Mapped[str] = mapped_column(String(40), nullable=False)
    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    enunciado: Mapped[str] = mapped_column(Text, nullable=False)
    codigo_plantilla: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    codigo_solucion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    opciones_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    respuesta_correcta: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    limites_caracteres_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    orden: Mapped[int] = mapped_column(Integer, nullable=False)
    peso: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    creada_por_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("usuarios_permitidos.id"), nullable=True
    )

    examen: Mapped["Examen"] = relationship("Examen", back_populates="preguntas")
    casos_prueba: Mapped[list["CasoPrueba"]] = relationship(
        "CasoPrueba",
        back_populates="pregunta",
        cascade="all, delete-orphan",
    )
    respuestas_alumno: Mapped[list["RespuestaAlumno"]] = relationship(
        "RespuestaAlumno", back_populates="pregunta"
    )
    asignaciones: Mapped[list["PreguntaAsignada"]] = relationship(
        "PreguntaAsignada", back_populates="pregunta"
    )


class CasoPrueba(Base):
    """Caso determinista definido por el profesorado para preguntas de código."""

    __tablename__ = "casos_prueba"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pregunta_id: Mapped[int] = mapped_column(
        ForeignKey("preguntas.id", ondelete="CASCADE"), nullable=False
    )
    descripcion: Mapped[str] = mapped_column(String(200), nullable=False)
    codigo_test: Mapped[str] = mapped_column(Text, nullable=False)
    salida_esperada: Mapped[str] = mapped_column(Text, nullable=False, default="")
    peso: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    visible: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    pregunta: Mapped["Pregunta"] = relationship(
        "Pregunta", back_populates="casos_prueba"
    )


class Entrega(Base):
    """Intento de examen de un alumno."""

    __tablename__ = "entregas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alumno_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios_permitidos.id"), nullable=False
    )
    examen_id: Mapped[int] = mapped_column(ForeignKey("examenes.id"), nullable=False)
    version_examen: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    titulo_examen: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    duracion_examen_segundos: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    modo_calificacion: Mapped[str] = mapped_column(
        String(30), default="parcial_por_tests", nullable=False
    )
    hora_inicio: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    hora_entrega: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    consentimiento_version: Mapped[str] = mapped_column(String(64), nullable=False)
    acepta_grabacion: Mapped[bool] = mapped_column(Boolean, nullable=False)
    entregado_automaticamente: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    cerrada: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    alumno: Mapped["UsuarioPermitido"] = relationship(
        "UsuarioPermitido", back_populates="entregas"
    )
    examen: Mapped["Examen"] = relationship("Examen", back_populates="entregas")
    respuestas_alumno: Mapped[list["RespuestaAlumno"]] = relationship(
        "RespuestaAlumno",
        back_populates="entrega",
        cascade="all, delete-orphan",
    )
    preguntas_asignadas: Mapped[list["PreguntaAsignada"]] = relationship(
        "PreguntaAsignada",
        back_populates="entrega",
        cascade="all, delete-orphan",
        order_by="PreguntaAsignada.orden",
    )
    calificacion: Mapped[Optional["Calificacion"]] = relationship(
        "Calificacion",
        back_populates="entrega",
        uselist=False,
        cascade="all, delete-orphan",
    )
    eventos: Mapped[list["EventoAuditoria"]] = relationship(
        "EventoAuditoria",
        back_populates="entrega",
        cascade="all, delete-orphan",
    )


class PreguntaAsignada(Base):
    """Pregunta y peso fijados para una entrega concreta."""

    __tablename__ = "preguntas_asignadas"
    __table_args__ = (
        UniqueConstraint("entrega_id", "pregunta_id", name="uq_entrega_pregunta"),
        UniqueConstraint("entrega_id", "orden", name="uq_entrega_orden"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entrega_id: Mapped[int] = mapped_column(
        ForeignKey("entregas.id", ondelete="CASCADE"), nullable=False
    )
    pregunta_id: Mapped[int] = mapped_column(ForeignKey("preguntas.id"), nullable=False)
    orden: Mapped[int] = mapped_column(Integer, nullable=False)
    peso: Mapped[float] = mapped_column(Float, nullable=False)
    version_pregunta: Mapped[int] = mapped_column(Integer, nullable=False)

    entrega: Mapped["Entrega"] = relationship(
        "Entrega", back_populates="preguntas_asignadas"
    )
    pregunta: Mapped["Pregunta"] = relationship(
        "Pregunta", back_populates="asignaciones"
    )


class RespuestaAlumno(Base):
    """Respuesta enviada por el alumno para una pregunta concreta."""

    __tablename__ = "respuestas_alumno"
    __table_args__ = (
        UniqueConstraint("entrega_id", "pregunta_id", name="uq_respuesta_entrega"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entrega_id: Mapped[int] = mapped_column(
        ForeignKey("entregas.id", ondelete="CASCADE"), nullable=False
    )
    pregunta_id: Mapped[int] = mapped_column(ForeignKey("preguntas.id"), nullable=False)
    contenido: Mapped[str] = mapped_column(Text, nullable=False)

    entrega: Mapped["Entrega"] = relationship(
        "Entrega", back_populates="respuestas_alumno"
    )
    pregunta: Mapped["Pregunta"] = relationship(
        "Pregunta", back_populates="respuestas_alumno"
    )


class Calificacion(Base):
    """Resultado calculado para una entrega cerrada."""

    __tablename__ = "calificaciones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entrega_id: Mapped[int] = mapped_column(
        ForeignKey("entregas.id"), unique=True, nullable=False
    )
    nota_global: Mapped[float] = mapped_column(Float, nullable=False)
    preguntas_pendientes: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    desglose_json: Mapped[str] = mapped_column(Text, nullable=False)
    calculada_en: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )

    entrega: Mapped["Entrega"] = relationship("Entrega", back_populates="calificacion")


class EventoAuditoria(Base):
    """Evento de supervisión ligera observado durante el examen."""

    __tablename__ = "eventos_auditoria"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios_permitidos.id"), nullable=False
    )
    entrega_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("entregas.id", ondelete="CASCADE"),
        nullable=True,
    )
    tipo: Mapped[str] = mapped_column(String(60), nullable=False)
    timestamp_cliente: Mapped[str] = mapped_column(String(50), nullable=False)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False)
    registrado_en: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )

    usuario: Mapped["UsuarioPermitido"] = relationship(
        "UsuarioPermitido", back_populates="eventos"
    )
    entrega: Mapped[Optional["Entrega"]] = relationship(
        "Entrega", back_populates="eventos"
    )
    evidencias: Mapped[list["EvidenciaAuditoria"]] = relationship(
        "EvidenciaAuditoria",
        back_populates="evento",
        cascade="all, delete-orphan",
    )


class EvidenciaAuditoria(Base):
    """Archivo de evidencia asociado a un evento autorizado por el alumno."""

    __tablename__ = "evidencias_auditoria"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    evento_id: Mapped[int] = mapped_column(
        ForeignKey("eventos_auditoria.id", ondelete="CASCADE"), nullable=False
    )
    tipo: Mapped[str] = mapped_column(String(40), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    nombre_archivo: Mapped[str] = mapped_column(String(180), nullable=False)
    tamano_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    contenido: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    creada_en: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )

    evento: Mapped["EventoAuditoria"] = relationship(
        "EventoAuditoria", back_populates="evidencias"
    )
