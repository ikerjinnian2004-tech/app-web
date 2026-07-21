# Informe de cierre técnico y reproducibilidad

Fecha de observación: 2026-07-21. Rama candidata local: `cierre-tfg-2026`.
El hash final y los registros completos se conservan en el paquete externo de
evidencias generado después del commit. Este informe no acredita una publicación
remota.

## Resumen ejecutivo

El candidato integra sobre una copia limpia de `origin/main` los cambios locales
de endurecimiento que pudieron verificarse y el material público recuperable de
los entregables auxiliares. No se copiaron historiales Git antiguos, bases de
datos, entornos virtuales, paquetes ZIP, PDF, evidencias previas ni secretos.

La verificación final en un entorno virtual creado desde cero obtuvo:

- 114 pruebas superadas, 16 omitidas y 0 avisos;
- cobertura combinada de líneas y ramas del 86 %;
- 60 pruebas focalizadas de atomicidad, concurrencia, borradores, producción y
  sandbox superadas;
- compilación, Ruff, formato, `pip check` y auditoría de dependencias correctos;
- 0 vulnerabilidades conocidas en la instantánea final de `pip-audit`;
- simulación integral correcta con datos ficticios;
- recorrido funcional sintético completo en Brave, con respuestas API 200;
- modelo acotado explorado: 17 estados, 32 transiciones y 5 estados finales.

Los 16 casos omitidos son exactamente 8 pruebas reales de Docker y 8 de
PostgreSQL. No se contabilizan como aprobados. El daemon Docker y el servicio
PostgreSQL no estuvieron disponibles, por lo que ambos quedan bloqueados para
ejecución material. Las dos configuraciones Compose sí superaron validación
estática.

## Reconciliación y dependencias

La rama candidata parte del commit oficial `37a61f759a6beca19ae8797fb91bf7c3210aad75`.
La copia local de trabajo original partía de `36235b54786e86891250973881483290bae15380`,
estaba un commit por detrás y contenía cambios sin confirmar. Antes de combinar
nada se realizó una copia íntegra, incluido `.git`, y se compararon manifiestos
SHA-256.

Se separaron dependencias de producción (`requirements.txt`) y validación
(`requirements-dev.txt`). Se añadió `python-multipart`, requerido por las rutas
FastAPI con formularios y archivos. La versión final es 0.0.31 porque la 0.0.29
presentaba avisos conocidos en la auditoría. `httpx2` no se eliminó: Starlette
1.3.1 lo usa preferentemente en `TestClient`; `httpx` se conserva solo en el
entorno de desarrollo para compatibilidad y comprobaciones explícitas.

## Cambios técnicos principales

| Área | Resultado | Evidencia y límite |
| --- | --- | --- |
| Envío | Reserva breve, cálculo fuera de la transacción y persistencia atómica final | Fallos inyectados y reintentos aprobados en SQLite; PostgreSQL pendiente |
| Concurrencia | Unicidad alumno/examen y recuperación del ganador | Carreras locales aprobadas; bloqueos internos de PostgreSQL no observados |
| Borradores | Versionado, autosalvado y recuperación | Pruebas focalizadas y recorrido Brave aprobados |
| Producción | Arranque cerrado ante configuración insegura | Pruebas de modo producción aprobadas; no hubo despliegue real |
| Sandbox | Contrato Docker estructurado y controles solicitados | Pruebas con dobles aprobadas; contenedor real bloqueado |
| Auditoría | Propiedad, MIME/firma, tamaño, duración, UUID, acceso y retención | No equivale a análisis forense ni cumplimiento jurídico |
| Panel docente | Catálogo, versiones, revisión, estadísticas y exportación | Pruebas API y recorrido sintético; no validado con usuarios reales |
| Reproducibilidad | Scripts, CI, diagramas, manual y paquete de evidencias | CI remota configurada, no ejecutada en este cierre |

## Atomicidad y modelo

El envío se divide en reserva, cálculo y persistencia. La persistencia vuelve a
validar el estado, reemplaza respuestas, crea la calificación, elimina borradores,
cierra la entrega y consume la reserva dentro de una unidad de trabajo. Las
restricciones impiden duplicar entregas, calificaciones y respuestas.

