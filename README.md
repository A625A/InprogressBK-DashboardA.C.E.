# InprogressBK-DashboardA.C.E.

API de comercio exterior. Python 3.13+, FastAPI y SQLAlchemy con
SQLite; separación simple en routers, services, repositories, models,
schemas, core y db. Las reglas y transacciones viven en services.

## Arquitectura

Monolito por capas: `app/main.py` construye la aplicación; `routers` define
HTTP y autenticación, `schemas` valida entradas/salidas, `services` aplica
reglas y transacciones, `repositories` consulta SQL y `models` mapea tablas.
`db` gestiona sesiones e inicialización explícita; `core` contiene configuración,
JWT/Argon2id, caché y observabilidad. Las pólizas y sus ítems se guardan en una
transacción. SQLite persiste en disco; la caché de KPIs reside solo en memoria.

Se eligió FastAPI por su validación de contratos con Pydantic y su integración
con autenticación y pruebas HTTP. SQLAlchemy permite expresar consultas
agregadas y controlar las transacciones sin cargar los ítems en memoria.
SQLite mantiene compatibilidad con la base entregada y evita servicios
adicionales. La separación por capas permite probar reglas y consultas por
separado sin añadir la complejidad de microservicios. La caché con TTL en
memoria es suficiente para la ejecución documentada con un único worker.

## Preparación

Requisitos locales: Python 3.13 o superior y uv. Docker usa Python 3.13,
compatible con `requires-python` y las dependencias fijadas en `uv.lock`.

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

## Docker

Requiere Docker Engine activo y Docker Compose. Ejecutar desde este checkout.
En equipos con Compose independiente, sustituir `docker compose` por
`docker-compose` en todos los comandos.

```sh
mkdir -p data
export APP_UID="$(id -u)" APP_GID="$(id -g)"
export JWT_SECRET="$(openssl rand -hex 32)"
export DATABASE_URL='sqlite:////data/comercio_exterior.db'
docker compose config --quiet
docker compose build
```

El bind mount conecta `./data` del host con `/data` del contenedor. Se monta el
directorio completo para conservar también archivos journal/WAL de SQLite.
Debe existir y permitir escritura al UID/GID configurado; Compose no lo crea
silenciosamente. Para otra carpeta usar `SQLITE_DATA_DIR` (preferiblemente una
ruta absoluta). El contenedor se ejecuta sin root por defecto; los UID/GID del
usuario local facilitan los permisos del bind mount en Linux/macOS.

Para trabajar con una base existente, colocar una **copia de trabajo consistente**
en `data/comercio_exterior.db` antes de iniciar. Si la base está en uso, emplear
el mecanismo de backup de SQLite; no copiar únicamente el archivo principal
con escrituras activas. No reemplazar un archivo de destino que ya exista.

La creación de tablas es un paso **manual**, tanto para una base vacía como
para agregar las tablas ausentes (incluida `users`) a una copia existente:

```sh
docker compose run --rm api python -m app.db.init
docker compose up -d
# Una respuesta 401 confirma HTTP y la protección de la ruta, no el estado de la BD.
curl -i http://127.0.0.1:8000/polizas
docker compose logs --tail=50 api
docker compose down
```

La imagen y el arranque no ejecutan `setup.py`, no importan el CSV y no
inicializan ni reemplazan la base. El build solo incluye `app/`, `pyproject.toml`
y `uv.lock`; instala dependencias de ejecución, sin grupos `dev`/`setup` ni el
proyecto como paquete. Los archivos del bind mount sobreviven a `down` y a la
recreación del contenedor; se deben respaldar por separado.

`DATABASE_URL` se pasa al contenedor desde el entorno o `.env`; allí debe apuntar
al destino **dentro** del contenedor (`sqlite:////data/...`, cuatro barras para
una ruta absoluta). La URL local `sqlite:///./...` queda fuera del bind mount:
no usarla en Docker. `SQLITE_DATA_DIR` cambia el origen del mount, no esa URL.
`API_PORT` cambia el puerto del host (8000 por defecto, solo en `127.0.0.1`).
También se admiten `ACCESS_TOKEN_EXPIRE_MINUTES` y `DASHBOARD_CACHE_TTL_SECONDS`.
Conservar el mismo `JWT_SECRET` entre reinicios para mantener la validez de los
tokens; no compartir salidas de `docker compose config` sin `--quiet`, pues
pueden contener el secreto. Se usa un solo worker para la invalidación de caché.

