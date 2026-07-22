# Evaluador web de ejercicios de Python

Prototipo de Trabajo Fin de Grado para crear, realizar y revisar pruebas de
programación. La aplicación combina un backend FastAPI, persistencia SQLAlchemy y
un frontend nativo HTML/CSS/JavaScript. La calificación automática es determinista;
las respuestas abiertas quedan pendientes de revisión docente.

## Funcionalidad incluida

- Acceso por rol y lista institucional de usuarios autorizados.
- Consentimiento y comprobación obligatoria de permisos de pantalla, cámara y
  micrófono antes de iniciar un intento de alumnado.
- Banco con preguntas de rellenar huecos, corregir código, tipo test y
  respuesta corta.
- Selección aleatoria por tipo y congelación de pregunta, versión y peso en cada
  intento.
- Configuración versionada de título, duración, ventana temporal y modo de
  calificación.
- Corrección por casos visibles y ocultos, con modos parcial o todo o nada.
- Auditoría de eventos y evidencias WebM asociadas, sin penalización automática.
- Panel docente para gestionar el catálogo, filtrar entregas, revisar respuestas,
  consultar estadísticas y exportar CSV.
- Protección frente a reenvíos y procesamiento concurrente de una misma entrega.
- Migraciones ligeras e idempotentes para evolucionar bases ya creadas.

## Arquitectura

| Componente | Tecnología | Responsabilidad |
| --- | --- | --- |
| API | FastAPI y Pydantic | Autenticación, examen, entrega, auditoría y panel docente |
| Persistencia | SQLAlchemy | SQLite local o PostgreSQL con Docker Compose |
| Frontend | HTML, CSS y JavaScript nativo | Flujos de alumnado y profesorado sin compilación |
| Corrección | Python y casos de prueba | Evaluación determinista y desglose trazable |
| Sandbox | Subproceso local o contenedor Docker | Límites de tiempo, salida, memoria, CPU y procesos |

## Requisitos

- Python 3.11 o superior.
- `pip`.
- Navegador moderno. El flujo de alumnado necesita soporte para compartir
  pantalla y acceder a cámara y micrófono.
- Docker Desktop y Docker Compose, solo para PostgreSQL, despliegue en contenedores
  o sandbox aislado.

## Puesta en marcha local (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edita `.env` y sustituye `SECRET_KEY` e `IDENTITY_HMAC_KEY`. Puedes generar cada
valor con:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Prepara la base de demostración:

```powershell
python scripts/reset_db.py
python backend/data/seed_questions.py
```

Inicia la API:

```powershell
python -m uvicorn backend.main:app --reload
```

En otra terminal, sirve el frontend:

```powershell
Set-Location frontend
python -m http.server 5500
```

- Aplicación: `http://127.0.0.1:5500/index.html`
- Documentación OpenAPI: `http://127.0.0.1:8000/docs`
- Estado de la API: `http://127.0.0.1:8000/health`

## Identidades de demostración

| Rol | Nombre | Correo |
| --- | --- | --- |
| Alumnado | Alumna Demostración | `alumna.demo@alu.uclm.es` |
| Profesorado | Profesor Demostración | `profesor.demo@uclm.es` |
| Profesorado | Docente Responsable Demo | `docente.demo@uclm.es` |

Los datos se mantienen en `backend/data/datos_iniciales.json`. Los correos se
normalizan sin distinguir mayúsculas y minúsculas.

## Recorrido

1. Abre la aplicación y accede como alumnado.
2. Acepta el consentimiento y concede los tres permisos solicitados. Si se deniega
   alguno, el servidor no crea el intento.
3. Responde a las cuatro preguntas y envía la prueba.
4. Comprueba la nota automática y la respuesta pendiente de revisión.
5. Vuelve al acceso, elige profesorado y entra con una identidad docente.
6. Revisa catálogo, configuración, estadísticas y detalle de la entrega.
7. Asigna una nota a la respuesta corta y guarda la revisión.
8. Descarga el CSV para comprobar la exportación trazable.

## Verificación reproducible

Con el entorno virtual activado:

```powershell
python -m pip install -r requirements-dev.txt
python -m compileall -q backend scripts tests
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python scripts/simular_flujo_demo.py
```

El script de demostración reinicia la base local, siembra los datos, completa un
intento correcto y comprueba que la entrega aparece en el panel docente.

La verificación portable completa, con cobertura de líneas y ramas, modelo de
estados ejecutable y simulación integral, se concentra en un solo comando:

```powershell
python scripts/verificar_tfg.py
```

Las comprobaciones que necesitan infraestructura se activan de forma explícita:

```powershell
python scripts/verificar_tfg.py --postgresql
python scripts/verificar_tfg.py --docker
python scripts/verificar_tfg.py --navegador
python scripts/verificar_tfg.py --seguridad
```

El modelo de amenazas y las limitaciones de privacidad se conservan en
`docs/seguridad/`; las figuras editables y listas para Overleaf están en
`docs/figuras_simplificadas/`.

Para validar Compose, primero debe existir `.env`:

```powershell
docker compose config
```

## Docker Compose

```powershell
docker compose build
docker compose up -d db backend frontend
docker compose exec backend python scripts/reset_db.py
docker compose exec backend python backend/data/seed_questions.py
```

El frontend queda en `http://127.0.0.1:5500` y la API en el puerto `8000`. La
configuración de ejemplo mantiene `SANDBOX_USE_DOCKER=false`: el backend del
contenedor usa el runner interno para la demostración local.

Para probar el sandbox Docker con la API ejecutada en el host:

```powershell
docker build -f Dockerfile.sandbox -t evaluador-sandbox:local .
```

Después configura `SANDBOX_USE_DOCKER=true`, confirma que el daemon está activo y
reinicia la API. No expongas el socket Docker dentro de un contenedor de aplicación
sin una revisión específica de seguridad.




## Límites del prototipo

- No hay SSO ni contraseñas: la autenticación usa identidades sembradas para una
  demostración controlada y se rechaza en modo producción.
- El consentimiento requiere revisión jurídica antes de utilizar datos reales.
- El runner por subproceso reduce riesgos, pero no sustituye el aislamiento fuerte
  de contenedores en un entorno compartido.
- Las migraciones incluidas cubren la evolución actual; una explotación prolongada
  debería adoptar una herramienta como Alembic y una política formal de copias.
- No se declara una licencia de software en este repositorio.
