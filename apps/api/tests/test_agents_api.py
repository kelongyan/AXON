from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.models import Base
from app.main import create_app
from app.services.llm import LLMCompletion, LLMProviderError


class FakeLLMClient:
    def __init__(self, content: str = "pong") -> None:
        self.content = content
        self.calls: list[dict[str, object]] = []

    def complete(
        self,
        *,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        max_output_tokens: int,
    ) -> LLMCompletion:
        self.calls.append(
            {
                "messages": messages,
                "model": model,
                "temperature": temperature,
                "max_output_tokens": max_output_tokens,
            }
        )
        return LLMCompletion(
            content=self.content,
            model=model,
            prompt_tokens=4,
            completion_tokens=2,
            total_tokens=6,
        )


class FailingLLMClient:
    def complete(self, **_: object) -> LLMCompletion:
        raise LLMProviderError("provider rejected request with Authorization: Bearer sk-secret")


def create_test_client(fake_llm: object | None = None) -> TestClient:
    app = create_app(
        Settings(
            check_dependencies=False,
            database_url="sqlite+pysqlite:///:memory:",
            llm_api_key="sk-test",
        )
    )
    Base.metadata.create_all(app.state.engine)
    if fake_llm is not None:
        app.state.llm_client = fake_llm
    return TestClient(app)


def create_test_client_with_settings(settings: Settings) -> TestClient:
    app = create_app(settings)
    Base.metadata.create_all(app.state.engine)
    return TestClient(app)


def valid_agent_payload() -> dict[str, object]:
    return {
        "name": "Researcher Agent",
        "description": "Find facts and summarize uncertainty.",
        "role_prompt": "You are a careful researcher.",
        "system_prompt": "Return concise findings.",
        "model_provider": "openai_compatible",
        "model_name": "gpt-4.1-mini",
        "temperature": 0.2,
        "max_output_tokens": 500,
    }


def test_me_returns_development_user_and_default_workspace():
    client = create_test_client()

    response = client.get("/me")

    assert response.status_code == 200
    body = response.json()
    UUID(body["user"]["id"])
    UUID(body["workspace"]["id"])
    assert body["user"]["display_name"] == "Development Admin"
    assert body["workspace"]["slug"] == "default"
    assert body["membership"]["role"] == "admin"


def test_configured_api_key_is_required_for_console_routes():
    client = create_test_client_with_settings(
        Settings(
            check_dependencies=False,
            database_url="sqlite+pysqlite:///:memory:",
            llm_api_key="sk-test",
            api_auth_key="console-secret",
        )
    )

    missing = client.get("/me")
    wrong = client.get("/me", headers={"X-AgentFlow-API-Key": "wrong"})
    authorized = client.get("/me", headers={"X-AgentFlow-API-Key": "console-secret"})

    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert authorized.status_code == 200


def test_non_development_environment_requires_configured_api_key():
    client = create_test_client_with_settings(
        Settings(
            environment="production",
            check_dependencies=False,
            database_url="sqlite+pysqlite:///:memory:",
            llm_api_key="sk-test",
        )
    )

    response = client.get("/me")

    assert response.status_code == 500
    assert "AGENTFLOW_API_AUTH_KEY" in response.json()["detail"]


def test_request_context_can_target_workspace_and_user_with_headers():
    client = create_test_client_with_settings(
        Settings(
            check_dependencies=False,
            database_url="sqlite+pysqlite:///:memory:",
            llm_api_key="sk-test",
            api_auth_key="console-secret",
        )
    )

    response = client.get(
        "/me",
        headers={
            "X-AgentFlow-API-Key": "console-secret",
            "X-AgentFlow-Workspace-Slug": "customer-a",
            "X-AgentFlow-Workspace-Name": "Customer A",
            "X-AgentFlow-User-Email": "operator@example.com",
            "X-AgentFlow-User-Name": "Operator",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["workspace"]["slug"] == "customer-a"
    assert body["workspace"]["name"] == "Customer A"
    assert body["user"]["email"] == "operator@example.com"
    assert body["user"]["display_name"] == "Operator"
    assert body["membership"]["role"] == "admin"


def test_api_allows_web_console_cors_preflight():
    client = create_test_client()

    response = client.options(
        "/me",
        headers={
            "Origin": "http://localhost:5180",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5180"


def test_agent_lifecycle_creates_versions_clones_disables_and_logs_llm_call():
    fake_llm = FakeLLMClient(content="pong")
    client = create_test_client(fake_llm)

    create_response = client.post("/agents", json=valid_agent_payload())

    assert create_response.status_code == 201
    created = create_response.json()
    agent_id = created["id"]
    UUID(agent_id)
    assert created["workspace_id"]
    assert created["status"] == "active"
    assert created["current_version"]["version_number"] == 1
    assert created["current_version"]["model_provider"] == "openai_compatible"

    list_response = client.get("/agents")
    assert list_response.status_code == 200
    assert [agent["name"] for agent in list_response.json()["items"]] == ["Researcher Agent"]

    update_response = client.patch(
        f"/agents/{agent_id}",
        json={"name": "Senior Researcher Agent", "description": "Updated description."},
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Senior Researcher Agent"

    version_response = client.post(
        f"/agents/{agent_id}/versions",
        json={
            "role_prompt": "You are a senior researcher.",
            "system_prompt": "Return bullets and confidence levels.",
            "model_provider": "openai_compatible",
            "model_name": "gpt-4.1-mini",
            "temperature": 0.1,
            "max_output_tokens": 700,
        },
    )
    assert version_response.status_code == 201
    assert version_response.json()["version_number"] == 2

    test_response = client.post(f"/agents/{agent_id}/test-runs", json={"input": "ping"})
    assert test_response.status_code == 200
    test_body = test_response.json()
    assert test_body["output"] == "pong"
    assert test_body["llm_call"]["status"] == "succeeded"
    assert test_body["llm_call"]["prompt_tokens"] == 4
    assert fake_llm.calls[0]["model"] == "gpt-4.1-mini"
    assert fake_llm.calls[0]["messages"][0]["role"] == "system"
    assert "senior researcher" in fake_llm.calls[0]["messages"][0]["content"]

    detail_response = client.get(f"/agents/{agent_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert [version["version_number"] for version in detail["versions"]] == [2, 1]
    assert detail["recent_llm_calls"][0]["status"] == "succeeded"

    clone_response = client.post(f"/agents/{agent_id}/clone")
    assert clone_response.status_code == 201
    clone = clone_response.json()
    assert clone["id"] != agent_id
    assert clone["name"] == "Senior Researcher Agent Copy"
    assert clone["current_version"]["version_number"] == 1

    disable_response = client.post(f"/agents/{agent_id}/disable")
    assert disable_response.status_code == 200
    assert disable_response.json()["status"] == "disabled"


def test_agent_validation_rejects_invalid_model_parameters():
    client = create_test_client()

    response = client.post(
        "/agents",
        json={**valid_agent_payload(), "temperature": 3, "max_output_tokens": 0},
    )

    assert response.status_code == 422


def test_agent_test_run_returns_sanitized_provider_errors():
    client = create_test_client(FailingLLMClient())
    agent_response = client.post("/agents", json=valid_agent_payload())
    agent_id = agent_response.json()["id"]

    response = client.post(f"/agents/{agent_id}/test-runs", json={"input": "ping"})

    assert response.status_code == 502
    body = response.json()
    assert "provider rejected request" in body["detail"]
    assert "sk-secret" not in body["detail"]
    assert "Authorization" not in body["detail"]
