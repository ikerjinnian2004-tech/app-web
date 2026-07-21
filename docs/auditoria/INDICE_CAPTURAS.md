# Índice y estado de capturas

La definición, el pie propuesto, la reproducción y los límites de las 30
capturas están en `MANUAL_EVIDENCIAS_TFG.md`. Este índice evita confundir una
captura pendiente con una evidencia ejecutada.

| Números | Estado actual | Evidencia conservada | Observación |
| --- | --- | --- | --- |
| 02-11, 14-15, 18 | `IMPLEMENTADO Y EJECUTADO` | Paquete externo, `09_navegador/capturas/` | Brave, 1440 x 900, datos y medios sintéticos. |
| 01, 20, 27-29 | `IMPLEMENTADO Y EJECUTADO` | Logs, JUnit y cobertura; captura terminal/manual pendiente | El resultado primario es máquina-legible, no una imagen ornamental. |
| 12-13, 16-17, 19 | `IMPLEMENTADO Y EJECUTADO` en el recorrido/API; captura dedicada pendiente | `resultado_navegador.json`, logs y pruebas | El manual indica el punto exacto para capturar cada vista. |
| 21 | `CONFIGURADO, NO VALIDADO` / `BLOQUEADO` local | Compose, prueba y job CI | PostgreSQL real requiere daemon. |
| 22-26 | `IMPLEMENTADO, NO EJECUTADO EN ESTE ENTORNO` / `BLOQUEADO` | Runner, pruebas y estado del daemon | No existen capturas ni resultados Docker reales. |
| 30 | `IMPLEMENTADO Y EJECUTADO` | Paquete externo, auditoría Git e inventarios | Los entregables previos se conservan fuera del repositorio candidato. |

No se crean imágenes simuladas para 21-26. La ausencia es parte explícita de la
evidencia y los comandos pendientes se mantienen en el manual.
