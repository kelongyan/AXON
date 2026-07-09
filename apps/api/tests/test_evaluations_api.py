from uuid import UUID

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.models import Base
from app.main import create_app
from app.services.llm import LLMCompletion, LLMProviderError


class SequencedLLMClient:
    def __init__(self, outputs: list[str]) -> None:
        self.outputs = outputs
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
        content = self.outputs[len(self.calls) - 1]
        if content == "__FAIL__":
            raise LLMProviderError("provider rejected case")
        return LLMCompletion(
            content=content,
            model=model,
            prompt_tokens=8,
            completion_tokens=4,
            total_tokens=12,
        )


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


def test_evaluation_can_be_created_with_cases_for_published_workflow():
    client = create_test_client()
    workflow_id = create_published_workflow(client)

    response = client.post(
        "/evaluations",
        json={
            "name": "Phase 6 Smoke Eval",
            "description": "Two deterministic cases.",
            "workflow_id": workflow_id,
            "settings": {"token_price_per_1k": 0.001},
            "cases": [
                {"name": "Case A", "input": {"topic": "AgentFlow"}, "expected": {"contains": "AgentFlow"}},
                {"name": "Case B", "input": {"topic": "Approval"}, "expected": {"contains": "Approval"}},
            ],
        },
    )

    assert response.status_code == 201
    body = response.json()
    UUID(body["id"])
    assert body["workflow_id"] == workflow_id
    assert body["status"] == "draft"
    assert len(body["cases"]) == 2
    assert body["summary"]["case_count"] == 2
    assert body["summary"]["success_count"] == 0


def test_running_evaluation_creates_case_results_and_summary():
    fake_llm = SequencedLLMClient(outputs=["AgentFlow answer", "Approval answer"])
    client = create_test_client(fake_llm)
    workflow_id = create_published_workflow(client)
    evaluation = create_evaluation(client, workflow_id)

    response = client.post(f"/evaluations/{evaluation['id']}/run")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["summary"]["case_count"] == 2
    assert body["summary"]["success_count"] == 2
    assert body["summary"]["failure_count"] == 0
    assert body["summary"]["total_tokens"] == 24
    assert body["summary"]["estimated_cost"] == 0.000024
    assert [result["status"] for result in body["results"]] == ["succeeded", "succeeded"]
    assert all(result["run_id"] for result in body["results"])
    assert fake_llm.calls[0]["model"] == "step-3.7-flash"


def test_running_evaluation_keeps_going_when_one_case_fails():
    fake_llm = SequencedLLMClient(outputs=["AgentFlow answer", "__FAIL__"])
    client = create_test_client(fake_llm)
    workflow_id = create_published_workflow(client)
    evaluation = create_evaluation(client, workflow_id)

    response = client.post(f"/evaluations/{evaluation['id']}/run")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["summary"]["success_count"] == 1
    assert body["summary"]["failure_count"] == 1
    assert [result["status"] for result in body["results"]] == ["succeeded", "failed"]
    assert body["results"][1]["error_message"]


def test_rerunning_evaluation_replaces_previous_results_for_current_summary():
    fake_llm = SequencedLLMClient(outputs=["AgentFlow answer", "Approval answer", "Second AgentFlow", "Second Approval"])
    client = create_test_client(fake_llm)
    workflow_id = create_published_workflow(client)
    evaluation = create_evaluation(client, workflow_id)

    first_response = client.post(f"/evaluations/{evaluation['id']}/run")
    second_response = client.post(f"/evaluations/{evaluation['id']}/run")

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    body = second_response.json()
    assert body["summary"]["case_count"] == 2
    assert body["summary"]["success_count"] == 2
    assert body["summary"]["failure_count"] == 0
    assert body["summary"]["total_tokens"] == 24
    assert len(body["results"]) == 2


def create_evaluation(client: TestClient, workflow_id: str) -> dict[str, object]:
    response = client.post(
        "/evaluations",
        json={
            "name": "Batch Eval",
            "workflow_id": workflow_id,
            "settings": {"token_price_per_1k": 0.001},
            "cases": [
                {"name": "Case A", "input": {"topic": "AgentFlow"}, "expected": {}},
                {"name": "Case B", "input": {"topic": "Approval"}, "expected": {}},
            ],
        },
    )
    assert response.status_code == 201
    return response.json()


def create_published_workflow(client: TestClient) -> str:
    agent = client.post(
        "/agents",
        json={
            "name": "Eval Agent",
            "description": "Answers evaluation cases.",
            "role_prompt": "You are an evaluation test agent.",
            "system_prompt": "Return concise answers.",
            "model_provider": "openai_compatible",
            "model_name": "step-3.7-flash",
            "temperature": 0.2,
            "max_output_tokens": 512,
        },
    ).json()
    workflow = client.post("/workflows", json={"name": "Evaluation Workflow"}).json()
    publish = client.post(
        f"/workflows/{workflow['id']}/versions",
        json={"graph": simple_graph(agent["current_version_id"])},
    )
    assert publish.status_code == 201
    return workflow["id"]


def simple_graph(agent_version_id: str) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "nodes": [
            {
                "id": "node_start",
                "type": "start",
                "name": "Start",
                "config": {
                    "input_schema": {
                        "type": "object",
                        "required": ["topic"],
                        "properties": {"topic": {"type": "string"}},
                    }
                },
            },
            {
                "id": "node_agent",
                "type": "agent",
                "name": "Agent",
                "config": {"agent_version_id": agent_version_id, "instruction": "Answer the topic."},
                "input_mapping": {"topic": "$.run.input.topic"},
            },
            {
                "id": "node_end",
                "type": "end",
                "name": "End",
                "config": {"output_mapping": {"answer": "$.steps.node_agent.output.content"}},
            },
        ],
        "edges": [
            {"id": "edge_start_agent", "source": "node_start", "target": "node_agent", "type": "default"},
            {"id": "edge_agent_end", "source": "node_agent", "target": "node_end", "type": "default"},
        ],
    }
