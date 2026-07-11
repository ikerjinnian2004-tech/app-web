# Evaluador web de ejercicios Python

Prototipo web para evaluar ejercicios de Python en un contexto universitario. La
aplicacion permite acceso separado de alumnos y profesores mediante correos
institucionales incluidos en una semilla inicial, carga un examen activo y corrige de
forma determinista las preguntas que lo permiten.

El alcance actual prioriza claridad y reproducibilidad: backend FastAPI, persistencia
SQLAlchemy sobre SQLite en desarrollo y PostgreSQL en Docker, frontend HTML/CSS/JS
nativo y sandbox configurable para ejecutar codigo de alumno.

## Requisitos

- Python 3.11 o superior
- pip
- Docker y Docker Compose, opcionales para PostgreSQL y despliegue local

## Instalacion local

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edita `.env` y cambia `SECRET_KEY` e `IDENTITY_HMAC_KEY`.

## Datos iniciales

Los usuarios autorizados, el examen de ejemplo y las preguntas estan en
`backend/data/datos_iniciales.json`. El texto que acepta el alumno antes de iniciar la
prueba esta en `backend/data/consentimiento-grabacion.md`.

```powershell
python scripts/reset_db.py
python backend/data/seed_questions.py
```

## Ejecucion

```powershell
python -m uvicorn backend.main:app --reload
```

En otra terminal:

```powershell
Set-Location frontend
python -m http.server 5500
```

- Aplicacion: `http://127.0.0.1:5500/index.html`
- API interactiva: `http://127.0.0.1:8000/docs`

Usuarios de demo:

- Alumno: `ana.garcia@alu.uclm.es`
- Profesor: `david.munoz@uclm.es`

## Flujo principal

1. El usuario elige rol e introduce correo institucional.
2. El backend valida dominio y presencia en la semilla inicial.
3. El alumno acepta el consentimiento de grabacion y se crea la entrega.
4. El examen muestra preguntas de rellenar huecos, corregir codigo, tipo test y
   respuesta corta.
5. El backend corrige automaticamente las preguntas deterministas y marca las
   respuestas cortas como pendientes de revision docente.
6. Los eventos de cambio de pestana o perdida de foco quedan registrados. Si hay
   consentimiento, el navegador puede adjuntar una evidencia breve en WebM.
7. El profesor revisa entregas, eventos, evidencias y exporta CSV desde el panel.

## API principal

- `POST /auth/acceder`
- `GET /consentimiento`
- `POST /examen/iniciar`
- `POST /entregas/enviar`
- `GET /entregas/{entrega_id}/resultado`
- `POST /auditoria/eventos`
- `POST /auditoria/evidencias`
- `GET /profesor/entregas`
- `GET /profesor/evidencias/{evidencia_id}`
- `GET /profesor/exportar`

## Tests y comprobaciones

```powershell
python -m compileall backend tests
python -m pytest -q
python scripts/simular_flujo_demo.py
python -m ruff check .
python -m black --check .
docker compose config
```

La suite cubre autenticacion por rol, validacion de semilla/dominio, consentimiento,
flujo mixto de preguntas, auditoria, subida de evidencias, panel docente, motor de
plantillas, sandbox y configuracion de base de datos.

## Docker

```powershell
docker compose up -d db
docker compose up -d backend frontend
docker compose exec backend python scripts/reset_db.py
docker compose exec backend python backend/data/seed_questions.py
```

Con Docker Compose, el backend usa PostgreSQL y el frontend queda publicado en
`http://127.0.0.1:5500`.

## Seguridad y limitaciones

- El runner local por `subprocess` es util para desarrollo, pero no equivale a un
  aislamiento fuerte.
- Para un entorno compartido debe activarse `SANDBOX_USE_DOCKER=true` y revisar la
  configuracion del contenedor.
- Las evidencias dependen de permisos del navegador; si se deniegan, se conserva solo
  el evento de auditoria.
- No hay SSO real ni contrasenas: el prototipo usa listas semilla de correos.
- No se incluyen migraciones Alembic; `scripts/reset_db.py` recrea el esquema.
