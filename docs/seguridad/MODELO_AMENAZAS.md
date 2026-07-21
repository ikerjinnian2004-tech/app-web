# Modelo de amenazas del evaluador

## Alcance

El activo más sensible del prototipo es la integridad de una entrega académica:
preguntas asignadas, respuestas, calificación, cierre, revisiones y evidencias.
También se protegen las claves de aplicación, los datos de identidad y el host
que ejecuta código del alumnado.

El adversario considerado controla el texto de una respuesta Python e intenta:

- leer o modificar el host o datos de otra ejecución;
- acceder a secretos, procesos, montajes, red o metadatos del runtime;
- consumir memoria, CPU, procesos, disco temporal o volumen de salida;
- persistir después del timeout o interferir con otra ejecución;
- duplicar inicios, repetir envíos o provocar estados parciales;
- subir un archivo multimedia distinto del tipo declarado o acceder a una
  evidencia ajena.

No se modelan vulnerabilidades desconocidas del kernel, Docker o hipervisor, una
persona administradora hostil, compromiso físico, denegación de servicio
distribuida ni validación jurídica del sistema de supervisión.

## Límites de confianza

1. El navegador y todas sus peticiones son no confiables.
2. La API valida identidad de demostración, rol, propiedad, tamaños y estados.
3. La base de datos impone unicidad y parte de las invariantes concurrentes.
4. El filtro AST es defensa preventiva, nunca frontera de aislamiento.
5. El adaptador Docker fija los argumentos; el código del usuario no los controla.
6. El contenedor es una frontera adicional que debe ejecutarse en un host o VM
   dedicado y, preferiblemente, con Docker rootless.

El diagrama editable y sus versiones de página están en
`docs/figuras_simplificadas/04_limites_confianza.*`.

## Controles implementados

- Transacción final única con bloqueo de fila y comprobación de reserva.
- Cálculo fuera de la transacción larga.
- Identificador y caducidad de reserva; hash para reenvío idempotente.
- `UNIQUE(alumno_id, examen_id)` y restricciones de respuestas/calificación.
- Producción rechaza autenticación demo, runner local y Docker indisponible.
- Docker solicita red `none`, raíz de solo lectura, usuario 10001, capacidades
  eliminadas, `no-new-privileges`, límites, `tmpfs`, entorno permitido y limpieza.
- Salidas stdout/stderr separadas, truncadas y acompañadas de motivo y duración.
- Evidencias autorizadas por entrega, con bytes/duración, firma WebM/MP4, nombre
  generado, BLOB no público, rol docente y log de descarga.

## Estado de la validación

- `IMPLEMENTADO Y EJECUTADO`: pruebas SQLite, inyección de siete fallos,
  concurrencia local, proceso interrumpido, navegador Brave y medios sintéticos.
- `IMPLEMENTADO, NO EJECUTADO EN ESTE ENTORNO`: pruebas reales del sandbox.
- `CONFIGURADO, NO VALIDADO`: PostgreSQL real y jobs CI nuevos.
- `BLOQUEADO`: Docker Desktop no expuso un daemon durante esta ejecución.

No se afirma aislamiento absoluto. La conclusión admisible tras ejecutar la
campaña Docker es: bajo las versiones, configuración e hipótesis registradas, la
campaña no consiguió vulnerar las propiedades ensayadas.
