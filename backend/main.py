from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.database import check_db_health, create_tables
from backend.datos_iniciales import (
    obtener_texto_consentimiento,
    obtener_version_consentimiento,
)
from backend.logging_config import setup_logging
from backend.routers import admin, audit, auth, exam, submission
from backend.schemas import ConsentimientoResponse, HealthResponse

settings = get_settings()
logger = logging.getLogger(__name__)
APP_VERSION = "2.0.0"


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging(settings.log_level)
    create_tables()
    logger.info("Base de datos lista")
    yield


app = FastAPI(
    title="Evaluador Automático de Python",
    version=APP_VERSION,
    description="Prototipo TFG para evaluación docente de ejercicios de Python.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(exam.router, prefix="/examen", tags=["examen"])
app.include_router(submission.router, prefix="/entregas", tags=["entregas"])
app.include_router(audit.router, prefix="/auditoria", tags=["auditoria"])
app.include_router(admin.router, prefix="/profesor", tags=["profesor"])


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "evaluador-python", "status": "ok", "docs": "/docs"}


@app.get("/consentimiento", response_model=ConsentimientoResponse)
def consentimiento() -> ConsentimientoResponse:
    return ConsentimientoResponse(
        texto=obtener_texto_consentimiento(),
        version=obtener_version_consentimiento(),
    )


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    db_ok = await check_db_health()
    return HealthResponse(
        status="ok" if db_ok else "degraded",
        db="ok" if db_ok else "error",
        version=APP_VERSION,
    )
