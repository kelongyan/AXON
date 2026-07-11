from app.core.config import Settings


def test_model_execution_is_api_only():
    settings = Settings(
        llm_api_base_url="https://api.example.com/v1",
        llm_api_key="sk-test-key",
        llm_model="gpt-compatible",
        embedding_model="text-embedding-compatible",
    )

    assert settings.model_execution_mode == "api"
    assert settings.llm_api_base_url == "https://api.example.com/v1"
    assert settings.llm_model == "gpt-compatible"
    assert settings.embedding_model == "text-embedding-compatible"


def test_embedding_provider_can_use_separate_openai_compatible_endpoint():
    settings = Settings(
        llm_api_base_url="https://chat.example.com/v1",
        llm_api_key="sk-chat-key",
        embedding_api_base_url="https://embed.example.com/v1",
        embedding_api_key="sk-embed-key",
        embedding_model="text-embedding-compatible",
    )

    assert settings.embedding_api_base_url == "https://embed.example.com/v1"
    assert settings.embedding_api_key.get_secret_value() == "sk-embed-key"


def test_safe_summary_redacts_model_api_key():
    settings = Settings(llm_api_key="sk-test-key")

    summary = settings.safe_summary()

    assert summary["llm_api_key"] == "[REDACTED]"
    assert summary["embedding_api_key"] == "[REDACTED]"
    assert summary["model_execution_mode"] == "api"


def test_worker_settings_are_configurable_and_visible_in_safe_summary():
    settings = Settings(
        worker_id="worker-east-1",
        worker_poll_interval_seconds=5,
        worker_lease_seconds=90,
        worker_max_runs_per_cycle=3,
    )

    summary = settings.safe_summary()

    assert settings.worker_id == "worker-east-1"
    assert settings.worker_poll_interval_seconds == 5
    assert settings.worker_lease_seconds == 90
    assert settings.worker_max_runs_per_cycle == 3
    assert summary["worker_id"] == "worker-east-1"
    assert summary["worker_poll_interval_seconds"] == 5
    assert summary["worker_lease_seconds"] == 90
    assert summary["worker_max_runs_per_cycle"] == 3
