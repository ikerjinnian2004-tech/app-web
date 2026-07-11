# Informe de revision

## 1. Resumen ejecutivo

- Archivos revisados: backend, frontend, scripts, tests, configuracion Docker, README y PDF de memoria como referencia funcional.
- Archivos modificados: modelos, esquemas, seguridad, routers, corrector, semillas, frontend completo, tests, scripts, README, `.env.example`, `.env` local y `docker-compose.yml`.
- Archivos residuales eliminados: documentacion tecnica antigua de `docs/`, caches Python/Ruff/Pytest, `test_runtime.db`, scripts antiguos de carga/concurrencia y `limpieza-general.md`.
- Resultado general: prototipo reconstruido de forma conservadora, con menos piezas, API nueva por roles y flujo comprobable.

## 2. Cambios realizados

### Backend

- Se sustituyo el acceso antiguo por `POST /auth/acceder`, usando rol `alumno` o `profesor`, correo institucional y lista semilla.
- Se anadio `UsuarioPermitido`, tipos de pregunta, consentimiento por entrega, eventos de auditoria y evidencias BLOB asociadas al evento.
- Se reorganizaron rutas publicas: `/consentimiento`, `/examen/iniciar`, `/entregas/*`, `/auditoria/*` y `/profesor/*`.
- El corrector soporta `rellenar_huecos`, `corregir_codigo`, `tipo_test` y `respuesta_corta`; esta ultima queda como `pendiente_revision`.
- Se conserva el sandbox existente y se anade validacion estatica diferenciada para fragmentos y programas completos.

### Frontend

- Se redujo la interfaz a `index.html`, `examen.html`, `resultado.html` y `profesor.html`.
- Se unifico CSS en `frontend/css/style.css`.
- Se sustituyo el JS antiguo por modulos de dominio: API, sesion, acceso, examen, auditoria/evidencia, resultado y profesor.
- La evidencia real se graba con `MediaRecorder`, `getDisplayMedia` y `getUserMedia` cuando el backend lo solicita tras un evento.
- El panel docente lista entregas, notas, revision pendiente, eventos y evidencias descargables con token de profesor.

### Datos y scripts

- `backend/data/datos_iniciales.json` concentra usuarios autorizados y examen demo.
- `backend/data/consentimiento-grabacion.md` contiene el texto aceptado por el alumno.
- `scripts/reset_db.py` recrea el esquema.
- `scripts/simular_flujo_demo.py` resetea, siembra, envia una entrega y comprueba el panel docente.

### Documentacion

- `README.md` se actualizo con instalacion, datos iniciales, rutas nuevas, flujo, tests, Docker y limitaciones.
- Este archivo queda como informe unico de revision.
- Se retiro la documentacion antigua que describia endpoints obsoletos.

## 3. Decisiones conservadoras

- No se anadio framework frontend ni build step: HTML/CSS/JS nativo sigue siendo suficiente y reproducible.
- No se introdujo Alembic: el prototipo sigue usando recreacion de esquema para desarrollo.
- No se elimino el PDF de memoria ni configuracion Docker.
- Se mantiene `dev.db` local como base generada para probar rapidamente; puede recrearse con `scripts/reset_db.py` y `backend/data/seed_questions.py`.

## 4. Pendiente de revision humana

- Sustituir listas semilla por SSO real si el prototipo pasa a uso institucional.
- Revisar juridicamente el texto de consentimiento antes de pruebas reales con alumnos.
- Validar el flujo de permisos de camara, microfono y pantalla en los navegadores objetivo.
- Activar Docker sandbox en entornos compartidos; el runner local no es aislamiento fuerte.
- Incorporar migraciones si el esquema empieza a evolucionar con datos persistentes reales.

## 5. Comprobaciones ejecutadas

| Comando | Resultado | Observaciones |
| --- | --- | --- |
| `python -m compileall backend tests` | Correcto | Compila backend y tests. |
| `python -m pytest -q` | Correcto | `34 passed`, con una advertencia de `python_multipart` emitida por Starlette. |
| `python -m ruff check .` | Correcto | Sin incidencias. |
| `python -m ruff format --check backend tests scripts` | Correcto | `34 files already formatted`. |
| `python scripts/simular_flujo_demo.py` | Correcto | Nota `10.0`, una pregunta pendiente y una entrega visible para profesor. |
| `docker compose config` | Correcto | Compose valido; Docker mostro avisos de acceso a `C:\Users\usuario\.docker\config.json`. |
| `python -m black --check .` | No concluye | Agota tiempo incluso con `black --version`; se uso Ruff Format como comprobacion alternativa. |

## 6. Notas de mantenimiento

- Usuarios demo: `ana.garcia@alu.uclm.es` y `david.munoz@uclm.es`.
- Flujo local: resetear base, sembrar datos, levantar FastAPI y servir `frontend/` por HTTP.
- Las evidencias se guardan en base de datos para evitar carpetas de videos locales.
- Los eventos de auditoria no penalizan automaticamente; solo informan al profesor.
