from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AGENTFLOW_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "agentflow-api"
    app_version: str = "0.1.0"
    environment: str = "development"
    check_dependencies: bool = True
    cors_allowed_origins: str = "http://localhost:3000"

    database_url: str = "postgresql+psycopg://agentflow:agentflow@localhost:5432/agentflow"
    redis_url: str = "redis://localhost:6379/0"
    worker_id: str = "worker"
    worker_poll_interval_seconds: int = 30
    worker_lease_seconds: int = 60
    worker_max_runs_per_cycle: int = 10

    minio_endpoint_url: str = "http://localhost:9000"
    minio_access_key: str = "agentflow"
    minio_secret_key: SecretStr = Field(default=SecretStr("agentflowsecret"))
    minio_bucket: str = "agentflow-artifacts"
    minio_region: str = "us-east-1"

    dev_user_email: str = "dev@agentflow.local"
    dev_user_display_name: str = "Development Admin"
    default_workspace_name: str = "Default Workspace"
    default_workspace_slug: str = "default"
    api_auth_key: SecretStr = Field(default=SecretStr(""))

    llm_api_base_url: str = "https://api.openai.com/v1"
    llm_api_key: SecretStr = Field(default=SecretStr(""))
    llm_model: str = "gpt-4.1-mini"
    embedding_api_base_url: str | None = None
    embedding_api_key: SecretStr = Field(default=SecretStr(""))
    embedding_model: str = "text-embedding-3-small"
    model_request_timeout_seconds: int = 60

    @property
    def model_execution_mode(self) -> str:
        return "api"

    def safe_summary(self) -> dict[str, str | bool | int | list[str]]:
        return {
            "app_name": self.app_name,
            "app_version": self.app_version,
            "environment": self.environment,
            "check_dependencies": self.check_dependencies,
            "cors_allowed_origins": self.cors_allowed_origin_list,
            "database_url": self._redact_url(self.database_url),
            "redis_url": self._redact_url(self.redis_url),
            "worker_id": self.worker_id,
            "worker_poll_interval_seconds": self.worker_poll_interval_seconds,
            "worker_lease_seconds": self.worker_lease_seconds,
            "worker_max_runs_per_cycle": self.worker_max_runs_per_cycle,
            "minio_endpoint_url": self.minio_endpoint_url,
            "dev_user_email": self.dev_user_email,
            "default_workspace_slug": self.default_workspace_slug,
            "api_auth_key": "[REDACTED]" if self.api_auth_key.get_secret_value() else "",
            "llm_api_base_url": self.llm_api_base_url,
            "llm_api_key": "[REDACTED]",
            "llm_model": self.llm_model,
            "embedding_api_base_url": self.resolved_embedding_api_base_url,
            "embedding_api_key": "[REDACTED]",
            "embedding_model": self.embedding_model,
            "model_execution_mode": self.model_execution_mode,
            "model_request_timeout_seconds": self.model_request_timeout_seconds,
        }

    @property
    def resolved_embedding_api_base_url(self) -> str:
        return self.embedding_api_base_url or self.llm_api_base_url

    @property
    def resolved_embedding_api_key(self) -> SecretStr:
        if self.embedding_api_key.get_secret_value():
            return self.embedding_api_key
        return self.llm_api_key

    @staticmethod
    def _redact_url(value: str) -> str:
        if "@" not in value or "://" not in value:
            return value
        scheme, rest = value.split("://", 1)
        return f"{scheme}://[REDACTED]@{rest.split('@', 1)[1]}"

    @property
    def cors_allowed_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]
