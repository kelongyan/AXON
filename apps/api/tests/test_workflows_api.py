from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Settings
from app.db.models import Base, Run, RunStep, Tool, ToolCall
from app.main import create_app
from app.services import workflows
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


def test_worker_claim_marks_oldest_queued_run_and_prevents_duplicate_claims():
    client = create_test_client()
    researcher = create_agent(client, "Claim Worker Agent")
    workflow = client.post("/workflows", json={"name": "Claim Worker Flow"}).json()
    client.post(
        f"/workflows/{workflow['id']}/versions",
        json={"graph": simple_graph(researcher["current_version_id"])},
    )
    run = client.post(
        f"/workflows/{workflow['id']}/runs",
        json={"input": {"topic": "AgentFlow", "audience": "CTO"}},
    ).json()

    with client.app.state.session_factory() as session:
        claimed = workflows.claim_next_queued_run(
            session,
            workspace_id=None,
            worker_id="worker-a",
            lease_seconds=120,
        )
        duplicate = workflows.claim_next_queued_run(
            session,
            workspace_id=None,
            worker_id="worker-b",
            lease_seconds=120,
        )
        stored_run = session.get(Run, UUID(run["id"]))

    assert claimed is not None
    assert duplicate is None
    assert stored_run is not None
    assert stored_run.status == "running"
    assert stored_run.worker_id == "worker-a"
    assert stored_run.claim_token
    assert stored_run.lease_expires_at is not None
    assert stored_run.started_at is not None


def test_run_detail_exposes_worker_claim_observability():
    client = create_test_client()
    researcher = create_agent(client, "Claim Detail Agent")
    workflow = client.post("/workflows", json={"name": "Claim Detail Flow"}).json()
    client.post(
        f"/workflows/{workflow['id']}/versions",
        json={"graph": simple_graph(researcher["current_version_id"])},
    )
    run = client.post(
        f"/workflows/{workflow['id']}/runs",
        json={"input": {"topic": "AgentFlow", "audience": "CTO"}},
    ).json()

    with client.app.state.session_factory() as session:
        claimed = workflows.claim_next_queued_run(
            session,
            workspace_id=None,
            worker_id="worker-a",
            lease_seconds=120,
        )
        session.commit()

    detail = client.get(f"/runs/{run['id']}")

    assert claimed is not None
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["worker_id"] == "worker-a"
    assert payload["lease_expires_at"] is not None
    assert payload["current_node_id"] is None
    assert "claim_token" not in payload


def test_worker_claim_reclaims_expired_running_lease():
    client = create_test_client()
    researcher = create_agent(client, "Expired Claim Agent")
    workflow = client.post("/workflows", json={"name": "Expired Claim Flow"}).json()
    client.post(
        f"/workflows/{workflow['id']}/versions",
        json={"graph": simple_graph(researcher["current_version_id"])},
    )
    run = client.post(
        f"/workflows/{workflow['id']}/runs",
        json={"input": {"topic": "AgentFlow", "audience": "CTO"}},
    ).json()

    with client.app.state.session_factory() as session:
        first_claim = workflows.claim_next_queued_run(
            session,
            workspace_id=None,
            worker_id="worker-a",
            lease_seconds=120,
        )
        assert first_claim is not None
        first_claim_token = first_claim.claim_token
        duplicate = workflows.claim_next_queued_run(
            session,
            workspace_id=None,
            worker_id="worker-b",
            lease_seconds=120,
        )
        stored_run = session.get(Run, UUID(run["id"]))
        assert stored_run is not None
        stored_run.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        session.flush()
        reclaimed = workflows.claim_next_queued_run(
            session,
            workspace_id=None,
            worker_id="worker-b",
            lease_seconds=120,
        )

    assert duplicate is None
    assert reclaimed is not None
    assert reclaimed.id == UUID(run["id"])
    assert reclaimed.worker_id == "worker-b"
    assert reclaimed.claim_token != first_claim_token
    assert reclaimed.status == "running"