Verificación de esta fase (21/10/2026): configuración Compose validada con
`docker-compose config --quiet`. El cliente Docker está instalado, pero no hay
daemon accesible en `/var/run/docker.sock`; no se pudo construir la imagen ni
realizar el smoke test de arranque/persistencia en contenedor. El despliegue
queda fuera de esta fase.

## Endpoints

Salvo registro y login, todos requieren `Authorization: Bearer <token>`.

| Método | Ruta | Uso |
| --- | --- | --- |
| POST | `/register` | JSON `username` y `password`; crea usuario (201). |
| POST | `/login` | Mismo JSON; devuelve `access_token` y `token_type`. |
| GET | `/dimensions/paises` | Catálogo de países. |
| GET | `/dimensions/aduanas` | Catálogo de aduanas. |
| GET | `/dimensions/tipos-regimen` | Catálogo de regímenes. |
| POST | `/polizas` | Crea cabecera e ítems en una transacción (201). |
| GET | `/polizas` | Lista paginada y filtrada, sin detalle de ítems. |
| GET | `/polizas/{poliza_id}` | Detalle con ítems; 404 si no existe. |
| GET | `/dashboard/kpis/totals` | Totales de pólizas e importaciones. |
| GET | `/dashboard/kpis/top-5` | Rankings de países y productos. |
| GET | `/dashboard/kpis/valor-por-mes?year=2025` | Serie de doce meses. |

`username`: 3–64 caracteres alfanuméricos, `_`, `.` o `-`, sensible a mayúsculas;
`password`: 8–128 caracteres. Las contraseñas se almacenan con Argon2id;
los tokens usan JWT HS256.

`GET /polizas` admite `page` (1 por defecto), `page_size` (20, máximo 100),
`correlativo`, `fecha_desde`, `fecha_hasta`, `aduana_id`, `tipo_regimen_id`,
`pais_id` y `sac_id`. Las fechas usan ISO `YYYY-MM-DD`, el rango es inclusivo y
los filtros se combinan con AND; país y SAC deben coincidir en el mismo ítem.
La respuesta contiene `items`, `total`, `page` y `page_size`, ordenados por ID.

Cuerpo mínimo de ejemplo para `POST /polizas` (usar un correlativo propio):

```json
{"correlativo": 123456, "items": [{"valor_cif_uds": 100.0}]}
```

Las referencias proporcionadas deben existir. Los campos opcionales admiten
nulos según el esquema legado. Errores comunes: 401 sin autenticación válida,
409 por conflicto y 422 por validación. `/docs`, `/redoc` y `/openapi.json` están
deshabilitados. El contrato puede exportarse localmente sin iniciar el servidor:

```sh
uv run --locked python -c 'import json; from app.main import create_app; print(json.dumps(create_app().openapi(), ensure_ascii=False, indent=2))' > /tmp/backend-openapi.json
```

Requiere el mismo `JWT_SECRET` válido de la preparación.

## Pruebas

```sh
uv run --locked pytest
uv run --locked ruff check app tests
```

La suite existente usa SQLite temporal y cubre autenticación, contratos,
transacciones, filtros, KPIs, caché y logs. Para una comprobación acotada:

```sh
uv run --locked pytest tests/test_foundation.py tests/test_auth.py
```

Revisión final contra el PDF original (21/10/2026): **118 pruebas aprobadas
en 11,53 s**, en una única ejecución completa con
`.venv/bin/python -m pytest -p no:cacheprovider`. No se encontraron fallos
funcionales ni se añadieron pruebas. También pasaron
`ruff check --no-cache app tests`, `uv lock --check --offline` y
`docker-compose config --quiet`. El build, arranque y persistencia en Docker
siguen pendientes por falta de un daemon accesible.

La imagen de ejecución no incluye pytest; ejecutar las pruebas en el entorno
local con el grupo `dev` que instala `uv sync --locked`.
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
