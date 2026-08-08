"""
Custom exceptions and global error handlers.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging

logger = logging.getLogger("jarvis")

class JarvisException(Exception):
    """Base exception for all JARVIS exceptions."""
    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class LLMServiceError(JarvisException):
    """Raised when an LLM service operation fails."""
    def __init__(self, message: str):
        super().__init__(message, status_code=502)


class ConfigurationError(JarvisException):
    """Raised when there is an issue with the application configuration."""
    def __init__(self, message: str):
        super().__init__(message, status_code=500)


def setup_exception_handlers(app: FastAPI) -> None:
    """Registers exception handlers for custom and standard exceptions."""
    
    @app.exception_handler(JarvisException)
    async def jarvis_exception_handler(request: Request, exc: JarvisException) -> JSONResponse:
        logger.error(f"JarvisException: {exc.message} on {request.url.path}")
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message, "error_type": exc.__class__.__name__},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        logger.error(f"HTTPException {exc.status_code}: {exc.detail} on {request.url.path}")
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "error_type": "HTTPException"},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        logger.error(f"Validation error on {request.url.path}: {exc.errors()}")
        return JSONResponse(
            status_code=422,
            content={"detail": "Request validation failed", "errors": exc.errors(), "error_type": "ValidationError"},
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.critical(f"Unhandled exception: {str(exc)} on {request.url.path}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "An internal server error occurred.", "error_type": "InternalServerError"},
        )