def test_worker_renew_run_lease_keeps_claim_from_expiring():
    client = create_test_client()
    researcher = create_agent(client, "Renew Claim Agent")
    workflow = client.post("/workflows", json={"name": "Renew Claim Flow"}).json()
    client.post(
        f"/workflows/{workflow['id']}/versions",
        json={"graph": simple_graph(researcher["current_version_id"])},
    )
    run = client.post(
        f"/workflows/{workflow['id']}/runs",
        json={"input": {"topic": "AgentFlow", "audience": "CTO"}},
    ).json()

    with client.app.state.session_factory() as session:
        claimed = workflows.claim_next_queued_run(
            session,
            workspace_id=None,
            worker_id="worker-a",
            lease_seconds=1,
        )
        assert claimed is not None
        assert claimed.claim_token is not None
        expired_at = datetime.now(UTC) - timedelta(seconds=1)
        claimed.lease_expires_at = expired_at
        session.flush()

        renewed = workflows.renew_run_lease(
            session,
            workspace_id=None,
            run_id=UUID(run["id"]),
            claim_token=claimed.claim_token,
            lease_seconds=120,
        )
        duplicate = workflows.claim_next_queued_run(
            session,
            workspace_id=None,
            worker_id="worker-b",
            lease_seconds=120,
        )
        stored_run = session.get(Run, UUID(run["id"]))

    assert renewed is True
    assert duplicate is None
    assert stored_run is not None
    assert stored_run.worker_id == "worker-a"
    assert stored_run.lease_expires_at is not None
    assert stored_run.lease_expires_at != expired_at


def test_claim_fence_rejects_lost_claim_token():
    client = create_test_client()
    researcher = create_agent(client, "Lost Claim Agent")
    workflow = client.post("/workflows", json={"name": "Lost Claim Flow"}).json()
    client.post(
        f"/workflows/{workflow['id']}/versions",
        json={"graph": simple_graph(researcher["current_version_id"])},
    )
    run = client.post(
        f"/workflows/{workflow['id']}/runs",
        json={"input": {"topic": "AgentFlow", "audience": "CTO"}},
    ).json()

    with client.app.state.session_factory() as session:
        claimed = workflows.claim_next_queued_run(
            session,
            workspace_id=None,
            worker_id="worker-a",
            lease_seconds=120,
        )
        assert claimed is not None
        assert claimed.claim_token is not None
        claim_token = claimed.claim_token
        claimed.claim_token = "stolen-token"
        session.flush()

        with pytest.raises(workflows.RunExecutionError, match="Run claim was lost"):
            workflows._assert_claim_still_owned(
                session,
                run_id=claimed.id,
                claim_token=claim_token,
            )


def test_cancel_queued_run_marks_terminal_and_prevents_worker_claim():
    client = create_test_client()
    researcher = create_agent(client, "Cancel Queued Agent")
    workflow = client.post("/workflows", json={"name": "Cancel Queued Flow"}).json()
    client.post(
        f"/workflows/{workflow['id']}/versions",
        json={"graph": simple_graph(researcher["current_version_id"])},
    )
    run = client.post(
        f"/workflows/{workflow['id']}/runs",
        json={"input": {"topic": "AgentFlow", "audience": "CTO"}},
    ).json()

    response = client.post(f"/runs/{run['id']}/cancel", json={"comment": "No longer needed."})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "cancelled"
    assert body["error_type"] == "RunCancelled"
    assert body["error_message"] == "No longer needed."
    assert body["cancelled_at"] is not None
    assert body["finished_at"] is not None
    assert "run.cancelled" in [event["event_type"] for event in body["trace_events"]]

    with client.app.state.session_factory() as session:
        executed = workflows.execute_next_queued_run(
            session,
            workspace_id=None,
            worker_id="worker-a",
            llm_client=object(),
        )

    assert executed is None


