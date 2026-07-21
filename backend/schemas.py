from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

RolUsuario = Literal["alumno", "profesor"]
EstadoPregunta = Literal["borrador", "publicada", "retirada"]
EstadoExamen = Literal["borrador", "publicado", "archivado"]
ModoCalificacion = Literal["parcial_por_tests", "todo_o_nada_por_pregunta"]
EstadoEntregaFiltro = Literal["abierta", "pendiente", "corregida"]
TipoPregunta = Literal[
    "rellenar_huecos",
    "corregir_codigo",
    "tipo_test",
    "respuesta_corta",
]


class AccesoRequest(BaseModel):
    rol: RolUsuario
    correo_institucional: EmailStr

    model_config = ConfigDict(str_strip_whitespace=True)


class AccesoResponse(BaseModel):
    token: str
    rol: RolUsuario
    nombre: str
    correo: str


class ConsentimientoResponse(BaseModel):
    texto: str
    version: str


class IniciarExamenRequest(BaseModel):
    consentimiento_version: str = Field(min_length=16, max_length=64)
    acepta_grabacion: bool
    permisos_evidencia_verificados: bool


class PreguntaExamen(BaseModel):
    id: int
    clave: str
    version: int
    tipo: TipoPregunta
    titulo: str
    enunciado: str
    codigo_plantilla: str | None = None
    opciones: list[str] | None = None
    numero_huecos: int = 0
    limites_caracteres: list[int] | None = None
    peso: float
    orden: int

    model_config = ConfigDict(from_attributes=True)


class ExamenResponse(BaseModel):
    examen_id: int
    entrega_id: int
    titulo: str
    duracion_segundos: int
    hora_inicio_servidor: str
    hora_actual_servidor: str
    hora_limite_servidor: str
    preguntas: list[PreguntaExamen]


class BorradorGuardarRequest(BaseModel):
    pregunta_id: int = Field(gt=0)
    contenido: str = Field(max_length=20_000)
    version_esperada: int = Field(default=0, ge=0)


class BorradorResponse(BaseModel):
    entrega_id: int
    pregunta_id: int
    contenido: str
    version: int
    actualizado_en: datetime

    model_config = ConfigDict(from_attributes=True)


class RespuestaItem(BaseModel):
    pregunta_id: int
    contenido: str = Field(max_length=20_000)


class SubmissionCreate(BaseModel):
    entrega_id: int
    respuestas: list[RespuestaItem] = Field(min_length=1, max_length=100)
    entregado_automaticamente: bool = False


class DesglosePregunta(BaseModel):
    pregunta_id: int
    tipo: TipoPregunta
    estado: Literal["corregida", "pendiente_revision"]
    nota: float | None
    tests_ok: int | None = None
    tests_total: int | None = None
    error_type: str | None = None
    peso: float
    contribucion: float | None
    version_pregunta: int


class SubmissionResponse(BaseModel):
    entrega_id: int
    nota_global: float
    preguntas_pendientes: int
    desglose: list[DesglosePregunta]


class AuditEventCreate(BaseModel):
    tipo: Literal[
        "CAMBIO_PESTANA",
        "PERDIDA_FOCO",
        "VENTANA_RECUPERADA",
        "ENVIO_MANUAL",
        "ENVIO_TIEMPO",
        "EVIDENCIA_DENEGADA",
    ]
    timestamp_cliente: str = Field(min_length=10, max_length=50)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("metadata")
    @classmethod
    def limitar_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        serializado = json.dumps(value, ensure_ascii=False)
        if len(serializado) > 5_000:
            raise ValueError("Los metadatos superan 5000 caracteres.")
        return value


class AuditEventResponse(BaseModel):
    ok: bool
    evento_id: int
    grabar_evidencia: bool


class EvidenciaResponse(BaseModel):
    ok: bool
    evidencia_id: int


class EventoProfesor(BaseModel):
    id: int
    tipo: str
    timestamp_cliente: str
    registrado_en: str
    evidencias: list[int]


