# Plan de endurecimiento ejecutable

## Principios de ejecución

1. Conservar el estado inicial y no mezclar los tres artefactos previos sin
   versionar con cambios del proyecto.
2. Añadir primero una prueba que exponga cada defecto, conservar el resultado y
   aplicar después el cambio mínimo.
3. Ejecutar la prueba afectada, el módulo y la suite relevante tras cada bloque.
4. Clasificar toda evidencia como `IMPLEMENTADO Y EJECUTADO`, `IMPLEMENTADO, NO
   EJECUTADO EN ESTE ENTORNO`, `CONFIGURADO, NO VALIDADO`, `BLOQUEADO` o `FUERA
   DEL ALCANCE`.
5. No llamar sandbox a la política AST ni afirmar seguridad absoluta.
6. Mantener los contratos públicos y la selección de preguntas en el backend.
7. No ejecutar cargas hostiles en el host. Las pruebas agresivas requieren
   `ALLOW_DESTRUCTIVE_SANDBOX_TESTS=1` y un entorno desechable.

## Matriz de trabajo

| Orden | Problema y gravedad | Archivos previstos | Propiedad de aceptación | Pruebas/evidencias | Riesgo de regresión |
| --- | --- | --- | --- | --- | --- |
| 0 | Baseline no reproducible en esta copia - alta | `scripts/verificar_tfg.py`, `artifacts/tfg-evidence/` | Un comando ejecuta y clasifica todas las comprobaciones | logs crudos, versiones, JUnit, manifiesto | Bajo |
| 1 | Envío no atómico - crítica | `models.py`, `migraciones.py`, `crud.py`, nuevo servicio, `submission.py` | Respuestas + calificación + cierre se confirman una sola vez; cualquier fallo previo restaura el snapshot | fallos inyectados desde una sesión nueva, éxito, reintento y reserva caducada | Alto |
| 2 | Inicio concurrente duplicable - alta | `models.py`, `migraciones.py`, `crud.py`, `exam.py` | Como máximo una entrega por alumno/examen en el dominio actual | 2/10/20 peticiones con conexiones independientes, recuperación de `IntegrityError` | Alto |
| 3 | PostgreSQL solo configurado - alta | Compose específico, scripts y CI | Esquema desde cero, suite crítica y concurrencia en PostgreSQL | JUnit y consultas de invariantes | Medio; depende de daemon |
| 4 | Reserva sin propietario/idempotencia - alta | modelo, migración y servicio de entregas | Solo el propietario vigente puede confirmar; reintentos son deterministas | expiración, payload distinto, caída anterior al commit | Alto |
| 5 | Docker no validado y modo producción inseguro - crítica/alta | `config.py`, `main.py`, `runner_docker.py`, Dockerfiles, scripts | Producción falla si falta sandbox; contenedor aplica controles observables | inspección real, campaña adversaria opt-in y limpieza | Alto; daemon bloqueado inicialmente |
| 6 | Sin autosalvado - media-alta | modelo/migración, router, esquemas, `api.js`, `examen.js` | Borradores versionados, recuperables y no calificables; envío congela/elimina | recarga, reconexión, dos pestañas, cierre y guardado pendiente | Medio |
| 7 | Demo utilizable en producción - media | `config.py`, `auth.py`, tests y `.env.example` | Demo explícita en desarrollo; producción la rechaza y exige secretos | pruebas de configuración y arranque | Medio |
| 8 | Multimedia solicita permisos en segundo plano - media | `index.js`, `auditoria.js`, API de eventos | Los flujos se autorizan por acción previa y se reutilizan; revocación se registra | pruebas JS/navegador con medios sintéticos y manual voluntario | Medio/alto por compatibilidad |
| 9 | Privacidad/observabilidad incompletas - media | audit/admin, modelos/config, runner, documentación | límites, contenido permitido, acceso, retención, descargas y motivos de terminación trazables | unidad/integración y matriz de controles | Medio |
| 10 | Cobertura/CI/evidencia incompletas - media | tests, workflows, scripts y docs | trabajos separados y ningún crítico omitido aparece aprobado | cobertura de línea/rama, Playwright, análisis de dependencias | Bajo/medio |
| 11 | Arquitectura y resultados difíciles de demostrar - media | `docs/figuras_simplificadas/`, manual e informe | fuentes editables y PDF/PNG/SVG legibles; pasos manuales reproducibles | renderizado e inspección visual | Bajo |
| 12 | Paquete final y limpieza - media | generador de evidencias, manifiesto, `.gitignore` | ZIP autocontenido, hashes válidos, sin secretos ni datos personales | apertura ZIP, recomputación SHA-256 y auditoría Git | Medio |

