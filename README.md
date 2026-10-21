# InprogressBK-DashboardA.C.E.

API de comercio exterior, Fase 1. Python 3.13+, FastAPI y SQLAlchemy con
SQLite; separación simple en routers, services, repositories, models,
schemas, core y db. Las reglas y transacciones viven en services.

## Preparación

```sh
uv sync --locked
export JWT_SECRET="$(openssl rand -hex 32)"
export DATABASE_URL='sqlite:///./comercio_exterior.db'
uv run --locked python -m app.db.init
uv run --locked uvicorn app.main:create_app --factory --reload
```

Ejecutar desde la raíz del checkout de desarrollo. El comando db.init crea
solo tablas ausentes; no carga datos ni modifica tablas existentes. No se
inicializa la base automáticamente al arrancar. Para usar los datos provistos,
hacer una copia SQLite de trabajo y apuntar DATABASE_URL a esa copia.

**No ejecutar setup.py sobre una base existente:** elimina el archivo antes
de comprobar el CSV. Se conserva sin cambios. `setup.md` es la documentación
original; usar `uv sync --locked` en lugar de `uv pip sync` sin argumentos.

`JWT_SECRET` es obligatorio (mínimo 32 caracteres, aleatorio); nunca subirlo.
Se puede usar un `.env` local ignorado. `ACCESS_TOKEN_EXPIRE_MINUTES` vale 30.
La URL es configurable para facilitar una migración futura; PostgreSQL no se
ha validado y requiere driver/migraciones. Las pruebas no usan la base original.

## Pruebas

```sh
uv run --locked pytest
uv run --locked ruff check app tests
```

Alcance pendiente: KPIs, caché, Docker, logs estructurados y despliegue.
Consultar docs/superpowers/specs/2026-10-21-phase-1.md para hallazgos del setup.
