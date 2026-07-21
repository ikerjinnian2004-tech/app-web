# Matriz de controles y evidencias

| Riesgo | Control | Estado | Prueba o comando | Límite |
| --- | --- | --- | --- | --- |
| Estado parcial | Unidad transaccional final | IMPLEMENTADO Y EJECUTADO | `pytest tests/test_atomicidad_envio.py` | PostgreSQL local bloqueado |
| Doble intento | Restricción única y recuperación del ganador | IMPLEMENTADO Y EJECUTADO | `pytest tests/test_concurrencia.py` | SQLite no reproduce todos los bloqueos PG |
| Reenvío | Hash, reserva identificada e idempotencia | IMPLEMENTADO Y EJECUTADO | `pytest tests/test_atomicidad_envio.py` | No sustituye control de identidad real |
| Código hostil | Opciones Docker endurecidas | IMPLEMENTADO, NO EJECUTADO EN ESTE ENTORNO | `python scripts/verificar_sandbox_docker.py` | Daemon ausente |
| Runner inseguro en producción | Validación fail-closed | IMPLEMENTADO Y EJECUTADO | `pytest tests/test_modo_produccion.py` | Requiere despliegue dedicado |
| Pérdida de respuestas | Borradores versionados del servidor | IMPLEMENTADO Y EJECUTADO | `pytest tests/test_borradores.py`; recorrido Brave | Última escritura aún en vuelo puede no sobrevivir al cierre abrupto |
| Captura oculta | Consentimiento, permiso y estado visible | IMPLEMENTADO Y EJECUTADO | `scripts/capturar_recorrido_navegador.py` | Medios sintéticos, no hardware real |
| Archivo disfrazado | MIME, firma, bytes, duración y nombre UUID | IMPLEMENTADO Y EJECUTADO | `pytest tests/test_auditoria_profesor.py` | Firma básica, no análisis profundo |
| Acceso a evidencia | Rol docente y registro de descarga | IMPLEMENTADO Y EJECUTADO | `pytest tests/test_auditoria_profesor.py` | Identidad docente demo |
| Retención indefinida | Días configurables y depuración confirmada | IMPLEMENTADO Y EJECUTADO | `python scripts/depurar_evidencias.py` | La política legal debe aprobarse externamente |
| Dependencia vulnerable | Versiones fijadas y `pip-audit` | IMPLEMENTADO Y EJECUTADO | `pip-audit-final.json`: 0 hallazgos | Foto temporal de una base externa |
| Imagen mutable | Etiqueta exacta y digest multiarquitectura | CONFIGURADO, NO VALIDADO | `docker compose config`; Dockerfiles | Construcción real bloqueada |
