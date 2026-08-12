from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def _envelope(*, code: str, message: str, request_id: str | None, details: object = None) -> dict:
    body = {"error": {"code": code, "message": message, "request_id": request_id}}
    if details is not None:
        body["error"]["details"] = details
    return body


def _sanitize_validation_errors(errors: list[dict]) -> list[dict]:
    """
    Pydantic v2's exc.errors() includes the original exception instance at
    error['ctx']['error'] for validators that raise ValueError/AssertionError. That's
    great for debugging in-process but is not JSON-serializable, so we stringify it
    before it ever reaches JSONResponse.
    """
    sanitized = []
    for err in errors:
        clean = dict(err)
        ctx = clean.get("ctx")
        if isinstance(ctx, dict) and "error" in ctx:
            clean["ctx"] = {**ctx, "error": str(ctx["error"])}
        sanitized.append(clean)
    return sanitized


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(code=_code_for_status(exc.status_code), message=str(exc.detail), request_id=request_id),
            headers=exc.headers or {},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_envelope(
                code="validation_error",
                message="Request validation failed",
                request_id=request_id,
                details=_sanitize_validation_errors(exc.errors()),
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_envelope(code="internal_error", message="An unexpected error occurred", request_id=request_id),
        )


_STATUS_CODE_NAMES = {
    400: "bad_request",
    401: "unauthorized",
    402: "payment_required",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    422: "validation_error",
    423: "locked",
    429: "rate_limited",
}


def _code_for_status(status_code: int) -> str:
    return _STATUS_CODE_NAMES.get(status_code, "error")
