from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.db.session import build_engine
from app.routers.auth import router as auth_router


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
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = sessionmaker(engine, expire_on_commit=False)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request, error):
        # Pydantic errors include raw inputs by default; never echo credentials.
        details = [
            {key: value for key, value in item.items() if key in {"loc", "msg", "type"}}
            for item in error.errors()
        ]
        return JSONResponse(status_code=422, content={"detail": details})

    app.include_router(auth_router)
    return app
