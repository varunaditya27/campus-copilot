import structlog
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = structlog.stdlib.get_logger(__name__)
_HTTP_ERROR_CODES = {404: "not_found", 405: "method_not_allowed"}


class AppError(Exception):
    """An expected failure with a message that is safe to show the user."""

    def __init__(self, status_code: int, error_code: str, message: str, detail=None):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        self.detail = detail


def _response(status_code: int, error_code: str, message: str, detail=None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error_code": error_code, "message": message, "detail": detail},
    )


async def _app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return _response(exc.status_code, exc.error_code, exc.message, exc.detail)


async def _http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = _HTTP_ERROR_CODES.get(exc.status_code, f"http_{exc.status_code}")
    return _response(exc.status_code, code, str(exc.detail))


async def _validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return _response(
        422, "validation_error", "The request was not valid.", jsonable_encoder(exc.errors())
    )


async def _unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled_exception", exc_info=exc, path=request.url.path)
    return _response(500, "internal_error", "Something went wrong on our side. Please try again.")


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(Exception, _unexpected_error_handler)
