# Manual reproducible de evidencias del TFG

Este manual permite repetir las comprobaciones sin depender de una conversación
previa. Todas las identidades de ejemplo son ficticias. No uses una base de datos
real ni captures cara, voz, pantalla, tokens o claves salvo que exista una decisión
voluntaria y una ubicación de almacenamiento aprobada.

## 1. Estados y alcance

- `IMPLEMENTADO Y EJECUTADO`: existe una salida conservada de esta ejecución.
- `IMPLEMENTADO, NO EJECUTADO EN ESTE ENTORNO`: el código y la prueba existen,
  pero faltó infraestructura.
- `CONFIGURADO, NO VALIDADO`: la configuración es inspeccionable, pero no se ha
  observado su ejecución completa.
- `BLOQUEADO`: se intentó y una dependencia externa impidió continuar.
- `FUERA DEL ALCANCE`: exige validación institucional, jurídica o humana externa.

El identificador de evidencia es el commit base corto. Obténlo con
`git rev-parse --short HEAD`. Si el árbol tiene cambios, anota además la salida de
`git status --short`: el hash identifica la base, no los cambios sin confirmar.

## 2. Instalación limpia

### Windows PowerShell

```powershell
git clone <URL-DEL-REPOSITORIO> app-web-tfg
Set-Location app-web-tfg
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Copia dos valores distintos del último comando a `SECRET_KEY` e
`IDENTITY_HMAC_KEY`. Nunca muestres `.env` en una captura.

### Linux Bash

```bash
git clone <URL-DEL-REPOSITORIO> app-web-tfg
cd app-web-tfg
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
cp .env.example .env
python -c 'import secrets; print(secrets.token_urlsafe(48))'
```

### Base local, backend y frontend

```powershell
python scripts/reset_db.py
python backend/data/seed_questions.py
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

En otra terminal:

```powershell
Set-Location frontend
python -m http.server 5500 --bind 127.0.0.1
```

Abre `http://127.0.0.1:5500/index.html`. La API debe responder en
`http://127.0.0.1:8000/health`. En Bash los comandos Python son iguales después
de activar el entorno.

## 3. Verificación portable

```powershell
python scripts/verificar_tfg.py
python scripts/verificar_configuracion_compose.py
```

El código de salida es cero solo si pasan compilación, Ruff, formato,
`pip check`, suite con cobertura de líneas y ramas, modelo de estados y simulación
integral. Las salidas quedan en `artifacts/tfg-evidence/<commit>/`.

Ejecuciones focalizadas útiles:

```powershell
python -m pytest tests/test_atomicidad_envio.py -q
python -m pytest tests/test_concurrencia.py -q
python -m pytest tests/test_borradores.py -q
python -m pytest tests/test_auditoria_profesor.py -q
python -m pytest tests/test_modo_produccion.py -q
python scripts/capturar_recorrido_navegador.py
python -m pip_audit -r requirements.txt --progress-spinner off
```

## 4. PostgreSQL real

### Docker Desktop en Windows

1. Abre Docker Desktop y espera a que indique que el motor está ejecutándose.
2. Comprueba `docker info`; no continúes si devuelve un error del daemon.
3. Ejecuta:

```powershell
docker compose -f docker-compose.postgresql.yml up -d --wait
$env:POSTGRES_TEST_URL='postgresql+psycopg2://evaluador_test:evaluador_test_local@127.0.0.1:55432/evaluador_test'
$env:ALLOW_POSTGRES_TEST_RESET='1'
python scripts/verificar_postgresql.py
docker compose -f docker-compose.postgresql.yml down -v
```

### Docker Engine en Linux

```bash
docker info
docker compose -f docker-compose.postgresql.yml up -d --wait
export POSTGRES_TEST_URL='postgresql+psycopg2://evaluador_test:evaluador_test_local@127.0.0.1:55432/evaluador_test'
export ALLOW_POSTGRES_TEST_RESET=1
python scripts/verificar_postgresql.py
docker compose -f docker-compose.postgresql.yml down -v
```