class EntregaProfesor(BaseModel):
    entrega_id: int
    alumno: str
    correo: str
    examen: str
    nota_global: float | None
    preguntas_pendientes: int
    cerrada: bool
    hora_inicio: str
    hora_entrega: str | None
    eventos: list[EventoProfesor]


class EntregaDetalleProfesor(EntregaProfesor):
    examen_id: int
    version_examen: int
    modo_calificacion: ModoCalificacion
    entregado_automaticamente: bool
    consentimiento_version: str
    acepta_grabacion: bool
    permisos_evidencia_verificados: bool
    preguntas: list[dict[str, Any]]
    desglose: list[dict[str, Any]]
    eventos_detalle: list[dict[str, Any]]


class EstadisticasProfesor(BaseModel):
    total_entregas: int
    abiertas: int
    corregidas: int
    pendientes_revision: int
    nota_media: float | None


class CasoPruebaDocente(BaseModel):
    id: int | None = None
    descripcion: str = Field(min_length=1, max_length=200)
    codigo_test: str = Field(min_length=1, max_length=20_000)
    salida_esperada: str = Field(default="", max_length=10_000)
    peso: float = Field(default=1.0, gt=0, le=100)
    visible: bool = False

    model_config = ConfigDict(str_strip_whitespace=True)


class DefinicionPreguntaDocente(BaseModel):
    tipo: TipoPregunta
    titulo: str = Field(min_length=1, max_length=200)
    enunciado: str = Field(min_length=1, max_length=20_000)
    codigo_plantilla: str | None = Field(default=None, max_length=20_000)
    codigo_solucion: str | None = Field(default=None, max_length=20_000)
    opciones: list[str] | None = Field(default=None, max_length=20)
    respuesta_correcta: str | None = Field(default=None, max_length=20_000)
    limites_caracteres: list[int] | None = None
    orden: int = Field(ge=1)
    peso: float = Field(gt=0, le=100)
    estado: EstadoPregunta = "borrador"
    casos_prueba: list[CasoPruebaDocente] = Field(default_factory=list, max_length=50)

    model_config = ConfigDict(str_strip_whitespace=True)


class PreguntaCrear(DefinicionPreguntaDocente):
    examen_id: int = Field(gt=0)
    clave: str = Field(
        min_length=3,
        max_length=100,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )


class PreguntaVersionar(DefinicionPreguntaDocente):
    pass


class EstadoPreguntaActualizar(BaseModel):
    estado: EstadoPregunta


class PreguntaDocente(DefinicionPreguntaDocente):
    id: int
    examen_id: int
    clave: str
    version: int
    creada_por_id: int | None

    model_config = ConfigDict(from_attributes=True)


class ConfiguracionExamenActualizar(BaseModel):
    titulo: str = Field(min_length=1, max_length=200)
    descripcion: str = Field(default="", max_length=20_000)
    duracion_segundos: int = Field(ge=60, le=28_800)
    estado: EstadoExamen
    modo_calificacion: ModoCalificacion
    seleccion_por_tipo: dict[TipoPregunta, int]
    apertura_en: datetime | None = None
    cierre_en: datetime | None = None

    model_config = ConfigDict(str_strip_whitespace=True)


class ExamenDocente(ConfiguracionExamenActualizar):
    id: int
    version: int
    activo: bool
    profesor_id: int | None


class VersionExamenDocente(BaseModel):
    version: int
    configuracion: dict[str, Any]
    creada_por_id: int | None
    creada_en: datetime


class RevisionManualCrear(BaseModel):
    nota: float = Field(ge=0, le=10)
    comentario: str = Field(default="", max_length=10_000)

    model_config = ConfigDict(str_strip_whitespace=True)


class CalificacionDocente(BaseModel):
    entrega_id: int
    nota_global: float
    preguntas_pendientes: int
    desglose: list[dict[str, Any]]


class HealthResponse(BaseModel):
    status: str
    db: str
    version: str

    model_config = ConfigDict(from_attributes=True)
