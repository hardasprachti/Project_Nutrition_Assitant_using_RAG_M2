from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app.config import get_settings

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"

EXPECTED_TABLES = {
    "documents",
    "chunks",
    "conversations",
    "messages",
    "message_sources",
    "claims",
    "failure_logs",
    "eval_questions",
    "eval_runs",
    "eval_results",
}


def _config() -> Config:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(ALEMBIC_INI.parent / "app/db/migrations"))
    return config


@pytest.mark.integration
def test_upgrade_creates_every_table_and_the_hnsw_index() -> None:
    command.upgrade(_config(), "head")
    engine = create_engine(get_settings().database_url)
    try:
        assert set(inspect(engine).get_table_names()) >= EXPECTED_TABLES
        with engine.connect() as connection:
            index_def: str = connection.execute(
                text("SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_chunks_embedding_hnsw'")
            ).scalar_one()
        assert "hnsw" in index_def
        assert "vector_cosine_ops" in index_def
    finally:
        engine.dispose()


@pytest.mark.integration
def test_models_and_migrations_have_not_drifted() -> None:
    """Fails if a model change was made without a migration (`alembic revision --autogenerate`)."""
    command.upgrade(_config(), "head")
    command.check(_config())
