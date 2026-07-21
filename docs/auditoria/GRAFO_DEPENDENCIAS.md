# Grafo de dependencias

El grafo se obtuvo de los imports y de las llamadas observadas en el commit inicial.
Las flechas indican dependencia en tiempo de ejecución.

```mermaid
flowchart TD
    FE[Frontend HTML CSS JavaScript] --> API[FastAPI backend.main]
    API --> AUTH[routers.auth y security]
    API --> EXAM[routers.exam]
    API --> SUB[routers.submission]
    API --> AUD[routers.audit]
    API --> ADM[routers.admin]
    AUTH --> CRUD[backend.crud]
    EXAM --> CRUD
    SUB --> CRUD
    SUB --> GRADER[backend.grader]
    AUD --> CRUD
    ADM --> CRUD
    ADM --> GRADER
    CRUD --> ORM[models y Session SQLAlchemy]
    GRADER --> TEMPLATE[template_engine]
    GRADER --> RUNNER[runner local o Docker]
    RUNNER --> POLICY[policy AST]
    ORM --> DB[(SQLite o PostgreSQL)]
    DBINIT[database y migraciones] --> ORM
    SEED[datos iniciales y scripts] --> ORM
```

## Dependencias relevantes para el orden de cambio

| Nivel | Módulos | Consumidores principales | Estrategia |
| --- | --- | --- | --- |
| 0 | `config.py`, `errors.py`, `sandbox/policy.py` | Todo el backend | Cambios pequeños y pruebas unitarias |
| 1 | `models.py`, `migraciones.py`, `database.py` | CRUD, routers, scripts, pruebas | Migraciones compatibles antes de usar nuevos campos |
| 2 | `crud.py` y nuevos servicios de aplicación | Todos los casos de uso | Sacar el control transaccional de auxiliares compuestos |
| 3 | `grader.py`, runners | Envío y revisión | Mantener ejecución fuera de transacciones largas |
| 4 | Routers | API pública y frontend | Añadir contratos sin romper rutas existentes |
| 5 | Frontend | Navegador | Integrar borradores y flujos multimedia tras estabilizar API |
| 6 | Scripts, CI y documentación | Reproducción | Ejecutar y registrar el sistema final, no una arquitectura supuesta |

## Límite transaccional inicial

```mermaid
sequenceDiagram
    participant API as router submission
    participant CRUD as backend.crud
    participant DB as base de datos
    API->>CRUD: reclamar_entrega
    CRUD->>DB: UPDATE + COMMIT
    API->>CRUD: guardar_respuestas
    CRUD->>DB: DELETE/INSERT + COMMIT
    API->>API: ejecutar corrector/sandbox
    API->>CRUD: guardar_calificacion
    CRUD->>DB: INSERT/UPDATE + COMMIT
    API->>CRUD: cerrar_entrega
    CRUD->>DB: UPDATE + COMMIT
```

El objetivo es conservar una reserva breve, ejecutar el sandbox sin transacción
abierta y transferir la fase final a un servicio que sea dueño de un único
`BEGIN/COMMIT/ROLLBACK`.

## Fronteras de confianza iniciales

```mermaid
flowchart LR
    B[Navegador no confiable] --> A[API]
    A --> P[(Persistencia)]
    A --> L[Subproceso local de desarrollo]
    A -. adaptador opcional .-> D[Daemon Docker]
    D --> C[Contenedor efímero]
```

La API usa directamente el cliente Docker cuando se activa. No existe todavía un
trabajador independiente ni se ha validado el daemon de esta máquina.
