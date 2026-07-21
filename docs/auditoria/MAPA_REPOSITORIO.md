# Mapa del repositorio

## Identificación de la inspección inicial

- Fecha de inspección: 2026-07-21 (Europe/Madrid).
- Referencia oficial reconciliada: `origin/main` en
  `37a61f759a6beca19ae8797fb91bf7c3210aad75`.
- Copia local original: `main` en
  `36235b54786e86891250973881483290bae15380`, con cambios sin confirmar y un
  commit por detrás de la referencia oficial.
- Rama candidata: `cierre-tfg-2026`, creada desde una clonación limpia oficial.
- Regla de conservación: los ZIP, PDF, bases, evidencias y `.git` auxiliares se
  mantuvieron fuera de la rama candidata.
- `AGENTS.md`: no existe en esta copia.

## Arquitectura y riesgos del snapshot previo al endurecimiento

| Área | Archivos principales | Responsabilidad real | Riesgo observado |
| --- | --- | --- | --- |
| Arranque y configuración | `backend/main.py`, `backend/config.py` | Carga de ajustes, CORS, cabeceras, esquema y salud | No distingue de forma explícita desarrollo, pruebas y producción |
| Persistencia | `backend/database.py`, `backend/models.py`, `backend/migraciones.py` | Engine SQLAlchemy, sesiones, modelos y seis migraciones ligeras | Las migraciones no tienen downgrade y faltan invariantes concurrentes |
| CRUD | `backend/crud.py` | Consultas y persistencia de usuarios, entregas, notas, eventos y evidencias | Los auxiliares confirman transacciones parciales con `commit()` |
| Inicio del examen | `backend/routers/exam.py` | Consentimiento, elección de examen y creación/reanudación | Patrón buscar-después-crear sin restricción única |
| Envío | `backend/routers/submission.py` | Validación temporal, reserva, corrección y cierre | Respuestas, nota y cierre se confirman por separado |
| Corrección | `backend/grader.py`, `backend/template_engine.py` | Construcción de programas, ejecución de casos y desglose | Depende del runner configurado y no conserva diagnóstico operacional completo |
| Sandbox | `backend/sandbox/` | Política AST y runners local/Docker | Docker tiene pruebas de contrato; el runner local no es frontera de producción |
| Identidad | `backend/routers/auth.py`, `backend/security.py`, `backend/datos_iniciales.py` | Lista sembrada, JWT y roles | El acceso de demostración no está deshabilitado por modo de despliegue |
| Auditoría | `backend/routers/audit.py` | Eventos y blobs multimedia en base de datos | Valida MIME declarado, no contenido; no hay retención ni auditoría de descarga |
| Docencia | `backend/routers/admin.py` | Catálogo, versiones, revisión, estadísticas, exportación y descarga | Varias operaciones controlan su propio commit; debe conservarse el contrato público |
| Frontend | `frontend/` | Acceso, examen, resultado, auditoría y panel sin compilación | No existe autosalvado autoritativo; se piden permisos nuevos al ocurrir el evento |
| Pruebas | `tests/` | 85 pruebas históricas de unidad/integración local | La copia actual no tiene dependencias instaladas; Docker/PostgreSQL/navegador no están cubiertos de forma real |
| Automatización | `.github/workflows/ci.yml`, `scripts/` | Calidad, pruebas SQLite, reset/seed y simulación | CI no separa PostgreSQL, Docker real, navegador, cobertura y evidencias |
| Contenedores | `Dockerfile.*`, `docker-compose.yml` | Backend, sandbox, PostgreSQL y frontend | Imágenes por etiqueta mutable; sandbox desactivado en el ejemplo |

## Contratos públicos que se conservarán

- Rutas actuales bajo `/auth`, `/examen`, `/entregas`, `/auditoria` y `/profesor`.
- Campos ya consumidos por el frontend, especialmente `entrega_id`, `preguntas`,
  `nota_global`, `preguntas_pendientes` y `desglose`.
- Cuatro tipos de pregunta y selección configurada por el backend.
- Roles `alumno` y `profesor` en la API; redacción inclusiva «Alumnado» y
  «Profesorado» en la interfaz.
- Identidades de demostración para desarrollo y pruebas, pero no para producción.
- Flujo `scripts/reset_db.py`, `backend/data/seed_questions.py` y
  `scripts/simular_flujo_demo.py`.

## Defectos confirmados en el código inicial

1. `guardar_respuestas()`, `guardar_calificacion()` y `cerrar_entrega()` realizan
   commits independientes; la reserva no puede revertirlos.
2. `iniciar_examen()` consulta la última entrega y después inserta sin una
   restricción única equivalente a alumno + examen.
3. La reserva usa solo un booleano y una fecha; no identifica al propietario.
4. No existe entidad, ruta ni contrato frontend para borradores.
5. `SANDBOX_USE_DOCKER=false` es válido para cualquier entorno y no hay fallo
   seguro de arranque productivo.
6. El adaptador Docker mezcla `stdout` y `stderr`, no fija `ulimit` de archivos y
   no expone identificador, imagen efectiva ni motivo de terminación.
7. La captura multimedia solicita nuevos permisos desde eventos de pérdida de foco,
   en vez de mantener flujos previamente autorizados.
8. El nombre de archivo se normaliza, pero el contenido se acepta según MIME
   declarado y se conserva indefinidamente en la base de datos.
9. La CI solo ejecuta calidad, suite SQLite y pruebas del sandbox con dobles.

## Baseline del entorno antes de instalar dependencias

| Comprobación | Resultado | Categoría |
| --- | --- | --- |
| Python | 3.11.9 | IMPLEMENTADO Y EJECUTADO |
| Node.js | 24.18.0 | IMPLEMENTADO Y EJECUTADO |
| Git | 2.53.0.windows.1 | IMPLEMENTADO Y EJECUTADO |
| Docker CLI | 29.5.3 | IMPLEMENTADO Y EJECUTADO |
| Docker Compose | 5.1.4 | IMPLEMENTADO Y EJECUTADO |
| Docker daemon | No disponible en el contexto `default` | BLOQUEADO |
| `python -m pytest -q` | No se pudo iniciar: falta `pytest` | BLOQUEADO |
| Python incluido con Codex | Tampoco contiene `pytest` ni `ruff` | BLOQUEADO |

Este baseline describe el entorno, no la calidad del código. El plan crea un entorno
aislado, vuelve a ejecutar las comprobaciones y conserva las salidas completas.

## Comandos de verificación descubiertos

```text
python -m compileall -q backend scripts tests
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python -m pip check
python scripts/reset_db.py
python backend/data/seed_questions.py
python scripts/simular_flujo_demo.py
docker compose config --quiet
```