def test_cancel_waiting_approval_run_cancels_pending_approval_without_calling_llm():
    fake_llm = SequencedLLMClient(outputs=["should not be used"])
    client = create_test_client(fake_llm)
    researcher = create_agent(client, "Cancel Approval Agent")
    workflow = client.post("/workflows", json={"name": "Cancel Approval Flow"}).json()
    client.post(
        f"/workflows/{workflow['id']}/versions",
        json={"graph": approval_graph(researcher["current_version_id"])},
    )
    run = client.post(
        f"/workflows/{workflow['id']}/runs",
        json={"input": {"topic": "AgentFlow approval", "audience": "CTO"}},
    ).json()
    paused = client.post(f"/runs/{run['id']}/execute").json()
    assert paused["status"] == "waiting_approval"

    response = client.post(f"/runs/{run['id']}/cancel", json={"comment": "Stop before provider call."})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "cancelled"
    assert body["error_type"] == "RunCancelled"
    assert body["approvals"][0]["status"] == "cancelled"
    assert body["approvals"][0]["decision"] == "cancelled"
    assert body["approvals"][0]["decision_comment"] == "Stop before provider call."
    assert body["steps"][-1]["status"] == "cancelled"
    assert body["steps"][-1]["output"]["status"] == "cancelled"
    assert body["steps"][-1]["error_type"] == "RunCancelled"
    assert "run.cancelled" in [event["event_type"] for event in body["trace_events"]]
    assert fake_llm.calls == []

    pending = client.get("/approvals?status=pending").json()
    assert pending["items"] == []


def test_cancel_succeeded_run_is_rejected():
    fake_llm = SequencedLLMClient(outputs=["finished"])
    client = create_test_client(fake_llm)
    researcher = create_agent(client, "Cancel Finished Agent")
    workflow = client.post("/workflows", json={"name": "Cancel Finished Flow"}).json()
    client.post(
        f"/workflows/{workflow['id']}/versions",
        json={"graph": simple_graph(researcher["current_version_id"])},
    )
    run = client.post(
        f"/workflows/{workflow['id']}/runs",
        json={"input": {"topic": "AgentFlow", "audience": "CTO"}},
    ).json()
    executed = client.post(f"/runs/{run['id']}/execute").json()

    response = client.post(f"/runs/{run['id']}/cancel", json={"comment": "Too late."})

    assert executed["status"] == "succeeded"
    assert response.status_code == 409
    assert response.json()["detail"] == "Run cannot be cancelled from status: succeeded"
    detail = client.get(f"/runs/{run['id']}").json()
    assert detail["status"] == "succeeded"
    assert detail["cancelled_at"] is None


def test_worker_execute_next_queued_run_uses_claim_and_clears_it_after_terminal_state():
    fake_llm = SequencedLLMClient(outputs=["worker output"])
    client = create_test_client(fake_llm)
    researcher = create_agent(client, "Claim Execute Agent")
    workflow = client.post("/workflows", json={"name": "Claim Execute Flow"}).json()
    client.post(
        f"/workflows/{workflow['id']}/versions",
        json={"graph": simple_graph(researcher["current_version_id"])},
    )
    run = client.post(
        f"/workflows/{workflow['id']}/runs",
        json={"input": {"topic": "AgentFlow", "audience": "CTO"}},
    ).json()

    with client.app.state.session_factory() as session:
        executed = workflows.execute_next_queued_run(
            session,
            workspace_id=None,
            worker_id="worker-a",
            llm_client=fake_llm,
        )
        stored_run = session.get(Run, UUID(run["id"]))

    assert executed is not None
    assert executed.status == "succeeded"
    assert stored_run is not None
    assert stored_run.status == "succeeded"
    assert stored_run.worker_id is None
    assert stored_run.claim_token is None
    assert stored_run.lease_expires_at is None
    started_event = next(event for event in executed.trace_events if event.event_type == "run.started")
    assert started_event.actor_id == "worker-a"


