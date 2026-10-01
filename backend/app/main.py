import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health
from app.api.errors import register_error_handlers
from app.config import get_settings
from app.logging.middleware import RequestIdMiddleware
from app.logging.setup import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()

    # /docs and the OpenAPI schema are disabled in production (Architecture §15, §19).
    docs = None if settings.is_production else "/docs"
    app = FastAPI(
        title="AI Nutrition Assistant",
        docs_url=docs,
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type", "X-Session-Token", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    # Added last so it is outermost: every response, including CORS preflights, gets a request id.
    app.add_middleware(RequestIdMiddleware)
    register_error_handlers(app)

    app.include_router(health.router, prefix="/api")

    logging.getLogger(__name__).info("app started", extra={"environment": settings.environment})
    return app


app = create_app()
