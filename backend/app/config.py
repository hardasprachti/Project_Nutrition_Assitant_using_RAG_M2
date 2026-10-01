"""Application settings, loaded from environment variables (and a repo-root `.env` if present)."""

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["local", "production"] = "local"

    # LLM and embeddings. Optional so the app (health, migrations) runs without them;
    # the code paths that need them must fail loudly when they are missing.
    anthropic_api_key: SecretStr | None = None
    llm_model: str = "claude-sonnet-5-5"
    openai_api_key: SecretStr | None = None
    embedding_model: str = "text-embedding-3-small"

    database_url: str = "postgresql+psycopg://nutrition:nutrition@localhost:5432/nutrition"

    admin_token: SecretStr | None = None
    allowed_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    # Retrieval tunables (tuned from the Phase 2 evaluation)
    top_k: int = Field(6, ge=1)
    candidate_k: int = Field(30, ge=1)
    per_doc_quota: int = Field(3, ge=1)
    min_similarity: float = Field(0.30, ge=0.0, le=1.0)

    history_turns: int = Field(6, ge=0)
    safety_window_turns: int = Field(3, ge=1)
    safety_similarity_threshold: float = Field(0.80, ge=0.0, le=1.0)

    rate_limit_per_min: int = Field(20, ge=1)

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        # NoDecode hands us the raw env string: "https://a.example,https://b.example"
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