## Secuencia detallada

### I0. Baseline y trazabilidad

- Crear un entorno virtual local ignorado e instalar las dependencias fijadas.
- Capturar Git, sistema, Python, Node, Docker/Compose, `pip check`, compilación,
  pytest, Ruff y Compose.
- Guardar las salidas crudas bajo
  `artifacts/tfg-evidence/<commit>/baseline/` sin reescribir resultados.
- Crear una matriz problema -> cambio -> prueba -> evidencia -> limitación.

### I1. Atomicidad e idempotencia

- Introducir un identificador opaco de reserva, caducidad y versión de entrega.
- Separar la reserva breve de la corrección fuera de transacción.
- Crear un servicio de aplicación que persista respuestas, calificación y cierre
  dentro de una sola transacción y use `flush()` sin commits internos.
- Añadir restricciones de una calificación por entrega, una respuesta por
  pregunta, rangos y estados consistentes donde el motor lo permita.
- Inyectar fallos después de cada punto solicitado y comparar snapshots desde
  conexiones nuevas.
- Modelar el protocolo concurrente en `verification/submission_atomicity/` y
  ejecutar un comprobador disponible; si no existe, conservar el modelo y marcar
  la ejecución como pendiente.

### I2. Inicio único y PostgreSQL

- Adoptar la regla del dominio actual: un intento total por alumno y examen.
- Añadir la restricción y recuperar de forma controlada el ganador cuando dos
  transacciones intenten insertar.
- Ejecutar contención con 2, 10 y 20 solicitudes.
- Añadir Compose de pruebas PostgreSQL sin datos persistentes y un script que
  recree el esquema y emita JUnit.
- Añadir el trabajo de CI PostgreSQL. La evidencia local quedará bloqueada si el
  daemon continúa sin estar disponible.

### I3. Sandbox y producción

- Añadir modo `development|test|production` y reglas de arranque seguro.
- Mantener el runner local solo para desarrollo/pruebas.
- Separar `stdout`/`stderr`, clasificar motivos, limitar archivos/salida/tmpfs y
  registrar imagen/ejecución/limpieza sin guardar código personal.
- Fijar imágenes por versión/digest cuando el daemon pueda resolver el digest.
- Preparar una campaña opt-in que inspeccione red, raíz de solo lectura,
  capacidades, usuario, mounts, recursos, timeout y residuos.
- No activar cargas agresivas en este host.

### I4. Producto y privacidad

- Añadir borradores servidor con contador de versión y timestamp.
- Integrar guardado periódico, al cambiar de control y antes del envío; mostrar
  guardado/error y recuperar tras recarga.
- Desactivar demo en producción y dejar un puerto OIDC desacoplado únicamente si
  puede probarse con proveedor simulado sin credenciales externas.
- Preparar los flujos multimedia antes del examen y reutilizarlos; validar MIME
  soportado y registrar denegación/revocación sin penalización.
- Añadir retención configurable, auditoría de acceso y documentación de límites
  técnicos sin declarar cumplimiento jurídico.

### I5. Verificación y entrega

- Añadir cobertura de línea y rama para módulos críticos, pruebas de propiedades
  justificadas y Playwright con Brave si Chromium no existe.
- Generar fuentes `.mmd`, y versiones `.svg`, `.png` y `.pdf`; renderizar e
  inspeccionar cada PDF.
- Crear capturas solo de estados realmente observados y fichas que indiquen qué
  demuestran y qué no.
- Crear `MANUAL_EVIDENCIAS_TFG.md`, documentación de seguridad, matriz de
  trazabilidad e `INFORME_FINAL_ENDURECIMIENTO.md`.
- Generar ZIP, `EVIDENCE_MANIFEST.json` y `SHA256SUMS.txt`; validar apertura,
  hashes, exclusiones y ausencia de secretos.
- Ejecutar auditoría de limpieza de solo lectura, borrar solo cachés inequívocas
  no versionadas y mantener en cuarentena lo dudoso.

## Política de commits

El árbol inicial no estaba limpio por artefactos previos del usuario. Por ello no se
crearán commits automáticos. El informe final propondrá una secuencia de commits en
castellano, cada uno asociado a una fase y a sus pruebas.

## Condiciones de cierre

Una fila de la directiva solo podrá cerrarse si tiene estado, comando, resultado y
ruta de evidencia. Las propiedades dependientes de Docker, PostgreSQL, permisos
multimedia reales, infraestructura institucional, validación jurídica o revisión de
seguridad externa permanecerán explícitamente bloqueadas o fuera de alcance cuando no
puedan ejecutarse con veracidad en este entorno.
