import pytest

from app.config import Settings


def test_defaults_match_architecture() -> None:
    settings = Settings(_env_file=None)
    assert settings.llm_model == "claude-sonnet-5-5"
    assert settings.embedding_model == "text-embedding-3-small"
    assert (settings.top_k, settings.candidate_k, settings.per_doc_quota) == (6, 30, 3)
    assert settings.safety_window_turns == 3
    assert not settings.is_production


def test_allowed_origins_parsed_from_comma_separated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://app.example.com, http://localhost:3000 ,")
    settings = Settings(_env_file=None)
    assert settings.allowed_origins == ["https://app.example.com", "http://localhost:3000"]


def test_secrets_are_not_leaked_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-should-not-appear")
    settings = Settings(_env_file=None)
    assert "sk-ant-should-not-appear" not in repr(settings)


def test_invalid_environment_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "staging-ish")
    with pytest.raises(ValueError):
        Settings(_env_file=None)