def test_worker_preserves_current_node_checkpoint_when_waiting_for_tool_approval():
    client = create_test_client()
    agent = create_agent(client, "Checkpoint Tool Agent")
    client.post("/tools/seed-built-ins")
    markdown_tool = tool_by_name(client, "markdown_report_generate")
    with client.app.state.session_factory() as session:
        stored_tool = session.get(Tool, UUID(markdown_tool["id"]))
        assert stored_tool is not None
        stored_tool.risk_level = "external_effect"
        stored_tool.requires_approval = True
        session.commit()
    grant = client.post(f"/agents/{agent['id']}/tools/{markdown_tool['id']}/grant")
    assert grant.status_code == 201
    workflow = client.post("/workflows", json={"name": "Checkpoint Tool Flow"}).json()
    publish = client.post(
        f"/workflows/{workflow['id']}/versions",
        json={"graph": tool_graph(agent["id"], markdown_tool["id"])},
    )
    assert publish.status_code == 201
    run = client.post(
        f"/workflows/{workflow['id']}/runs",
        json={"input": {"title": "Checkpoint Report", "summary": "Needs approval."}},
    ).json()

    with client.app.state.session_factory() as session:
        paused = workflows.execute_next_queued_run(
            session,
            workspace_id=None,
            worker_id="worker-a",
            llm_client=object(),
        )
        stored_run = session.get(Run, UUID(run["id"]))

    assert paused is not None
    assert paused.status == "waiting_approval"
    assert stored_run is not None
    assert stored_run.status == "waiting_approval"
    assert stored_run.worker_id is None
    assert stored_run.claim_token is None
    assert stored_run.lease_expires_at is None
    assert stored_run.current_node_id == "node_tool"


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


def test_condition_node_publishes_and_executes_only_the_selected_branch():
    fake_llm = SequencedLLMClient(outputs=["urgent answer", "standard answer"])
    client = create_test_client(fake_llm)
    urgent_agent = create_agent(client, "Urgent Branch Agent")
    standard_agent = create_agent(client, "Standard Branch Agent")
    workflow = client.post("/workflows", json={"name": "Condition Node Flow"}).json()

    publish = client.post(
        f"/workflows/{workflow['id']}/versions",
        json={
            "graph": condition_graph(
                urgent_agent["current_version_id"],
                standard_agent["current_version_id"],
            )
        },
    )

    assert publish.status_code == 201
    version = publish.json()
    assert set(version["referenced_agent_versions"]) == {
        urgent_agent["current_version_id"],
        standard_agent["current_version_id"],
    }
    assert version["node_snapshots"]["node_condition"]["conditions"][0]["target"] == "node_urgent"

    urgent_run = client.post(
        f"/workflows/{workflow['id']}/runs",
        json={"input": {"topic": "Incident", "priority": "urgent"}},
    ).json()
    urgent_response = client.post(f"/runs/{urgent_run['id']}/execute")

    assert urgent_response.status_code == 200
    urgent_body = urgent_response.json()
    assert urgent_body["status"] == "succeeded"
    assert urgent_body["output"] == {"result": "urgent answer", "route": "urgent"}
    assert [step["node_id"] for step in urgent_body["steps"]] == [
        "node_start",
        "node_condition",
        "node_urgent",
        "node_urgent_end",
    ]
    assert urgent_body["steps"][1]["output"]["selected_target"] == "node_urgent"
    assert "condition.selected" in [event["event_type"] for event in urgent_body["trace_events"]]

    standard_run = client.post(
        f"/workflows/{workflow['id']}/runs",
        json={"input": {"topic": "Roadmap", "priority": "normal"}},
    ).json()
    standard_response = client.post(f"/runs/{standard_run['id']}/execute")

    assert standard_response.status_code == 200
    standard_body = standard_response.json()
    assert standard_body["status"] == "succeeded"
    assert standard_body["output"] == {"result": "standard answer", "route": "standard"}
    assert [step["node_id"] for step in standard_body["steps"]] == [
        "node_start",
        "node_condition",
        "node_standard",
        "node_standard_end",
    ]
    assert standard_body["steps"][1]["output"]["matched"] is False
    assert len(fake_llm.calls) == 2