El script destruye y recrea el esquema de **esa base de pruebas**. Revisa dos
veces la URL y no actives `ALLOW_POSTGRES_TEST_RESET` contra datos valiosos.
El resultado esperado es un JUnit sin omisiones en la carpeta `postgresql/`.

## 5. Sandbox Docker real

Ejecuta esta campaña solo en una VM desechable, runner aislado o máquina sin
datos personales. Nunca ejecutes los payloads hostiles directamente en el host.

```powershell
docker build -f Dockerfile.sandbox -t evaluador-sandbox:local .
$env:SANDBOX_IMAGE='evaluador-sandbox:local'
$env:RUN_DOCKER_SANDBOX_TESTS='1'
$env:ALLOW_DESTRUCTIVE_SANDBOX_TESTS='1'
python scripts/verificar_sandbox_docker.py
docker ps -a --filter label=app=evaluador-sandbox
```

En Bash usa `export` en vez de `$env:`. Conserva `docker version`, `docker info`,
el informe JSON, `docker inspect`, eventos y el listado final de contenedores.
Un fallo de red, escritura o recursos solo prueba el payload y configuración
ensayados; no demuestra aislamiento absoluto ni ausencia de vulnerabilidades del
kernel/runtime.

## 6. Recorrido multimedia manual

Chrome/Chromium es la ruta de referencia. Firefox puede comprobar acceso,
consentimiento, cámara y micrófono, pero la captura de pantalla y los formatos de
`MediaRecorder` dependen de versión y plataforma; si no ofrece el mismo flujo,
registra `CONFIGURADO, NO VALIDADO` y conserva el mensaje exacto.

1. Abre la aplicación en `localhost` o HTTPS.
2. Accede como `alumna.demo@alu.uclm.es`.
3. Lee y acepta el consentimiento versionado.
4. Selecciona de forma visible la cámara frontal.
5. Autoriza el micrófono.
6. Comparte una pantalla o ventana de prueba sin datos personales.
7. Comprueba los indicadores del navegador y de la aplicación.
8. Inicia el examen; los flujos deben seguir activos.
9. Escribe respuestas y espera el indicador `Guardado`.
10. Recarga y comprueba que el servidor recupera los borradores.
11. Cambia a otra pestaña.
12. Espera el intervalo de clip y vuelve al examen.
13. Finaliza la entrega.
14. Accede como `profesor.demo@uclm.es`.
15. Abre el detalle, el evento y la evidencia.
16. Comprueba propietario, timestamp, tamaño, duración y reproducción de las
    pistas esperadas.
17. Repite revocando cámara o micrófono; debe mostrarse ausencia/reactivación.
18. Detén manualmente la pantalla; la interfaz debe reflejar que finalizó.
19. Repite denegando permisos; el inicio debe quedar bloqueado de forma controlada.

La automatización usa un lienzo y audio sintéticos. Ejecútala con
`python scripts/capturar_recorrido_navegador.py`; no equivale a probar hardware
real ni el selector nativo de pantalla.

## 7. Catálogo de 30 capturas

Regla común: resolución 1440 x 900, nombre sin espacios, terminal recortada al
comando y resultado, commit/fecha en el pie, y ocultación de `.env`, cabeceras de
autorización, respuestas ocultas y datos personales. Para fallos frecuentes:
activa primero el entorno virtual, verifica puertos 8000/5500, revisa
`artifacts/.../*.log`, y no conviertas un `skipped` o daemon ausente en aprobado.

