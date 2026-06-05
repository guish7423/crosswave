"""Centralized exception hierarchy + handlers for CrossWave."""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("crosswave")


class AppError(Exception):
    """Base class for all application errors."""

    def __init__(self, message: str, code: str = "INTERNAL_ERROR", status: int = 500):
        self.message = message
        self.code = code
        self.status = status


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message=message, code="NOT_FOUND", status=404)


class ValidationError(AppError):
    def __init__(self, message: str):
        super().__init__(message=message, code="VALIDATION_ERROR", status=422)


class ExternalServiceError(AppError):
    def __init__(self, message: str = "External service unavailable"):
        super().__init__(message=message, code="EXTERNAL_ERROR", status=502)


def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers on the given app instance."""

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):  # noqa: RUF100
        return JSONResponse(
            status_code=exc.status,
            content={"error": exc.code, "detail": exc.message},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):  # noqa: RUF100
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": "HTTP_ERROR", "detail": exc.detail},
        )

    # Catch-all via middleware (avoids Starlette's ServerErrorMiddleware issue)
    @app.middleware("http")
    async def catch_all_exceptions(request: Request, call_next):  # noqa: RUF100
        try:
            return await call_next(request)
        except Exception:
            logger.exception("Unhandled exception in request %s %s", request.method, request.url.path)
            return JSONResponse(
                status_code=500,
                content={"error": "INTERNAL_ERROR", "detail": "An unexpected error occurred"},
            )
