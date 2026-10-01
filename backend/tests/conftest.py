from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.config import get_settings
from app.main import app


def _database_reachable() -> bool:
    engine = create_engine(get_settings().database_url, connect_args={"connect_timeout": 3})
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        return False
    finally:
        engine.dispose()
    return True


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip `integration` tests when no Postgres is reachable at DATABASE_URL."""
    integration = [item for item in items if "integration" in item.keywords]
    if integration and not _database_reachable():
        skip = pytest.mark.skip(reason="Postgres is not reachable at DATABASE_URL")
        for item in integration:
            item.add_marker(skip)


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
        app.dependency_overrides.clear()
