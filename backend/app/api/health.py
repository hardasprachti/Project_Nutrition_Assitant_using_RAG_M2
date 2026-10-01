import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_session

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health")
def health(session: Annotated[Session, Depends(get_session)]) -> JSONResponse:
    """Liveness plus a database and pgvector-extension check (used as the Railway health check)."""
    try:
        session.execute(text("SELECT 1"))
        version = session.execute(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        ).scalar_one_or_none()
    except Exception:
        logger.exception("health check: database unreachable")
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "database": "unreachable", "vector_extension": None},
        )

    if version is None:
        logger.error("health check: pgvector extension is not installed")
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "database": "ok", "vector_extension": None},
        )
    return JSONResponse(
        content={"status": "ok", "database": "ok", "vector_extension": str(version)}
    )
