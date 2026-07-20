from collections.abc import Mapping
from typing import Any, cast

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ExceptionHandler


class ApiErrorDetails(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    code: str
    message: str
    field_errors: dict[str, list[str]] | None = Field(default=None, alias="fieldErrors")


class ApiErrorEnvelope(BaseModel):
    error: ApiErrorDetails


class ApiError(HTTPException):
    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        field_errors: Mapping[str, list[str]] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=message, headers=headers)
        self.code = code
        self.message = message
        self.field_errors = dict(field_errors) if field_errors is not None else None


def install_api_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(
        StarletteHTTPException,
        cast(ExceptionHandler, api_http_exception_handler),
    )
    app.add_exception_handler(
        RequestValidationError,
        cast(ExceptionHandler, api_validation_exception_handler),
    )


async def api_http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> Response:
    if not _is_api_request(request):
        return await http_exception_handler(request, exc)

    if isinstance(exc, ApiError):
        return _error_response(
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
            field_errors=exc.field_errors,
            headers=exc.headers,
        )

    return _error_response(
        status_code=exc.status_code,
        code=_default_error_code(exc.status_code),
        message=_safe_http_message(exc),
        headers=exc.headers,
    )


async def api_validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> Response:
    if not _is_api_request(request):
        return await request_validation_exception_handler(request, exc)

    return _error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        code="validation_error",
        message="Проверьте переданные данные.",
        field_errors=_validation_field_errors(exc),
    )


def _error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    field_errors: Mapping[str, list[str]] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    envelope = ApiErrorEnvelope(
        error=ApiErrorDetails(
            code=code,
            message=message,
            fieldErrors=dict(field_errors) if field_errors is not None else None,
        )
    )
    return JSONResponse(
        status_code=status_code,
        content=envelope.model_dump(mode="json", by_alias=True, exclude_none=True),
        headers=dict(headers) if headers is not None else None,
    )


def _validation_field_errors(exc: RequestValidationError) -> dict[str, list[str]]:
    field_errors: dict[str, list[str]] = {}
    for error in exc.errors():
        field_name = _field_name(error.get("loc"))
        message = str(error.get("msg", "Некорректное значение."))
        field_errors.setdefault(field_name, []).append(message)
    return field_errors


def _field_name(location: Any) -> str:
    if not isinstance(location, tuple | list):
        return "request"
    visible_parts = [str(part) for part in location if part not in {"body", "path", "query"}]
    return ".".join(visible_parts) or "request"


def _is_api_request(request: Request) -> bool:
    return request.url.path == "/api" or request.url.path.startswith("/api/")


def _safe_http_message(exc: StarletteHTTPException) -> str:
    if isinstance(exc.detail, str):
        return exc.detail
    return "Запрос не может быть выполнен."


def _default_error_code(status_code: int) -> str:
    return {
        status.HTTP_400_BAD_REQUEST: "bad_request",
        status.HTTP_401_UNAUTHORIZED: "unauthorized",
        status.HTTP_403_FORBIDDEN: "forbidden",
        status.HTTP_404_NOT_FOUND: "not_found",
        status.HTTP_409_CONFLICT: "conflict",
        status.HTTP_422_UNPROCESSABLE_ENTITY: "validation_error",
    }.get(status_code, "http_error")