def test_low_risk_tool_node_executes_and_records_tool_call():
    client = create_test_client()
    agent = create_agent(client, "Tool Workflow Agent")
    client.post("/tools/seed-built-ins")
    markdown_tool = tool_by_name(client, "markdown_report_generate")
    grant = client.post(f"/agents/{agent['id']}/tools/{markdown_tool['id']}/grant")
    assert grant.status_code == 201
    workflow = client.post("/workflows", json={"name": "Tool Execution Flow"}).json()
    publish = client.post(
        f"/workflows/{workflow['id']}/versions",
        json={"graph": tool_graph(agent["id"], markdown_tool["id"])},
    )
    assert publish.status_code == 201

    run = client.post(
        f"/workflows/{workflow['id']}/runs",
        json={"input": {"title": "AXON Tool Report", "summary": "Tool node executed."}},
    ).json()
    response = client.post(f"/runs/{run['id']}/execute")

    assert response.status_code == 200
    body = response.json()
    expected_markdown = "# AXON Tool Report\n\n## Summary\n\nTool node executed."
    assert body["status"] == "succeeded"
    assert body["output"] == {"markdown": expected_markdown}
    assert [step["node_id"] for step in body["steps"]] == ["node_start", "node_tool", "node_end"]
    assert body["steps"][1]["status"] == "succeeded"
    assert body["steps"][1]["output"] == {"markdown": expected_markdown}
    assert body["tool_calls"][0]["status"] == "succeeded"
    assert body["tool_calls"][0]["tool_name"] == "markdown_report_generate"
    assert body["tool_calls"][0]["run_id"] == body["id"]
    assert body["tool_calls"][0]["run_step_id"] == body["steps"][1]["id"]
    assert "tool.succeeded" in [event["event_type"] for event in body["trace_events"]]

    with client.app.state.session_factory() as session:
        stored_call = session.get(ToolCall, UUID(body["tool_calls"][0]["id"]))
        assert stored_call is not None
        assert stored_call.run_id == UUID(body["id"])
        assert stored_call.run_step_id == UUID(body["steps"][1]["id"])


def test_high_risk_tool_node_waits_for_approval_then_executes_once():
    client = create_test_client()
    agent = create_agent(client, "Approval Tool Agent")
    client.post("/tools/seed-built-ins")
    markdown_tool = tool_by_name(client, "markdown_report_generate")
    with client.app.state.session_factory() as session:
        stored_tool = session.get(Tool, UUID(markdown_tool["id"]))
        assert stored_tool is not None
        stored_tool.risk_level = "external_effect"
        stored_tool.requires_approval = True
        session.commit()
    grant = client.post(f"/agents/{agent['id']}/tools/{markdown_tool['id']}/grant")
    assert grant.status_code == 201
    workflow = client.post("/workflows", json={"name": "Approval Tool Flow"}).json()
    publish = client.post(
        f"/workflows/{workflow['id']}/versions",
        json={"graph": tool_graph(agent["id"], markdown_tool["id"])},
    )
    assert publish.status_code == 201
    run = client.post(
        f"/workflows/{workflow['id']}/runs",
        json={"input": {"title": "Approval Tool Report", "summary": "Approved execution."}},
    ).json()

    paused_response = client.post(f"/runs/{run['id']}/execute")

    assert paused_response.status_code == 200
    paused = paused_response.json()
    assert paused["status"] == "waiting_approval"
    assert [step["node_id"] for step in paused["steps"]] == ["node_start", "node_tool"]
    assert paused["steps"][1]["status"] == "waiting_approval"
    assert paused["approvals"][0]["status"] == "pending"
    assert paused["approvals"][0]["node_id"] == "node_tool"
    assert paused["approvals"][0]["requested_payload"]["title"] == "Approval Tool Report"
    assert paused["tool_calls"] == []
    requested_event = next(event for event in paused["trace_events"] if event["event_type"] == "approval.requested")
    assert requested_event["payload"]["node_id"] == "node_tool"

    response = client.post(
        f"/approvals/{paused['approvals'][0]['id']}/approve",
        json={"comment": "Approved for report generation."},
    )

    assert response.status_code == 200
    approved = response.json()
    assert approved["status"] == "queued"
    assert approved["approvals"][0]["status"] == "approved"
    assert approved["tool_calls"] == []

    with client.app.state.session_factory() as session:
        resumed = workflows.execute_next_queued_run(
            session,
            workspace_id=None,
            worker_id="worker-a",
            llm_client=object(),
        )
        session.commit()

    assert resumed is not None
    body = client.get(f"/runs/{run['id']}").json()
    expected_markdown = "# Approval Tool Report\n\n## Summary\n\nApproved execution."
    assert body["status"] == "succeeded"
    assert body["output"] == {"markdown": expected_markdown}
    assert [step["node_id"] for step in body["steps"]] == ["node_start", "node_tool", "node_end"]
    assert body["steps"][1]["status"] == "succeeded"
    assert body["steps"][1]["output"] == {"markdown": expected_markdown}
    assert body["approvals"][0]["status"] == "approved"
    assert body["tool_calls"][0]["status"] == "succeeded"
    assert body["tool_calls"][0]["run_step_id"] == body["steps"][1]["id"]
    assert [call["status"] for call in body["tool_calls"]] == ["succeeded"]
    event_types = [event["event_type"] for event in body["trace_events"]]
    assert "approval.approved" in event_types
    assert "tool.succeeded" in event_types


