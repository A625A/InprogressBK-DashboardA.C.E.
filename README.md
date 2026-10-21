# InprogressBK-DashboardA.C.E.

API de comercio exterior. Python 3.13+, FastAPI y SQLAlchemy con
SQLite; separación simple en routers, services, repositories, models,
schemas, core y db. Las reglas y transacciones viven en services.

## Preparación

```sh
uv sync --locked
export JWT_SECRET="$(openssl rand -hex 32)"
export DATABASE_URL='sqlite:///./comercio_exterior.db'
uv run --locked python -m app.db.init
uv run --locked uvicorn app.main:create_app --factory --reload --no-access-log
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

Alcance pendiente: Docker y despliegue.
Consultar docs/superpowers/specs/2026-10-21-phase-1.md para hallazgos del setup.


## KPIs

Todos requieren `Authorization: Bearer <token>` y agregan en SQL sobre
`valor_cif_uds`, sin conversión de moneda ni redondeo adicional. Los importes
conservan el tipo FLOAT del esquema original.

`GET /dashboard/kpis/totals` devuelve `total_polizas` y `valor_importado_total`.
Cuenta todas las cabeceras una sola vez, incluidas las que no tienen ítems.
Suma únicamente los ítems vinculados a una póliza; los ítems con `poliza_id`
nulo no representan una declaración y quedan excluidos de todos los KPIs.
SUM ignora valores nulos; una suma vacía o completamente nula devuelve cero.
Los valores negativos existentes se conservan, sin inventar reglas de negocio.

`GET /dashboard/kpis/top-5` devuelve `paises` y `productos`: hasta cinco
filas por ranking, con `id`, metadatos de la dimensión y `valor_importado`.
Ordena por suma descendente y desempata por ID ascendente. Agrupa por ID,
no solo por nombre o descripción. Excluye referencias de dimensión nulas;
los nombres/descripciones nulos de dimensiones existentes se conservan.
Solo aparecen dimensiones con ítems vinculados a pólizas. Por tanto, un
ranking puede contener menos de cinco filas y no tiene por qué sumar el total.

`GET /dashboard/kpis/valor-por-mes?year=2025` exige un año entero entre 1 y
9999; valores inválidos o ausentes devuelven 422. Usa `fecha_declaracion`
para filtrar el año y agrupar por mes. Devuelve `year` y `meses`, con doce
objetos `{ "mes": 1, "valor_importado": 0.0 }` ordenados de enero a diciembre.
Las fechas nulas quedan fuera de la serie mensual, aunque sus importes sí
participan en totales y rankings globales. Python solo completa los meses
faltantes a partir de un máximo de doce filas ya agregadas en SQL.

```sh
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/dashboard/kpis/totals
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/dashboard/kpis/top-5
curl -H "Authorization: Bearer $TOKEN" 'http://127.0.0.1:8000/dashboard/kpis/valor-por-mes?year=2025'
```

Las pruebas de KPIs cubren autenticación, múltiples ítems por póliza,
SUM sin DISTINCT, nulos, datos vacíos, empates, límites del año y agrupación
SQL. Las pruebas unitarias de la serie mensual verifican orden y relleno de
meses; las de integración ejecutan los endpoints contra SQLite temporal.

## Caché de KPIs

Caché en memoria por aplicación/proceso, con TTL absoluto configurable mediante
`DASHBOARD_CACHE_TTL_SECONDS` (60 segundos por defecto; número positivo y finito).
Las claves separan cada endpoint y sus parámetros validados, incluido `year`.
Se guardan únicamente los DTO de agregados correctos: no solicitudes, JWT,
usuarios, contraseñas, detalles de pólizas ni errores. JWT se valida en cada
petición, incluidos los aciertos de caché. Máximo 256 entradas; se eliminan las
expiradas al consultar y la más antigua al alcanzar el límite.

Después del COMMIT exitoso de `POST /polizas` se invalidan totales, rankings y
la serie mensual del año de la nueva póliza. Una fecha nula no afecta series
mensuales. ROLLBACK y errores de validación no invalidan. Una lectura iniciada
antes de la invalidación puede terminar, pero no volver a guardar su resultado
obsoleto en caché. Las pruebas usan reloj simulado y SQLite temporal, sin sleeps.

No requiere servicios adicionales. Cada proceso tiene su propia caché: escrituras
externas u otros workers se reflejan al expirar el TTL de ese proceso. Para
invalidación inmediata por esta API, ejecutar una única instancia/worker.

## Observabilidad y errores

Cada solicitud genera un log JSON en stderr con timestamp UTC, nivel, request_id,
method, path y status_code. Respuestas menores a 400 usan INFO, 4xx WARNING y
5xx ERROR. El servidor genera un UUID por solicitud, disponible en
`request.state.request_id` y en el encabezado `X-Request-ID` de la respuesta.

Se registra la plantilla de ruta (por ejemplo `/polizas/{poliza_id}`) o
`<unmatched>` para rutas desconocidas. Se omiten cuerpos, cabeceras, parámetros,
credenciales y detalles de excepciones. El access log estándar de Uvicorn se
desactiva para evitar que registre URLs con secretos.

Los fallos inesperados devuelven 500 con `Error interno del servidor`; los errores
HTTP explícitos conservan sus códigos y encabezados, con mensaje genérico para
5xx. La validación conserva 422 y devuelve `Solicitud inválida`, sin repetir
valores ni nombres de campos enviados por el cliente. Los demás mensajes HTTP
existentes se conservan. Ninguna respuesta de error incluye tracebacks.

Verificación específica: `uv run --locked pytest tests/test_observability.py tests/test_auth.py tests/test_polizas.py tests/test_queries.py`.