| N | Objetivo, requisito y comando/pasos | Captura, resultado esperado y nombre | Pie; demuestra / no demuestra |
| --- | --- | --- | --- |
| 01 | Identificar commit y entorno: `git rev-parse HEAD`, `python --version`, `docker version`. | Tras la salida; `01_entorno.png`. Debe ocultar usuario/rutas sensibles. | "Entorno y commit base"; prueba procedencia observada, no limpieza ni reproducibilidad futura. |
| 02 | Acceso: servicios activos y navegador. | Formulario completo; `02_acceso.png`. | "Acceso con identidades ficticias"; prueba interfaz, no identidad institucional. |
| 03 | Consentimiento: entrar como alumnado. | Texto, versión y casilla; `03_consentimiento.png`. | "Consentimiento previo"; prueba flujo técnico, no validez jurídica. |
| 04 | Permisos: autorizar cámara, audio y pantalla. | Estado de los tres flujos; `04_permisos.png`. | "Permisos multimedia visibles"; con medios sintéticos no prueba hardware real. |
| 05 | Inicio: pulsar comenzar. | Cabecera, temporizador y estado; `05_inicio_examen.png`. | "Intento iniciado"; no prueba exclusión concurrente por sí sola. |
| 06 | Huecos: navegar a esa pregunta. | Enunciado y editor, sin solución oculta; `06_huecos.png`. | "Pregunta de huecos asignada"; no revela banco completo. |
| 07 | Corrección: siguiente pregunta. | Editor y casos visibles; `07_correccion.png`. | "Corrección de código"; no muestra casos ocultos. |
| 08 | Test: siguiente pregunta. | Opciones visibles; `08_test.png`. | "Pregunta tipo test"; no demuestra calificación. |
| 09 | Respuesta corta. | Campo y aviso de revisión; `09_respuesta_corta.png`. | "Revisión pendiente"; no demuestra criterio docente. |
| 10 | Autosalvado: escribir y esperar. | Indicador `Guardado`; `10_autosalvado.png`. | "Borrador aceptado por servidor"; no asegura la última petición en vuelo. |
| 11 | Recuperación: recargar. | Textos recuperados; `11_recuperacion.png`. | "Recuperación tras recarga"; no prueba una desconexión prolongada. |
| 12 | Inicio HTTP: DevTools/Network, filtrar `start`. | Petición y 200 sin cabeceras sensibles; `12_peticion_inicio.png`. | "Contrato HTTP observado"; no prueba carrera. |
| 13 | Recarga: comparar identificadores/preguntas. | Mismo intento/orden; `13_seleccion_estable.png`. | "Selección congelada"; no prueba otra cuenta. |
| 14 | Enviar respuestas. | Resultado y desglose; `14_resultado.png`. | "Calificación funcional"; no prueba atomicidad aislada. |
| 15 | Panel docente y detalle. | Revisión manual visible; `15_revision.png`. | "Acceso docente y revisión"; usa identidad demo. |
| 16 | Guardar nota manual. | Resultado recalculado; `16_nota_recalculada.png`. | "Recalculo tras revisión"; no valida política académica. |
| 17 | Exportar CSV. | Descarga y columnas, con datos ficticios; `17_exportacion.png`. | "Exportación coherente"; no prueba interoperabilidad externa. |
| 18 | Cambiar de pestaña y volver. | Evento en detalle docente; `18_evento.png`. | "Cambio de visibilidad registrado"; no implica fraude ni penalización. |
| 19 | Abrir evidencia sintética. | Metadatos y reproductor; `19_multimedia.png`. | "Persistencia/acceso del clip sintético"; no prueba cámara personal. |
| 20 | `python scripts/verificar_tfg.py`. | Resumen final y código 0; `20_suite.png`. | "Suite portable ejecutada"; las omisiones siguen sin ejecutar. |
| 21 | Sección 4, `python scripts/verificar_postgresql.py`. | JUnit sin skips; `21_postgresql.png`. | "Suite sobre PostgreSQL"; no prueba producción sostenida. Si no hay daemon: `BLOQUEADO`. |
| 22 | Sección 5, construir/ejecutar sandbox. | Versión, imagen y resumen; `22_docker_real.png`. | "Contenedores reales usados"; no aislamiento absoluto. Si no hay daemon: `BLOQUEADO`. |
| 23 | Campaña Docker, casos de red. | Resultado TCP/UDP/DNS bloqueado; `23_red_bloqueada.png`. | Prueba payloads ensayados, no todas las vías de red. |
| 24 | Campaña Docker, escritura. | Raíz rechazada y tmpfs limitado; `24_escritura.png`. | Prueba montajes/rutas ensayados, no vulnerabilidades del runtime. |
| 25 | Caso Docker de bucle/timeout. | Motivo, duración y salida; `25_timeout.png`. | Prueba terminación ensayada, no disponibilidad bajo carga. |
| 26 | `docker ps -a --filter label=app=evaluador-sandbox`. | Lista vacía tras campaña; `26_limpieza_docker.png`. | Prueba limpieza observada, no futuros fallos del daemon. |
| 27 | `python -m pytest tests/test_atomicidad_envio.py -q`. | Casos de fallos verdes/JUnit; `27_rollback.png`. | Prueba rollback desde conexiones nuevas en SQLite; PostgreSQL se separa en 21. |
| 28 | `python -m pytest tests/test_concurrencia.py -q`. | Casos 2/10/20 verdes; `28_concurrencia.png`. | Prueba carrera local y restricción; los bloqueos PostgreSQL requieren 21. |
| 29 | Abrir `artifacts/.../cobertura/html/index.html`. | Total y módulos críticos; `29_cobertura.png`. | Mide ejecución de líneas/ramas, no ausencia de defectos. |
| 30 | `git status --untracked-files=all` y `git clean -ndx`. | Estado explicado y sin cachés; `30_estado_git.png`. | Prueba auditoría local; un árbol con cambios deliberados no es un árbol confirmado. |

