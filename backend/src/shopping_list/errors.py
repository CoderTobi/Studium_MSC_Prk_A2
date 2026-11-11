"""Uniform error handling.

Every error leaves the backend as an ``ErrorResponse`` (see ``api/openapi.yaml``):

    {"error": {"code": "...", "message": "...", "requestId": "...", ...}}

``message`` is always one of the fixed texts below (or a fixed template), so it can
never contain stack traces, prompt content or model output.
"""

import re
from collections.abc import Iterable, Mapping, Sequence
from enum import StrEnum
from typing import Any

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.routing import Route, compile_path

from shopping_list.request_context import current_request_id


class ErrorCode(StrEnum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    PROMPT_EMPTY = "PROMPT_EMPTY"
    PROMPT_TOO_LONG = "PROMPT_TOO_LONG"
    UNAUTHENTICATED = "UNAUTHENTICATED"
    ITEM_NOT_FOUND = "ITEM_NOT_FOUND"
    NOT_FOUND = "NOT_FOUND"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    ITEM_LIMIT_REACHED = "ITEM_LIMIT_REACHED"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
    UNSUPPORTED_MEDIA_TYPE = "UNSUPPORTED_MEDIA_TYPE"
    PROMPT_REJECTED = "PROMPT_REJECTED"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    AI_INVALID_RESPONSE = "AI_INVALID_RESPONSE"
    AI_UNAVAILABLE = "AI_UNAVAILABLE"
    AI_TIMEOUT = "AI_TIMEOUT"


HTTP_STATUS: Mapping[ErrorCode, int] = {
    ErrorCode.VALIDATION_ERROR: 400,
    ErrorCode.PROMPT_EMPTY: 400,
    ErrorCode.PROMPT_TOO_LONG: 400,
    ErrorCode.UNAUTHENTICATED: 401,
    ErrorCode.ITEM_NOT_FOUND: 404,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.METHOD_NOT_ALLOWED: 405,
    ErrorCode.ITEM_LIMIT_REACHED: 409,
    ErrorCode.PAYLOAD_TOO_LARGE: 413,
    ErrorCode.UNSUPPORTED_MEDIA_TYPE: 415,
    ErrorCode.PROMPT_REJECTED: 422,
    ErrorCode.RATE_LIMIT_EXCEEDED: 429,
    ErrorCode.INTERNAL_ERROR: 500,
    ErrorCode.AI_INVALID_RESPONSE: 502,
    ErrorCode.AI_UNAVAILABLE: 503,
    ErrorCode.AI_TIMEOUT: 504,
}

DEFAULT_MESSAGES: Mapping[ErrorCode, str] = {
    ErrorCode.VALIDATION_ERROR: "The request contains invalid fields.",
    ErrorCode.PROMPT_EMPTY: "Please describe what you would like to eat.",
    ErrorCode.PROMPT_TOO_LONG: "The prompt is too long.",
    ErrorCode.UNAUTHENTICATED: "Please sign in to continue.",
    ErrorCode.ITEM_NOT_FOUND: "The item was not found.",
    ErrorCode.NOT_FOUND: "The requested resource does not exist.",
    ErrorCode.METHOD_NOT_ALLOWED: "This method is not allowed for this resource.",
    ErrorCode.ITEM_LIMIT_REACHED: "Your shopping list is full. Remove some items first.",
    ErrorCode.PAYLOAD_TOO_LARGE: "The request is too large.",
    ErrorCode.UNSUPPORTED_MEDIA_TYPE: "The request body must be JSON.",
    ErrorCode.PROMPT_REJECTED: (
        "Your prompt could not be processed. Please describe a meal or dish you would like to cook."
    ),
    ErrorCode.RATE_LIMIT_EXCEEDED: "Too many requests. Please wait a moment and try again.",
    ErrorCode.INTERNAL_ERROR: "Something went wrong. Please try again later.",
    ErrorCode.AI_INVALID_RESPONSE: "The AI returned an unusable answer. Please try again.",
    ErrorCode.AI_UNAVAILABLE: "The AI service is currently unavailable. Please try again later.",
    ErrorCode.AI_TIMEOUT: "The AI took too long to respond. Please try again.",
}

# Limits from the FieldError / ErrorResponse schemas.
_MAX_DETAILS = 50
_MAX_FIELD_LENGTH = 100
_MAX_ISSUE_LENGTH = 200


class ApiError(Exception):
    """An error that is answered with a defined ``ErrorResponse``.

    Raise it anywhere in request handling (routers, dependencies, repositories,
    services); the registered handler turns it into the JSON response.
    """

    def __init__(
        self,
        code: ErrorCode,
        message: str | None = None,
        *,
        details: Sequence[Mapping[str, str]] | None = None,
        retry_after_seconds: int | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(code.value)
        self.code = code
        self.message = message or DEFAULT_MESSAGES[code]
        self.details = list(details) if details is not None else None
        self.retry_after_seconds = retry_after_seconds
        self.headers = dict(headers or {})


def error_response(
    code: ErrorCode,
    message: str | None = None,
    *,
    details: Sequence[Mapping[str, str]] | None = None,
    retry_after_seconds: int | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    error: dict[str, Any] = {
        "code": code.value,
        "message": message or DEFAULT_MESSAGES[code],
        "requestId": current_request_id(),
    }
    response_headers = dict(headers or {})
    if code is ErrorCode.VALIDATION_ERROR and details:
        error["details"] = list(details)[:_MAX_DETAILS]
    if code is ErrorCode.RATE_LIMIT_EXCEEDED and retry_after_seconds is not None:
        error["retryAfterSeconds"] = retry_after_seconds
        response_headers["Retry-After"] = str(retry_after_seconds)
    if code is ErrorCode.UNAUTHENTICATED:
        response_headers["WWW-Authenticate"] = "Bearer"
    return JSONResponse({"error": error}, status_code=HTTP_STATUS[code], headers=response_headers)


def field_errors(errors: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    """Convert pydantic errors into ``FieldError`` entries.

    Only the location and pydantic's generic message are used. The rejected input
    value is never echoed back.
    """
    result: list[dict[str, str]] = []
    for err in errors[:_MAX_DETAILS]:
        loc = list(err.get("loc", ()))
        # FastAPI prefixes request parameters with their location.
        if loc and loc[0] in {"body", "path", "query", "header", "cookie"}:
            loc = loc[1:]
        field = ""
        for part in loc:
            if isinstance(part, int):
                field += f"[{part}]"
            else:
                field += f".{part}" if field else str(part)
        issue = str(err.get("msg", "is invalid")).removeprefix("Value error, ")
        result.append(
            {
                "field": (field or "body")[:_MAX_FIELD_LENGTH],
                "issue": issue[:_MAX_ISSUE_LENGTH],
            }
        )
    return result


_HTTP_STATUS_TO_CODE: Mapping[int, ErrorCode] = {
    400: ErrorCode.VALIDATION_ERROR,
    401: ErrorCode.UNAUTHENTICATED,
    404: ErrorCode.NOT_FOUND,
    405: ErrorCode.METHOD_NOT_ALLOWED,
    413: ErrorCode.PAYLOAD_TOO_LARGE,
    415: ErrorCode.UNSUPPORTED_MEDIA_TYPE,
    429: ErrorCode.RATE_LIMIT_EXCEEDED,
}


async def _handle_api_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ApiError)
    return error_response(
        exc.code,
        exc.message,
        details=exc.details,
        retry_after_seconds=exc.retry_after_seconds,
        headers=exc.headers,
    )


async def _handle_validation_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    return error_response(ErrorCode.VALIDATION_ERROR, details=field_errors(exc.errors()))


class RouteMethodIndex:
    """Which HTTP methods each path supports, for the ``Allow`` header of 405 responses.

    Starlette's own ``Allow`` header only lists the methods of the first route that
    matches the path, but e.g. ``GET /items`` and ``POST /items`` are separate routes.
    Built once from the routers' public route list in ``create_app``.
    """

    def __init__(self, prefix: str, routers: Iterable[APIRouter]) -> None:
        self._entries: list[tuple[re.Pattern[str], frozenset[str]]] = []
        for router in routers:
            for route in router.routes:
                if isinstance(route, Route) and route.methods:
                    regex, _, _ = compile_path(prefix + route.path)
                    self._entries.append((regex, frozenset(route.methods)))

    def allowed_methods(self, path: str) -> str:
        methods: set[str] = set()
        for regex, route_methods in self._entries:
            if regex.match(path):
                methods |= route_methods
        return ", ".join(sorted(methods))


async def _handle_http_exception(request: Request, exc: Exception) -> JSONResponse:
    """Framework-level errors such as unknown routes (404) or wrong methods (405)."""
    assert isinstance(exc, StarletteHTTPException)
    code = _HTTP_STATUS_TO_CODE.get(exc.status_code, ErrorCode.INTERNAL_ERROR)
    headers = {}
    if code is ErrorCode.METHOD_NOT_ALLOWED:
        index: RouteMethodIndex = request.app.state.route_methods
        headers["Allow"] = index.allowed_methods(request.url.path)
    return error_response(code, headers=headers)


def register_exception_handlers(app: FastAPI) -> None:
    """Register handlers for all expected errors.

    Unexpected exceptions are not handled here but in ``ErrorGuardMiddleware``, so that
    the resulting 500 response still passes through the CORS and request ID middleware.
    """
    app.add_exception_handler(ApiError, _handle_api_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)
