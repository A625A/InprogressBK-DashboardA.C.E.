from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.orm import sessionmaker

from app.core.cache import DashboardCache
from app.core.config import Settings
from app.core.observability import configure_observability
from app.db.session import build_engine
from app.routers.auth import router as auth_router
from app.routers.dashboard import router as dashboard_router
from app.routers.dimensions import router as dimensions_router
from app.routers.polizas import router as polizas_router


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    engine = build_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        engine.dispose()

    app = FastAPI(
        title="API de Comercio Exterior",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.dashboard_cache = DashboardCache(settings.dashboard_cache_ttl_seconds)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = sessionmaker(engine, expire_on_commit=False)

    configure_observability(app)

    app.include_router(auth_router)
    app.include_router(dashboard_router)
    app.include_router(polizas_router)
    app.include_router(dimensions_router)
    return app
