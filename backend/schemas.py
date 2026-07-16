from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

RolUsuario = Literal["alumno", "profesor"]
EstadoPregunta = Literal["borrador", "publicada", "retirada"]
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
    preguntas: list[PreguntaExamen]


class RespuestaItem(BaseModel):
    pregunta_id: int
    contenido: str = Field(max_length=20_000)


class SubmissionCreate(BaseModel):
    entrega_id: int
    respuestas: list[RespuestaItem] = Field(min_length=1)
    entregado_automaticamente: bool = False


class DesglosePregunta(BaseModel):
    pregunta_id: int
    tipo: TipoPregunta
    estado: Literal["corregida", "pendiente_revision"]
    nota: float | None
    tests_ok: int | None = None
    tests_total: int | None = None
    error_type: str | None = None


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
    timestamp_cliente: str
    metadata: dict[str, Any] = Field(default_factory=dict)


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
    opciones: list[str] | None = None
    respuesta_correcta: str | None = Field(default=None, max_length=20_000)
    limites_caracteres: list[int] | None = None
    orden: int = Field(ge=1)
    peso: float = Field(gt=0, le=100)
    estado: EstadoPregunta = "borrador"
    casos_prueba: list[CasoPruebaDocente] = Field(default_factory=list)

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


class HealthResponse(BaseModel):
    status: str
    db: str
    version: str

    model_config = ConfigDict(from_attributes=True)
