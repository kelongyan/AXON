from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Settings
from app.db.models import Base, RunStep
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
            raise LLMProviderError("provider rejected approval resume")
        return LLMCompletion(
            content=content,
            model=model,
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
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


def create_agent(client: TestClient, name: str, prompt: str = "Return concise output.") -> dict[str, object]:
    response = client.post(
        "/agents",
        json={
            "name": name,
            "description": f"{name} for workflow tests.",
            "role_prompt": f"You are {name}.",
            "system_prompt": prompt,
            "model_provider": "openai_compatible",
            "model_name": "step-3.7-flash",
            "temperature": 0.2,
            "max_output_tokens": 512,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_workflow_can_be_published_with_agent_version_snapshots():
    client = create_test_client()
    researcher = create_agent(client, "Researcher Agent")
    agent_version_id = researcher["current_version_id"]

    workflow_response = client.post(
        "/workflows",
        json={"name": "Report Workflow", "description": "Sequential report generation."},
    )

    assert workflow_response.status_code == 201
    workflow = workflow_response.json()
    workflow_id = workflow["id"]
    UUID(workflow_id)
    assert workflow["status"] == "draft"
    assert workflow["current_version_id"] is None

    publish_response = client.post(
        f"/workflows/{workflow_id}/versions",
        json={"graph": simple_graph(agent_version_id)},
    )

    assert publish_response.status_code == 201
    version = publish_response.json()
    UUID(version["id"])
    assert version["workflow_id"] == workflow_id
    assert version["version_number"] == 1
    assert version["status"] == "published"
    assert version["referenced_agent_versions"] == [agent_version_id]

    detail_response = client.get(f"/workflows/{workflow_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["current_version_id"] == version["id"]
    assert detail["versions"][0]["id"] == version["id"]


def test_run_executes_start_agent_end_and_records_steps_trace_and_llm_call():
    fake_llm = SequencedLLMClient(outputs=["Research notes for AgentFlow"])
    client = create_test_client(fake_llm)
    researcher = create_agent(client, "Researcher Agent", "Return research notes.")
    workflow = client.post("/workflows", json={"name": "Single Agent Flow"}).json()
    version = client.post(
        f"/workflows/{workflow['id']}/versions",
        json={"graph": simple_graph(researcher["current_version_id"])},
    ).json()

    run_response = client.post(
        f"/workflows/{workflow['id']}/runs",
        json={"input": {"topic": "AgentFlow", "audience": "CTO"}},
    )

    assert run_response.status_code == 201
    queued = run_response.json()
    run_id = queued["id"]
    assert queued["status"] == "queued"
    assert queued["workflow_version_id"] == version["id"]

    execute_response = client.post(f"/runs/{run_id}/execute")

    assert execute_response.status_code == 200
    executed = execute_response.json()
    assert executed["status"] == "succeeded"
    assert executed["output"] == {"result": "Research notes for AgentFlow"}
    assert [step["node_id"] for step in executed["steps"]] == ["node_start", "node_agent", "node_end"]
    assert [step["status"] for step in executed["steps"]] == ["succeeded", "succeeded", "succeeded"]
    assert executed["steps"][1]["output"] == {"content": "Research notes for AgentFlow"}
    assert executed["llm_calls"][0]["status"] == "succeeded"
    assert executed["llm_calls"][0]["total_tokens"] == 15
    assert executed["trace_events"][0]["event_type"] == "run.created"
    assert "run.succeeded" in [event["event_type"] for event in executed["trace_events"]]
    assert fake_llm.calls[0]["model"] == "step-3.7-flash"
    assert "AgentFlow" in fake_llm.calls[0]["messages"][1]["content"]

    detail_response = client.get(f"/runs/{run_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["status"] == "succeeded"
    assert detail["steps"][1]["node_name"] == "Research"
    assert detail["trace_events"][-1]["event_type"] == "run.succeeded"


def test_run_detail_orders_steps_by_execution_start_time_when_created_at_is_not_distinct():
    fake_llm = SequencedLLMClient(outputs=["ordered output"])
    client = create_test_client(fake_llm)
    researcher = create_agent(client, "Ordered Researcher Agent", "Return research notes.")
    workflow = client.post("/workflows", json={"name": "Ordered Step Flow"}).json()
    client.post(
        f"/workflows/{workflow['id']}/versions",
        json={"graph": simple_graph(researcher["current_version_id"])},
    )
    run = client.post(
        f"/workflows/{workflow['id']}/runs",
        json={"input": {"topic": "AgentFlow", "audience": "CTO"}},
    ).json()
    executed = client.post(f"/runs/{run['id']}/execute").json()
    expected_order = [step["node_id"] for step in executed["steps"]]
    assert expected_order == ["node_start", "node_agent", "node_end"]

    base_time = datetime(2026, 7, 9, 12, 0, tzinfo=UTC)
    with client.app.state.session_factory() as session:
        steps = list(session.scalars(select(RunStep).where(RunStep.run_id == UUID(run["id"]))))
        by_node_id = {step.node_id: step for step in steps}
        by_node_id["node_start"].started_at = base_time
        by_node_id["node_agent"].started_at = base_time + timedelta(seconds=1)
        by_node_id["node_end"].started_at = base_time + timedelta(seconds=2)
        by_node_id["node_start"].created_at = base_time + timedelta(seconds=2)
        by_node_id["node_agent"].created_at = base_time + timedelta(seconds=1)
        by_node_id["node_end"].created_at = base_time
        session.commit()

    detail = client.get(f"/runs/{run['id']}").json()

    assert [step["node_id"] for step in detail["steps"]] == expected_order


def test_run_created_trace_redacts_sensitive_input_fields():
    client = create_test_client()
    researcher = create_agent(client, "Researcher Agent", "Return research notes.")
    workflow = client.post("/workflows", json={"name": "Redaction Flow"}).json()
    client.post(
        f"/workflows/{workflow['id']}/versions",
        json={"graph": simple_graph(researcher["current_version_id"])},
    )

    response = client.post(
        f"/workflows/{workflow['id']}/runs",
        json={"input": {"topic": "AgentFlow", "api_key": "secret-value", "headers": {"Authorization": "Bearer abc"}}},
    )

    assert response.status_code == 201
    created_event = response.json()["trace_events"][0]
    assert created_event["event_type"] == "run.created"
    assert created_event["payload"]["input_summary"]["api_key"] == "[REDACTED]"
    assert created_event["payload"]["input_summary"]["headers"]["Authorization"] == "[REDACTED]"
    assert "secret-value" not in str(created_event["payload"])


def test_run_executes_multiple_agents_in_sequence_with_prior_step_outputs():
    fake_llm = SequencedLLMClient(outputs=["research notes", "draft markdown", "accepted final"])
    client = create_test_client(fake_llm)
    researcher = create_agent(client, "Researcher Agent", "Return notes.")
    writer = create_agent(client, "Writer Agent", "Return draft.")
    reviewer = create_agent(client, "Reviewer Agent", "Return final.")
    workflow = client.post("/workflows", json={"name": "Three Agent Flow"}).json()
    client.post(
        f"/workflows/{workflow['id']}/versions",
        json={
            "graph": three_agent_graph(
                researcher["current_version_id"],
                writer["current_version_id"],
                reviewer["current_version_id"],
            )
        },
    )
    run = client.post(
        f"/workflows/{workflow['id']}/runs",
        json={"input": {"topic": "AgentFlow", "audience": "CTO"}},
    ).json()

    response = client.post(f"/runs/{run['id']}/execute")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["output"] == {"markdown": "accepted final"}
    assert [step["node_id"] for step in body["steps"]] == [
        "node_start",
        "node_researcher",
        "node_writer",
        "node_reviewer",
        "node_end",
    ]
    assert len(body["llm_calls"]) == 3
    assert "research notes" in fake_llm.calls[1]["messages"][1]["content"]
    assert "draft markdown" in fake_llm.calls[2]["messages"][1]["content"]


def test_publish_rejects_graph_without_single_start_node():
    client = create_test_client()
    workflow = client.post("/workflows", json={"name": "Broken Flow"}).json()

    response = client.post(
        f"/workflows/{workflow['id']}/versions",
        json={
            "graph": {
                "schema_version": "1.0",
                "nodes": [{"id": "node_end", "type": "end", "name": "End", "config": {}}],
                "edges": [],
            }
        },
    )

    assert response.status_code == 422
    assert "exactly one start node" in response.json()["detail"]


def test_publish_accepts_visual_builder_graph_with_positions_and_retrieval_node():
    fake_embedding = KeywordEmbeddingClient()
    client = create_test_client()
    client.app.state.embedding_client = fake_embedding
    kb_id = create_knowledge_base(client)
    researcher = create_agent(client, "Visual Researcher Agent")
    workflow = client.post("/workflows", json={"name": "Visual RAG Flow"}).json()

    response = client.post(
        f"/workflows/{workflow['id']}/versions",
        json={"graph": visual_retrieval_graph(researcher["current_version_id"], kb_id)},
    )

    assert response.status_code == 201
    version = response.json()
    assert version["graph"]["nodes"][1]["position"] == {"x": 300, "y": 120}
    assert version["node_snapshots"]["node_retrieval"]["knowledge_base_ids"] == [kb_id]


def test_publish_rejects_visual_graph_with_unreachable_node():
    client = create_test_client()
    researcher = create_agent(client, "Unreachable Agent")
    workflow = client.post("/workflows", json={"name": "Broken Visual Flow"}).json()
    graph = simple_graph(researcher["current_version_id"])
    graph["nodes"].append(
        {
            "id": "node_orphan",
            "type": "agent",
            "name": "Orphan",
            "position": {"x": 700, "y": 320},
            "config": {"agent_version_id": researcher["current_version_id"]},
        }
    )

    response = client.post(f"/workflows/{workflow['id']}/versions", json={"graph": graph})

    assert response.status_code == 422
    assert "reachable" in response.json()["detail"]


def test_publish_rejects_planned_visual_nodes_that_are_not_executable_yet():
    client = create_test_client()
    workflow = client.post("/workflows", json={"name": "Tool Node Flow"}).json()
    graph = {
        "schema_version": "1.0",
        "nodes": [
            {"id": "node_start", "type": "start", "name": "Start", "position": {"x": 0, "y": 0}, "config": {}},
            {
                "id": "node_tool",
                "type": "tool",
                "name": "Generate Artifact",
                "position": {"x": 280, "y": 0},
                "config": {"tool_id": "00000000-0000-0000-0000-000000000001"},
            },
            {"id": "node_end", "type": "end", "name": "End", "position": {"x": 560, "y": 0}, "config": {}},
        ],
        "edges": [
            {"id": "edge_start_tool", "source": "node_start", "target": "node_tool", "type": "default"},
            {"id": "edge_tool_end", "source": "node_tool", "target": "node_end", "type": "default"},
        ],
    }

    response = client.post(f"/workflows/{workflow['id']}/versions", json={"graph": graph})

    assert response.status_code == 422
    assert "not executable in Phase 6 MVP" in response.json()["detail"]


def test_publish_accepts_phase6_approval_node():
    client = create_test_client()
    researcher = create_agent(client, "Approval Researcher")
    workflow = client.post("/workflows", json={"name": "Approval Flow"}).json()

    response = client.post(
        f"/workflows/{workflow['id']}/versions",
        json={"graph": approval_graph(researcher["current_version_id"])},
    )

    assert response.status_code == 201
    version = response.json()
    assert version["graph"]["nodes"][1]["type"] == "approval"
    assert version["node_snapshots"]["node_approval"]["risk_level"] == "medium"


def test_run_pauses_at_approval_node_and_creates_pending_approval():
    fake_llm = SequencedLLMClient(outputs=["approved answer"])
    client = create_test_client(fake_llm)
    researcher = create_agent(client, "Approval Pause Agent")
    workflow = client.post("/workflows", json={"name": "Pause Approval Flow"}).json()
    client.post(
        f"/workflows/{workflow['id']}/versions",
        json={"graph": approval_graph(researcher["current_version_id"])},
    )
    run = client.post(
        f"/workflows/{workflow['id']}/runs",
        json={"input": {"topic": "AgentFlow approval", "audience": "CTO"}},
    ).json()

    response = client.post(f"/runs/{run['id']}/execute")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "waiting_approval"
    assert body["steps"][-1]["node_id"] == "node_approval"
    assert body["steps"][-1]["status"] == "waiting_approval"
    assert body["approvals"][0]["status"] == "pending"
    assert body["approvals"][0]["run_id"] == run["id"]
    assert body["approvals"][0]["node_id"] == "node_approval"
    assert body["steps"][-1]["output"]["approval_id"] == body["approvals"][0]["id"]
    requested_event = next(event for event in body["trace_events"] if event["event_type"] == "approval.requested")
    assert requested_event["payload"]["approval_id"] == body["approvals"][0]["id"]
    assert "approval.requested" in [event["event_type"] for event in body["trace_events"]]
    assert fake_llm.calls == []


def test_approving_pending_approval_resumes_run_to_success():
    fake_llm = SequencedLLMClient(outputs=["approved answer"])
    client = create_test_client(fake_llm)
    researcher = create_agent(client, "Approval Resume Agent")
    workflow = client.post("/workflows", json={"name": "Resume Approval Flow"}).json()
    client.post(
        f"/workflows/{workflow['id']}/versions",
        json={"graph": approval_graph(researcher["current_version_id"])},
    )
    run = client.post(
        f"/workflows/{workflow['id']}/runs",
        json={"input": {"topic": "AgentFlow approval", "audience": "CTO"}},
    ).json()
    paused = client.post(f"/runs/{run['id']}/execute").json()
    approval_id = paused["approvals"][0]["id"]

    response = client.post(
        f"/approvals/{approval_id}/approve",
        json={"comment": "Looks safe to continue."},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["output"] == {"result": "approved answer"}
    assert [step["node_id"] for step in body["steps"]] == ["node_start", "node_approval", "node_agent", "node_end"]
    assert body["approvals"][0]["status"] == "approved"
    assert body["approvals"][0]["decision_comment"] == "Looks safe to continue."
    assert "approval.approved" in [event["event_type"] for event in body["trace_events"]]
    assert "run.resumed" in [event["event_type"] for event in body["trace_events"]]
    assert fake_llm.calls[0]["model"] == "step-3.7-flash"


def test_approval_resume_failure_marks_run_failed_and_keeps_decision():
    fake_llm = SequencedLLMClient(outputs=["__FAIL__"])
    client = create_test_client(fake_llm)
    researcher = create_agent(client, "Approval Failure Agent")
    workflow = client.post("/workflows", json={"name": "Approval Failure Flow"}).json()
    client.post(
        f"/workflows/{workflow['id']}/versions",
        json={"graph": approval_graph(researcher["current_version_id"])},
    )
    run = client.post(
        f"/workflows/{workflow['id']}/runs",
        json={"input": {"topic": "AgentFlow approval", "audience": "CTO"}},
    ).json()
    paused = client.post(f"/runs/{run['id']}/execute").json()
    approval_id = paused["approvals"][0]["id"]

    response = client.post(
        f"/approvals/{approval_id}/approve",
        json={"comment": "Approved, but downstream provider fails."},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["error_type"] == "RunExecutionError"
    assert body["approvals"][0]["status"] == "approved"
    assert body["approvals"][0]["decision_comment"] == "Approved, but downstream provider fails."
    assert "approval.approved" in [event["event_type"] for event in body["trace_events"]]
    assert "run.failed" in [event["event_type"] for event in body["trace_events"]]


def test_rejecting_pending_approval_fails_run_without_calling_llm():
    fake_llm = SequencedLLMClient(outputs=["should not be used"])
    client = create_test_client(fake_llm)
    researcher = create_agent(client, "Approval Reject Agent")
    workflow = client.post("/workflows", json={"name": "Reject Approval Flow"}).json()
    client.post(
        f"/workflows/{workflow['id']}/versions",
        json={"graph": approval_graph(researcher["current_version_id"])},
    )
    run = client.post(
        f"/workflows/{workflow['id']}/runs",
        json={"input": {"topic": "AgentFlow approval", "audience": "CTO"}},
    ).json()
    paused = client.post(f"/runs/{run['id']}/execute").json()
    approval_id = paused["approvals"][0]["id"]

    response = client.post(
        f"/approvals/{approval_id}/reject",
        json={"comment": "Risk is too high."},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["error_type"] == "ApprovalRejected"
    assert body["approvals"][0]["status"] == "rejected"
    assert "approval.rejected" in [event["event_type"] for event in body["trace_events"]]
    assert fake_llm.calls == []


class KeywordEmbeddingClient:
    def embed_texts(self, *, texts: list[str], model: str) -> list[list[float]]:
        return [[float(text.lower().count("agentflow")), float(text.lower().count("rag"))] for text in texts]


def create_knowledge_base(client: TestClient) -> str:
    response = client.post(
        "/knowledge-bases",
        json={"name": "Visual Builder KB", "embedding_model": "test-embedding"},
    )
    assert response.status_code == 201
    return response.json()["id"]


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
                "name": "Research",
                "config": {
                    "agent_version_id": agent_version_id,
                    "instruction": "Research the topic and return notes.",
                },
                "input_mapping": {"topic": "$.run.input.topic", "audience": "$.run.input.audience"},
            },
            {
                "id": "node_end",
                "type": "end",
                "name": "End",
                "config": {"output_mapping": {"result": "$.steps.node_agent.output.content"}},
            },
        ],
        "edges": [
            {"id": "edge_start_agent", "source": "node_start", "target": "node_agent", "type": "default"},
            {"id": "edge_agent_end", "source": "node_agent", "target": "node_end", "type": "default"},
        ],
    }


def visual_retrieval_graph(agent_version_id: str, knowledge_base_id: str) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "nodes": [
            {
                "id": "node_start",
                "type": "start",
                "name": "Start",
                "position": {"x": 40, "y": 120},
                "config": {
                    "input_schema": {
                        "type": "object",
                        "required": ["topic"],
                        "properties": {"topic": {"type": "string"}},
                    }
                },
            },
            {
                "id": "node_retrieval",
                "type": "retrieval",
                "name": "Retrieve",
                "position": {"x": 300, "y": 120},
                "config": {"knowledge_base_ids": [knowledge_base_id], "top_k": 3},
                "input_mapping": {"query": "$.run.input.topic"},
            },
            {
                "id": "node_agent",
                "type": "agent",
                "name": "Answer",
                "position": {"x": 560, "y": 120},
                "config": {
                    "agent_version_id": agent_version_id,
                    "instruction": "Answer with retrieved context.",
                },
                "input_mapping": {
                    "topic": "$.run.input.topic",
                    "retrieval_context": "$.steps.node_retrieval.output.context",
                },
            },
            {
                "id": "node_end",
                "type": "end",
                "name": "End",
                "position": {"x": 820, "y": 120},
                "config": {"output_mapping": {"answer": "$.steps.node_agent.output.content"}},
            },
        ],
        "edges": [
            {"id": "edge_start_retrieval", "source": "node_start", "target": "node_retrieval", "type": "default"},
            {"id": "edge_retrieval_agent", "source": "node_retrieval", "target": "node_agent", "type": "default"},
            {"id": "edge_agent_end", "source": "node_agent", "target": "node_end", "type": "default"},
        ],
    }


def approval_graph(agent_version_id: str) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "nodes": [
            {
                "id": "node_start",
                "type": "start",
                "name": "Start",
                "position": {"x": 40, "y": 120},
                "config": {
                    "input_schema": {
                        "type": "object",
                        "required": ["topic"],
                        "properties": {"topic": {"type": "string"}, "audience": {"type": "string"}},
                    }
                },
            },
            {
                "id": "node_approval",
                "type": "approval",
                "name": "Human Review",
                "position": {"x": 320, "y": 120},
                "config": {
                    "title": "Review before model call",
                    "instructions": "Approve only if the request is safe to send to the model.",
                    "risk_level": "medium",
                },
                "input_mapping": {"topic": "$.run.input.topic", "audience": "$.run.input.audience"},
            },
            {
                "id": "node_agent",
                "type": "agent",
                "name": "Research",
                "position": {"x": 600, "y": 120},
                "config": {
                    "agent_version_id": agent_version_id,
                    "instruction": "Research the topic and return notes.",
                },
                "input_mapping": {"topic": "$.run.input.topic", "audience": "$.run.input.audience"},
            },
            {
                "id": "node_end",
                "type": "end",
                "name": "End",
                "position": {"x": 880, "y": 120},
                "config": {"output_mapping": {"result": "$.steps.node_agent.output.content"}},
            },
        ],
        "edges": [
            {"id": "edge_start_approval", "source": "node_start", "target": "node_approval", "type": "default"},
            {"id": "edge_approval_agent", "source": "node_approval", "target": "node_agent", "type": "default"},
            {"id": "edge_agent_end", "source": "node_agent", "target": "node_end", "type": "default"},
        ],
    }


def three_agent_graph(researcher_version_id: str, writer_version_id: str, reviewer_version_id: str) -> dict[str, object]:
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
                        "properties": {"topic": {"type": "string"}, "audience": {"type": "string"}},
                    }
                },
            },
            {
                "id": "node_researcher",
                "type": "agent",
                "name": "Researcher",
                "config": {
                    "agent_version_id": researcher_version_id,
                    "instruction": "Research the topic.",
                },
                "input_mapping": {"topic": "$.run.input.topic", "audience": "$.run.input.audience"},
            },
            {
                "id": "node_writer",
                "type": "agent",
                "name": "Writer",
                "config": {
                    "agent_version_id": writer_version_id,
                    "instruction": "Write a Markdown draft.",
                },
                "input_mapping": {
                    "topic": "$.run.input.topic",
                    "notes": "$.steps.node_researcher.output.content",
                },
            },
            {
                "id": "node_reviewer",
                "type": "agent",
                "name": "Reviewer",
                "config": {
                    "agent_version_id": reviewer_version_id,
                    "instruction": "Review and finalize the draft.",
                },
                "input_mapping": {"draft": "$.steps.node_writer.output.content"},
            },
            {
                "id": "node_end",
                "type": "end",
                "name": "End",
                "config": {"output_mapping": {"markdown": "$.steps.node_reviewer.output.content"}},
            },
        ],
        "edges": [
            {"id": "edge_start_researcher", "source": "node_start", "target": "node_researcher", "type": "default"},
            {"id": "edge_researcher_writer", "source": "node_researcher", "target": "node_writer", "type": "default"},
            {"id": "edge_writer_reviewer", "source": "node_writer", "target": "node_reviewer", "type": "default"},
            {"id": "edge_reviewer_end", "source": "node_reviewer", "target": "node_end", "type": "default"},
        ],
    }
