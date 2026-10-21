import json
import logging
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException


class RequestLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        # Only explicitly selected metadata is serialized, never exception text.
        return json.dumps(
            {
                "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
                "level": record.levelname,
                "request_id": record.request_id,
                "method": record.method,
                "path": record.path,
                "status_code": record.status_code,
            }
        )


logger = logging.getLogger("app.requests")
logger.setLevel(logging.INFO)
logger.propagate = False
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(RequestLogFormatter())
    logger.addHandler(handler)


def internal_error() -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": "Error interno del servidor"})


def configure_observability(app: FastAPI) -> None:
    # Uvicorn's access log includes raw paths/query strings; use our safe log instead.
    logging.getLogger("uvicorn.access").disabled = True

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, _error: RequestValidationError):
        # Even error locations may contain user-provided keys with secrets.
        return JSONResponse(status_code=422, content={"detail": "Solicitud inválida"})

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException):
        if error.status_code >= 500:
            return JSONResponse(
                status_code=error.status_code,
                content={"detail": "Error interno del servidor"},
                headers=error.headers,
            )
        # Existing application errors use fixed, safe messages and auth headers.
        return await http_exception_handler(request, error)

    @app.middleware("http")
    async def request_log(request: Request, call_next):
        request_id = str(uuid4())
        request.state.request_id = request_id
        try:
            response = await call_next(request)
        except Exception:  # noqa: BLE001 - final HTTP boundary; never log exception secrets
            response = internal_error()
        response.headers["X-Request-ID"] = request_id
        status = response.status_code
        level = (
            logging.ERROR if status >= 500 else logging.WARNING if status >= 400 else logging.INFO
        )
        route = request.scope.get("route")
        logger.log(
            level,
            "request",
            extra={
                "request_id": request_id,
                "method": request.method,
                # Never log query strings, path parameters, or arbitrary unmatched paths.
                "path": getattr(route, "path", "<unmatched>"),
                "status_code": status,
            },
        )
        return response
