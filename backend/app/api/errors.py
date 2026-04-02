import logging
from http import HTTPStatus
from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.schemas.error import ErrorDetail, ErrorResponse

logger = logging.getLogger(__name__)


def _status_label(value: int) -> str:
    try:
        return HTTPStatus(value).phrase
    except ValueError:
        return "Error"


def _status_code_name(value: int) -> str:
    try:
        return HTTPStatus(value).name.lower()
    except ValueError:
        return "unknown_error"


def _normalize_http_details(detail: Any) -> list[ErrorDetail]:
    if isinstance(detail, list):
        return [ErrorDetail(message=str(item)) for item in detail]
    if isinstance(detail, dict):
        if {"field", "message"} <= set(detail):
            return [ErrorDetail(**detail)]
        return [ErrorDetail(message=str(detail))]
    if isinstance(detail, str):
        return [ErrorDetail(message=detail)]
    if detail is None:
        return []
    return [ErrorDetail(message=str(detail))]


def build_error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    details: list[ErrorDetail] | None = None,
) -> JSONResponse:
    payload = ErrorResponse(
        code=code,
        message=message,
        details=details or [],
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump())


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    del request

    details = _normalize_http_details(exc.detail)
    message = details[0].message if len(details) == 1 else _status_label(exc.status_code)

    return build_error_response(
        status_code=exc.status_code,
        code=_status_code_name(exc.status_code),
        message=message,
        details=details,
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    del request

    details = [
        ErrorDetail(
            field=".".join(str(part) for part in error["loc"] if part != "body") or None,
            message=error["msg"],
            type=error["type"],
            input=error.get("input"),
        )
        for error in exc.errors()
    ]

    return build_error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        code="validation_error",
        message="Request validation failed",
        details=details,
    )


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    logger.exception("Unhandled error for %s %s", request.method, request.url.path, exc_info=exc)

    return build_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="internal_server_error",
        message="An unexpected error occurred",
    )
