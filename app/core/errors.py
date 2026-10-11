"""Standardized error envelope: {"error": {"code", "message", ["details"]}}. No internals leak."""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger(__name__)

_CODES = {400: "bad_request", 401: "unauthorized", 403: "forbidden", 404: "not_found",
          405: "method_not_allowed", 409: "conflict", 413: "payload_too_large",
          422: "validation_error", 429: "rate_limited"}


def envelope(status: int, code: str, message: str, details=None) -> dict:
    err: dict = {"code": code, "message": message}
    if details is not None:
        err["details"] = details
    return {"error": err}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        code = _CODES.get(exc.status_code, "error" if exc.status_code < 500 else "server_error")
        msg = exc.detail if isinstance(exc.detail, str) else code.replace("_", " ")
        return JSONResponse(envelope(exc.status_code, code, msg), exc.status_code,
                            headers=getattr(exc, "headers", None))

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        # Only location + message: never echo submitted input (may contain secrets).
        details = [{"loc": [str(x) for x in e.get("loc", ())], "message": str(e.get("msg", ""))}
                   for e in exc.errors()]
        return JSONResponse(envelope(422, "validation_error", "Request validation failed",
                                     details), 422)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        log.error("Unhandled error on %s %s", request.method, request.url.path,
                  exc_info=(type(exc), exc, exc.__traceback__))
        return JSONResponse(envelope(500, "internal_error", "Internal server error"), 500)
