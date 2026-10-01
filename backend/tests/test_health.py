from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_session
from app.main import app


class _BrokenSession:
    def execute(self, *args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("connection refused")


def test_health_reports_503_when_database_is_down(client: TestClient) -> None:
    app.dependency_overrides[get_session] = lambda: _BrokenSession()
    response = client.get("/api/health")
    assert response.status_code == 503
    assert response.json()["status"] == "unhealthy"


@pytest.mark.integration
def test_health_ok_with_real_database(client: TestClient) -> None:
    from alembic import command
    from alembic.config import Config

    from tests.test_migrations import ALEMBIC_INI

    command.upgrade(Config(str(ALEMBIC_INI)), "head")  # the extension is created by migration 0001
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["vector_extension"]


def test_unknown_route_uses_the_standard_error_shape(client: TestClient) -> None:
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "not_found"
    assert error["request_id"] == response.headers["X-Request-ID"]


def test_request_id_header_is_generated_and_accepted(client: TestClient) -> None:
    generated = client.get("/api/does-not-exist").headers["X-Request-ID"]
    assert len(generated) == 32

    echoed = client.get("/api/does-not-exist", headers={"X-Request-ID": "trace-abc-12345"})
    assert echoed.headers["X-Request-ID"] == "trace-abc-12345"

    rejected = client.get("/api/does-not-exist", headers={"X-Request-ID": "bad id\twith junk"})
    assert rejected.headers["X-Request-ID"] != "bad id\twith junk"


def test_cors_allows_configured_origin_only(client: TestClient) -> None:
    allowed = client.get("/api/does-not-exist", headers={"Origin": "http://localhost:3000"})
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:3000"
    blocked = client.get("/api/does-not-exist", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in blocked.headers