## 8. Atomicidad, concurrencia y consultas SQL

Las pruebas rojas conservadas muestran el defecto anterior y las verdes el
comportamiento final. Para una lectura directa de invariantes ejecuta las
consultas de `docs/auditoria/CONSULTAS_INTEGRIDAD.sql` sobre una copia de prueba.
Todos los contadores de incoherencias deben ser cero. Las consultas observan el
estado; no fuerzan intercalados concurrentes.

## 9. Diagramas y Overleaf

Regenera las fuentes y cuatro formatos con:

```powershell
python scripts/generar_diagramas.py
```

Usa PDF para diagramas vectoriales y PNG para capturas de interfaz. Recorta solo
márgenes irrelevantes, mantén texto legible al 100 %, no estires imágenes y usa
nombres ASCII sin espacios. Un pie debe indicar sistema, fecha, commit, resultado
y límite, y el texto debe referenciarlo antes o después de la figura.

```latex
\begin{figure}[htbp]
    \centering
    \includegraphics[width=\textwidth]{figuras/02_transaccion_envio.pdf}
    \caption{Unidad transaccional del envío y rollback antes del commit.}
    \label{fig:transaccion-envio}
\end{figure}
```

## 10. Paquete, hashes y limpieza

Genera y verifica el paquete con:

```powershell
python scripts/generar_paquete_evidencias.py
```

El script excluye secretos, bases, cachés, entornos y medios personales; abre el
ZIP, compara sus hashes y deja un resumen. Para auditar antes de borrar:

```powershell
git status --untracked-files=all
git clean -ndx
git ls-files --others --exclude-standard
```

Borra solo cachés o entornos regenerables después de verificar sus rutas. No uses
`git clean -fdx`, no borres entregables previos y conserva en cuarentena cualquier
archivo de propósito dudoso.

## 11. Errores frecuentes

- **`ModuleNotFoundError`**: activa `.venv` e instala `requirements-dev.txt`.
- **Puerto ocupado**: usa `Get-NetTCPConnection -LocalPort 8000,5500` en Windows
  o `ss -ltnp` en Linux; detén solo el proceso que hayas identificado.
- **Docker daemon no disponible**: inicia Docker Desktop/Engine y repite
  `docker info`; conserva el bloqueo si sigue fallando.
- **PostgreSQL omitido**: define ambas variables de la sección 4 y usa solo la
  base efímera indicada.
- **Permiso multimedia denegado**: restablece permisos del sitio, recarga y vuelve
  a realizar la acción visible; no automatices el selector saltando garantías.
- **Formato de grabación no soportado**: prueba Chrome/Chromium actualizado y
  conserva el MIME y versión; no renombres un archivo para simular otro formato.
- **Ruff o pruebas fallan**: abre el log numerado bajo `verificacion/`, corrige la
  causa y regenera todo el paquete para no mezclar ejecuciones.
