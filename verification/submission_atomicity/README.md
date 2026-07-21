# Modelo ejecutable de atomicidad

Este directorio contiene una exploración explícita y finita de estados de dos
solicitudes concurrentes. Modela reserva, cálculo fuera de transacción,
persistencia atómica, `COMMIT`, `ROLLBACK`, fallo, reintento y observación de un
resultado ya cerrado.

Ejecutar desde la raíz:

```powershell
.\.venv\Scripts\python.exe verification/submission_atomicity/modelo_estados.py --output artifacts/tfg-evidence/<commit>/modelo_formal/salida_modelo.json
```

La salida `ok: true` es una **comprobación exhaustiva del modelo acotado**, no
una demostración formal del código Python, SQLAlchemy, el motor SQL ni Docker.
Las pruebas de inyección de fallos y las restricciones de base de datos aportan
evidencia independiente sobre la implementación real.