def test_approved_tool_node_is_requeued_and_worker_resumes_once():
    client = create_test_client()
    agent = create_agent(client, "Queued Approval Tool Agent")
    client.post("/tools/seed-built-ins")
    markdown_tool = tool_by_name(client, "markdown_report_generate")
    with client.app.state.session_factory() as session:
        stored_tool = session.get(Tool, UUID(markdown_tool["id"]))
        assert stored_tool is not None
        stored_tool.risk_level = "external_effect"
        stored_tool.requires_approval = True
        session.commit()
    grant = client.post(f"/agents/{agent['id']}/tools/{markdown_tool['id']}/grant")
    assert grant.status_code == 201
    workflow = client.post("/workflows", json={"name": "Queued Approval Tool Flow"}).json()
    publish = client.post(
        f"/workflows/{workflow['id']}/versions",
        json={"graph": tool_graph(agent["id"], markdown_tool["id"])},
    )
    assert publish.status_code == 201
    run = client.post(
        f"/workflows/{workflow['id']}/runs",
        json={"input": {"title": "Queued Tool Report", "summary": "Worker resumed execution."}},
    ).json()
    paused = client.post(f"/runs/{run['id']}/execute").json()

    approved_response = client.post(
        f"/approvals/{paused['approvals'][0]['id']}/approve",
        json={"comment": "Worker may continue."},
    )

    assert approved_response.status_code == 200
    approved = approved_response.json()
    assert approved["status"] == "queued"
    assert approved["approvals"][0]["status"] == "approved"
    assert approved["tool_calls"] == []
    assert approved["steps"][1]["status"] == "waiting_approval"

    with client.app.state.session_factory() as session:
        resumed = workflows.execute_next_queued_run(
            session,
            workspace_id=None,
            worker_id="worker-a",
            llm_client=object(),
        )
        session.commit()

    assert resumed is not None
    expected_markdown = "# Queued Tool Report\n\n## Summary\n\nWorker resumed execution."
    assert resumed.status == "succeeded"
    assert resumed.output == {"markdown": expected_markdown}
    assert [call.status for call in resumed.tool_calls] == ["succeeded"]
    assert resumed.tool_calls[0].run_step_id == resumed.steps[1].id
    event_types = [event.event_type for event in resumed.trace_events]
    assert event_types.count("approval.approved") == 1
    approval_queued_events = [
        event
        for event in resumed.trace_events
        if event.event_type == "run.queued" and event.payload.get("approval_id") == approved["approvals"][0]["id"]
    ]
    assert len(approval_queued_events) == 1


