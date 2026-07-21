# Estado de la infraestructura externa

Fecha de observación: 2026-07-21. Rama candidata local: `cierre-tfg-2026`.
El hash final se conserva en el paquete externo de evidencias.

## Docker y sandbox real

Estado: `BLOQUEADO`.

El cliente Docker 29.5.3 y Compose 5.1.4 están instalados. `docker info` no pudo
conectar con `npipe:////./pipe/docker_engine` porque el daemon no estaba
disponible. No se inició ni modificó Docker Desktop durante esta comprobación.

Por ello no se construyó la imagen, no se ejecutaron contenedores, no se produjo
SBOM de la imagen final y no se ejecutó la campaña adversaria. Las opciones del
adaptador y las pruebas reales quedaron `IMPLEMENTADO, NO EJECUTADO EN ESTE
ENTORNO`; los Dockerfiles y digests quedaron `CONFIGURADO, NO VALIDADO`.

Comando pendiente, solo en una máquina aislada sin datos personales:

```powershell
docker build -f Dockerfile.sandbox -t evaluador-sandbox:local .
$env:SANDBOX_IMAGE='evaluador-sandbox:local'
$env:RUN_DOCKER_SANDBOX_TESTS='1'
$env:ALLOW_DESTRUCTIVE_SANDBOX_TESTS='1'
python scripts/verificar_sandbox_docker.py
```

## PostgreSQL

Estado: `CONFIGURADO, NO VALIDADO` y ejecución local `BLOQUEADO` por el mismo
daemon. Se validó de forma estática `docker-compose.postgresql.yml`, se añadió
un job CI y existen pruebas que reinician una base efímera, aplican migraciones y
ejercitan atomicidad/concurrencia. En la suite portable estas pruebas quedan
omitidas si `POSTGRES_TEST_URL` no está definido; una omisión no es un aprobado.

```powershell
docker compose -f docker-compose.postgresql.yml up -d --wait
$env:POSTGRES_TEST_URL='postgresql+psycopg2://evaluador_test:evaluador_test_local@127.0.0.1:55432/evaluador_test'
$env:ALLOW_POSTGRES_TEST_RESET='1'
python scripts/verificar_postgresql.py
docker compose -f docker-compose.postgresql.yml down -v
```

## CI

Estado: `CONFIGURADO, NO VALIDADO`.

El flujo separa calidad, pruebas, seguridad, navegador, aislamiento, PostgreSQL y
evidencia. No se publicó ni observó una ejecución remota durante este trabajo, por
lo que el archivo YAML no debe citarse como resultado de CI aprobado.
