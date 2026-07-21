# Privacidad y limitaciones

## Finalidad y minimización

La captura se limita a incidencias configuradas (`CAMBIO_PESTANA` y
`PERDIDA_FOCO`) y no aplica penalización automática. El flujo exige una acción
visible previa, consentimiento versionado y permisos de pantalla, cámara y
micrófono. Si el navegador revoca un flujo, se registra la ausencia y se ofrece
una reactivación visible; no se intenta eludir el control del navegador.

Los clips tienen un objetivo máximo de 15 segundos. El cliente graba 14 segundos
para absorber latencia de parada; el servidor rechaza una duración declarada
superior a 15 segundos y limita el tamaño mediante `EVIDENCIA_MAX_BYTES`.

## Almacenamiento y acceso

- El contenido se almacena como BLOB en la base, fuera del frontend público.
- El nombre recibido no se conserva: se genera un UUID y una extensión permitida.
- Se valida el MIME permitido y la firma EBML WebM o `ftyp` MP4.
- La descarga exige rol de profesorado y deja un registro con docente, acción y
  timestamp.
- La eliminación de una entrega propaga el borrado a eventos, evidencias y logs
  mediante claves foráneas/cascadas del modelo.
- `EVIDENCIA_RETENCION_DIAS` define la política técnica; el comando
  `python scripts/depurar_evidencias.py` solo informa y `--aplicar` confirma el
  borrado.
- Los logs de aplicación no incluyen el BLOB ni el código completo del alumnado.

La duración se valida como metadato producido por el cliente, no mediante un
analizador forense del contenedor multimedia. La firma comprueba el formato
básico, no que todas las pistas prometidas sean visibles/audibles. La prueba
automática usa medios sintéticos; no demuestra dispositivos físicos ni la
experiencia de cada navegador.

## Límites jurídicos y operativos

Estos son controles técnicos, no una declaración de cumplimiento jurídico. Antes
de utilizar datos reales se requiere, como mínimo, revisión por la universidad,
base legitimadora, información al alumnado, proporcionalidad, plazos aprobados,
procedimiento de acceso/rectificación/supresión, análisis de accesibilidad y
evaluación de proveedores e infraestructura.

El repositorio usa identidades ficticias. El paquete automático no incluye cara,
voz ni pantalla de una persona. La autenticación sigue siendo de demostración;
un uso académico real requiere OIDC/SSO institucional validado y gestión de altas,
bajas y segundo factor según la política aplicable.
