from uuid import UUID

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.models import Base
from app.main import create_app


def create_test_client() -> TestClient:
    app = create_app(
        Settings(
            check_dependencies=False,
            database_url="sqlite+pysqlite:///:memory:",
            llm_api_key="sk-test",
        )
    )
    Base.metadata.create_all(app.state.engine)
    return TestClient(app)


def create_agent(client: TestClient) -> str:
    payload = {
        "name": "Tool Test Agent",
        "description": "Agent used for Tool Registry tests.",
        "role_prompt": "You use tools carefully.",
        "system_prompt": "Follow tool safety policy.",
        "model_provider": "openai_compatible",
        "model_name": "step-3.7-flash",
        "temperature": 0.2,
        "max_output_tokens": 512,
    }
    response = client.post("/agents", json=payload)
    assert response.status_code == 201
    return response.json()["id"]


def tool_by_name(client: TestClient, name: str) -> dict[str, object]:
    response = client.get("/tools")
    assert response.status_code == 200
    for tool in response.json()["items"]:
        if tool["name"] == name:
            return tool
    raise AssertionError(f"Tool not found: {name}")


def test_seed_built_ins_lists_risk_and_approval_policy():
    client = create_test_client()

    seed_response = client.post("/tools/seed-built-ins")

    assert seed_response.status_code == 201
    assert seed_response.json()["created"] == 8

    list_response = client.get("/tools")
    assert list_response.status_code == 200
    tools = {tool["name"]: tool for tool in list_response.json()["items"]}
    assert set(tools) == {
        "web_search",
        "http_request",
        "document_parse",
        "code_runner",
        "database_query",
        "file_artifact_create",
        "json_transform",
        "markdown_report_generate",
    }
    assert tools["json_transform"]["risk_level"] == "low_write"
    assert tools["json_transform"]["requires_approval"] is False
    assert tools["code_runner"]["risk_level"] == "high_cost"
    assert tools["code_runner"]["requires_approval"] is True


def test_agent_must_be_granted_tool_before_invocation_and_calls_are_logged():
    client = create_test_client()
    agent_id = create_agent(client)
    client.post("/tools/seed-built-ins")
    json_tool = tool_by_name(client, "json_transform")

    blocked_response = client.post(
        f"/tools/{json_tool['id']}/invoke",
        json={
            "agent_id": agent_id,
            "input": {"data": {"title": "Report"}, "select_keys": ["title"]},
        },
    )

    assert blocked_response.status_code == 403
    assert blocked_response.json()["detail"] == "Agent is not authorized to use this tool"

    grant_response = client.post(f"/agents/{agent_id}/tools/{json_tool['id']}/grant")
    assert grant_response.status_code == 201
    assert grant_response.json()["agent_id"] == agent_id
    assert grant_response.json()["tool_id"] == json_tool["id"]

    invoke_response = client.post(
        f"/tools/{json_tool['id']}/invoke",
        json={
            "agent_id": agent_id,
            "input": {
                "data": {"title": "Report", "secret": "hidden"},
                "select_keys": ["title"],
            },
        },
    )

    assert invoke_response.status_code == 200
    body = invoke_response.json()
    assert body["status"] == "succeeded"
    assert body["output"] == {"result": {"title": "Report"}}
    UUID(body["tool_call"]["id"])
    assert body["tool_call"]["status"] == "succeeded"
    assert body["tool_call"]["input_summary"]["data"]["secret"] == "[REDACTED]"

    calls_response = client.get("/tools/calls")
    assert calls_response.status_code == 200
    calls = calls_response.json()["items"]
    assert [call["status"] for call in calls] == ["succeeded", "blocked"]
    assert calls[1]["error_message"] == "Agent is not authorized to use this tool"


def test_high_risk_tool_invocation_is_blocked_even_when_granted():
    client = create_test_client()
    agent_id = create_agent(client)
    client.post("/tools/seed-built-ins")
    code_runner = tool_by_name(client, "code_runner")
    client.post(f"/agents/{agent_id}/tools/{code_runner['id']}/grant")

    response = client.post(
        f"/tools/{code_runner['id']}/invoke",
        json={"agent_id": agent_id, "input": {"language": "python", "code": "print('hi')"}},
    )

    assert response.status_code == 409
    body = response.json()
    assert body["detail"] == "Tool requires approval before execution"
    assert body["tool_call"]["status"] == "blocked"
    assert body["tool_call"]["risk_level"] == "high_cost"


def test_schema_validation_failure_is_logged():
    client = create_test_client()
    agent_id = create_agent(client)
    client.post("/tools/seed-built-ins")
    markdown_tool = tool_by_name(client, "markdown_report_generate")
    client.post(f"/agents/{agent_id}/tools/{markdown_tool['id']}/grant")

    response = client.post(
        f"/tools/{markdown_tool['id']}/invoke",
        json={"agent_id": agent_id, "input": {"title": "Bad payload"}},
    )

    assert response.status_code == 422
    assert "Missing required field: sections" in response.json()["detail"]

    calls_response = client.get("/tools/calls")
    assert calls_response.json()["items"][0]["status"] == "failed"
    assert "Missing required field: sections" in calls_response.json()["items"][0]["error_message"]