Las pruebas inyectan fallos en puntos intermedios y comparan el estado desde
conexiones nuevas. También cubren reintento idéntico o distinto, timeout,
finalización del proceso y recuperación de la reserva. El explorador recorre de
forma exhaustiva su modelo acotado, pero no demuestra equivalencia formal con
SQLAlchemy ni con PostgreSQL.

## Sandbox y PostgreSQL

El adaptador Docker solicita red deshabilitada, raíz de solo lectura, usuario no
privilegiado, capacidades eliminadas, `no-new-privileges`, límites de memoria,
CPU y procesos, `tmpfs`, timeout, truncamiento de salida y eliminación del
contenedor. Estas opciones están implementadas y probadas a nivel de contrato.

Estado material de Docker: `BLOQUEADO`. La CLI 29.5.3 y Compose 5.1.4 estaban
instalados, pero `docker info` no pudo conectar con el pipe del daemon. No se
construyó una imagen, no se inició ningún contenedor, no se ejecutó código hostil
y no se generó un SBOM de imagen.

Estado material de PostgreSQL: `BLOQUEADO`. La configuración Compose estática se
validó y el script de prueba alcanzó una URL dedicada terminada en `_test`, pero
la conexión local al puerto 55432 fue rechazada por ausencia del servicio. No se
tocó ninguna base de datos ajena.

## Navegador y multimedia

Brave se ejecutó sin interfaz a 1440 × 900. La automatización recorrió acceso,
consentimiento, permisos, examen, autosalvado y recuperación, evento y evidencia,
envío, desglose y panel docente. La traza de red conserva cada respuesta API.

La cámara, el micrófono y la pantalla fueron flujos sintéticos inyectados. No se
capturó a ninguna persona ni se comprobó hardware físico, revocación de permisos,
selector nativo o validez jurídica del consentimiento. Un 404 de recurso estático
secundario quedó en consola sin impedir el recorrido ni afectar las API.

## Matriz de estado

| Comprobación | Estado |
| --- | --- |
| Instalación desde `requirements-dev.txt` | `IMPLEMENTADO Y EJECUTADO` |
| Compilación, Ruff, formato y `pip check` | `IMPLEMENTADO Y EJECUTADO` |
| Suite portable y cobertura | `IMPLEMENTADO Y EJECUTADO` |
| Auditoría de dependencias | `IMPLEMENTADO Y EJECUTADO` |
| Simulación integral y modelo de estados | `IMPLEMENTADO Y EJECUTADO` |
| Recorrido Brave con datos y medios sintéticos | `IMPLEMENTADO Y EJECUTADO` |
| Compose de aplicación y PostgreSQL | `CONFIGURADO Y VALIDADO ESTÁTICAMENTE` |
| Docker real | `BLOQUEADO` |
| PostgreSQL real | `BLOQUEADO` |
| CI de GitHub | `CONFIGURADO, NO EJECUTADO` |
| SSO/OIDC, despliegue y carga | `NO VALIDADO` |
| Hardware multimedia y usuarios reales | `NO VALIDADO` |
| Revisión jurídica | `PENDIENTE` |

## Reproducción portable

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe scripts/verificar_tfg.py
.\.venv\Scripts\python.exe scripts/capturar_recorrido_navegador.py
```

Las campañas Docker/PostgreSQL requieren infraestructura externa y activación
explícita. `MANUAL_EVIDENCIAS_TFG.md` describe las salvaguardas y los comandos.

## Limitaciones y decisiones pendientes

- No se hizo `push`, merge, tag, release ni despliegue.
- No se observó ninguna ejecución de CI remota.
- No se declara una licencia; su elección corresponde a la autoría.
- La autenticación de demostración no acredita identidad institucional real.
- El runner local no es una frontera de seguridad para uso compartido.
- Las migraciones ligeras no sustituyen una estrategia de operación prolongada.
- La evidencia sintética no acredita accesibilidad, usabilidad ni privacidad con
  personas reales.
- El PDF académico preexistente no se alteró y puede contener afirmaciones
  históricas anteriores a este candidato; debe alinearse antes de una entrega
  académica definitiva.