def test_approved_tool_node_stays_succeeded_when_downstream_step_fails():
    fake_llm = SequencedLLMClient(outputs=["__FAIL__"])
    client = create_test_client(fake_llm)
    agent = create_agent(client, "Tool Then Failing Agent")
    client.post("/tools/seed-built-ins")
    markdown_tool = tool_by_name(client, "markdown_report_generate")
    with client.app.state.session_factory() as session:
        stored_tool = session.get(Tool, UUID(markdown_tool["id"]))
        assert stored_tool is not None
        stored_tool.risk_level = "external_effect"
        stored_tool.requires_approval = True
        session.commit()
    grant = client.post(f"/agents/{agent['id']}/tools/{markdown_tool['id']}/grant")
    assert grant.status_code == 201
    workflow = client.post("/workflows", json={"name": "Approved Tool Downstream Failure Flow"}).json()
    publish = client.post(
        f"/workflows/{workflow['id']}/versions",
        json={"graph": tool_then_agent_graph(agent["id"], markdown_tool["id"], agent["current_version_id"])},
    )
    assert publish.status_code == 201
    run = client.post(
        f"/workflows/{workflow['id']}/runs",
        json={"input": {"title": "Approval Tool Report", "summary": "Approved execution."}},
    ).json()
    paused = client.post(f"/runs/{run['id']}/execute").json()

    response = client.post(
        f"/approvals/{paused['approvals'][0]['id']}/approve",
        json={"comment": "Approved before downstream failure."},
    )

    assert response.status_code == 200
    queued = response.json()
    assert queued["status"] == "queued"

    with client.app.state.session_factory() as session:
        resumed = workflows.execute_next_queued_run(
            session,
            workspace_id=None,
            worker_id="worker-a",
            llm_client=fake_llm,
        )
        session.commit()

    assert resumed is not None
    body = client.get(f"/runs/{run['id']}").json()
    steps_by_node = {step["node_id"]: step for step in body["steps"]}
    assert body["status"] == "failed"
    assert steps_by_node["node_tool"]["status"] == "succeeded"
    assert steps_by_node["node_agent"]["status"] == "failed"
    assert body["tool_calls"][0]["status"] == "succeeded"
    assert body["approvals"][0]["status"] == "approved"


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
    queued = response.json()
    assert queued["status"] == "queued"
    assert queued["approvals"][0]["status"] == "approved"
    assert queued["approvals"][0]["decision_comment"] == "Looks safe to continue."
    assert "approval.approved" in [event["event_type"] for event in queued["trace_events"]]
    assert "run.queued" in [event["event_type"] for event in queued["trace_events"]]
    assert fake_llm.calls == []

    with client.app.state.session_factory() as session:
        resumed = workflows.execute_next_queued_run(
            session,
            workspace_id=None,
            worker_id="worker-a",
            llm_client=fake_llm,
        )
        session.commit()

    assert resumed is not None
    body = client.get(f"/runs/{run['id']}").json()
    assert body["status"] == "succeeded"
    assert body["output"] == {"result": "approved answer"}
    assert [step["node_id"] for step in body["steps"]] == ["node_start", "node_approval", "node_agent", "node_end"]
    assert body["approvals"][0]["status"] == "approved"
    assert body["approvals"][0]["decision_comment"] == "Looks safe to continue."
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
    queued = response.json()
    assert queued["status"] == "queued"
    assert queued["approvals"][0]["status"] == "approved"
    assert queued["approvals"][0]["decision_comment"] == "Approved, but downstream provider fails."

    with client.app.state.session_factory() as session:
        resumed = workflows.execute_next_queued_run(
            session,
            workspace_id=None,
            worker_id="worker-a",
            llm_client=fake_llm,
        )
        session.commit()

    assert resumed is not None
    body = client.get(f"/runs/{run['id']}").json()
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


def tool_by_name(client: TestClient, name: str) -> dict[str, object]:
    response = client.get("/tools")
    assert response.status_code == 200
    for tool in response.json()["items"]:
        if tool["name"] == name:
            return tool
    raise AssertionError(f"Tool not found: {name}")


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


def tool_graph(agent_id: str, tool_id: str) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "nodes": [
            {"id": "node_start", "type": "start", "name": "Start", "config": {}},
            {
                "id": "node_tool",
                "type": "tool",
                "name": "Generate Markdown",
                "config": {"agent_id": agent_id, "tool_id": tool_id},
                "input_mapping": {
                    "title": "$.run.input.title",
                    "sections": [{"heading": "Summary", "content": "$.run.input.summary"}],
                },
            },
            {
                "id": "node_end",
                "type": "end",
                "name": "End",
                "config": {"output_mapping": {"markdown": "$.steps.node_tool.output.markdown"}},
            },
        ],
        "edges": [
            {"id": "edge_start_tool", "source": "node_start", "target": "node_tool", "type": "default"},
            {"id": "edge_tool_end", "source": "node_tool", "target": "node_end", "type": "default"},
        ],
    }


