"""Consistent error body (Architecture §15): {"error": {"code", "message", "request_id"}}."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException  # also covers router-level 404/405

logger = logging.getLogger(__name__)

_CODES = {400: "bad_request", 404: "not_found", 405: "method_not_allowed", 429: "rate_limited"}


def _body(request: Request, code: str, message: str) -> dict[str, dict[str, str | None]]:
    request_id = getattr(request.state, "request_id", None)
    return {"error": {"code": code, "message": message, "request_id": request_id}}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        code = _CODES.get(exc.status_code, "http_error")
        return JSONResponse(
            status_code=exc.status_code,
            content=_body(request, code, str(exc.detail)),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Field names only; never echo submitted values back.
        fields = ", ".join(".".join(str(p) for p in e["loc"]) for e in exc.errors())
        return JSONResponse(
            status_code=400, content=_body(request, "invalid_request", f"Invalid fields: {fields}")
        )

    @app.exception_handler(Exception)
    async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
        # This runs outside the request-id middleware, so the contextvar is already reset.
        logger.error(
            "unhandled error",
            exc_info=exc,
            extra={"request_id": getattr(request.state, "request_id", None)},
        )
        return JSONResponse(
            status_code=500, content=_body(request, "internal_error", "Internal server error")
        )