def tool_then_agent_graph(agent_id: str, tool_id: str, agent_version_id: str) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "nodes": [
            {"id": "node_start", "type": "start", "name": "Start", "config": {}},
            {
                "id": "node_tool",
                "type": "tool",
                "name": "Generate Markdown",
                "config": {"agent_id": agent_id, "tool_id": tool_id},
                "input_mapping": {
                    "title": "$.run.input.title",
                    "sections": [{"heading": "Summary", "content": "$.run.input.summary"}],
                },
            },
            {
                "id": "node_agent",
                "type": "agent",
                "name": "Summarize Tool Output",
                "config": {
                    "agent_version_id": agent_version_id,
                    "instruction": "Summarize the generated markdown.",
                },
                "input_mapping": {"markdown": "$.steps.node_tool.output.markdown"},
            },
            {
                "id": "node_end",
                "type": "end",
                "name": "End",
                "config": {"output_mapping": {"summary": "$.steps.node_agent.output.content"}},
            },
        ],
        "edges": [
            {"id": "edge_start_tool", "source": "node_start", "target": "node_tool", "type": "default"},
            {"id": "edge_tool_agent", "source": "node_tool", "target": "node_agent", "type": "default"},
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


def condition_graph(urgent_agent_version_id: str, standard_agent_version_id: str) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "nodes": [
            {
                "id": "node_start",
                "type": "start",
                "name": "Start",
                "position": {"x": 40, "y": 160},
                "config": {
                    "input_schema": {
                        "type": "object",
                        "required": ["topic", "priority"],
                        "properties": {"topic": {"type": "string"}, "priority": {"type": "string"}},
                    }
                },
            },
            {
                "id": "node_condition",
                "type": "condition",
                "name": "Priority Branch",
                "position": {"x": 300, "y": 160},
                "config": {
                    "conditions": [
                        {
                            "id": "urgent",
                            "label": "Urgent",
                            "path": "$.run.input.priority",
                            "operator": "equals",
                            "value": "urgent",
                            "target": "node_urgent",
                        }
                    ],
                    "default_target": "node_standard",
                },
            },
            {
                "id": "node_urgent",
                "type": "agent",
                "name": "Urgent Agent",
                "position": {"x": 580, "y": 40},
                "config": {
                    "agent_version_id": urgent_agent_version_id,
                    "instruction": "Handle urgent requests.",
                },
                "input_mapping": {"topic": "$.run.input.topic", "priority": "$.run.input.priority"},
            },
            {
                "id": "node_standard",
                "type": "agent",
                "name": "Standard Agent",
                "position": {"x": 580, "y": 280},
                "config": {
                    "agent_version_id": standard_agent_version_id,
                    "instruction": "Handle standard requests.",
                },
                "input_mapping": {"topic": "$.run.input.topic", "priority": "$.run.input.priority"},
            },
            {
                "id": "node_urgent_end",
                "type": "end",
                "name": "Urgent End",
                "position": {"x": 860, "y": 40},
                "config": {
                    "output_mapping": {
                        "result": "$.steps.node_urgent.output.content",
                        "route": "urgent",
                    }
                },
            },
            {
                "id": "node_standard_end",
                "type": "end",
                "name": "Standard End",
                "position": {"x": 860, "y": 280},
                "config": {
                    "output_mapping": {
                        "result": "$.steps.node_standard.output.content",
                        "route": "standard",
                    }
                },
            },
        ],
        "edges": [
            {"id": "edge_start_condition", "source": "node_start", "target": "node_condition", "type": "default"},
            {"id": "edge_condition_urgent", "source": "node_condition", "target": "node_urgent", "type": "branch"},
            {
                "id": "edge_condition_standard",
                "source": "node_condition",
                "target": "node_standard",
                "type": "default",
            },
            {"id": "edge_urgent_end", "source": "node_urgent", "target": "node_urgent_end", "type": "default"},
            {"id": "edge_standard_end", "source": "node_standard", "target": "node_standard_end", "type": "default"},
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
