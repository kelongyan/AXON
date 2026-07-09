from datetime import UTC, datetime
from time import perf_counter
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Agent,
    AgentVersion,
    Approval,
    LLMCall,
    Run,
    RunStep,
    TraceEvent,
    Workflow,
    WorkflowVersion,
)
from app.schemas.workflows import (
    ApprovalResponse,
    RunCreate,
    RunResponse,
    TraceEventResponse,
    WorkflowCreate,
    WorkflowDetailResponse,
    WorkflowResponse,
    WorkflowVersionCreate,
    WorkflowVersionResponse,
)
from app.services.llm import LLMProviderError, sanitize_provider_error
from app.services import knowledge_bases
from app.services.tools import redact_mapping, validate_input_schema


class WorkflowNotFoundError(LookupError):
    pass


class WorkflowValidationError(ValueError):
    pass


class RunNotFoundError(LookupError):
    pass


class RunExecutionError(RuntimeError):
    pass


class ApprovalNotFoundError(LookupError):
    pass


class ApprovalStateError(ValueError):
    pass


class RunWaitingForApproval(RuntimeError):
    pass


EXECUTABLE_PHASE6_NODE_TYPES = {"start", "retrieval", "agent", "approval", "end"}
PLANNED_VISUAL_NODE_TYPES = {"tool", "condition"}


def create_workflow(
    session: Session,
    *,
    workspace_id: UUID,
    created_by: UUID,
    payload: WorkflowCreate,
) -> WorkflowResponse:
    workflow = Workflow(
        workspace_id=workspace_id,
        name=payload.name,
        description=payload.description,
        status="draft",
        created_by=created_by,
    )
    session.add(workflow)
    session.flush()
    session.refresh(workflow)
    return workflow_response(workflow, None)


def list_workflows(session: Session, *, workspace_id: UUID) -> list[WorkflowResponse]:
    workflows = list(
        session.scalars(
            select(Workflow)
            .where(Workflow.workspace_id == workspace_id)
            .order_by(Workflow.created_at.desc(), Workflow.name.asc())
        )
    )
    current_versions = _current_versions_by_workflow_id(session, workflows)
    return [workflow_response(workflow, current_versions.get(workflow.id)) for workflow in workflows]


def get_workflow_detail(session: Session, *, workspace_id: UUID, workflow_id: UUID) -> WorkflowDetailResponse:
    workflow = _get_workflow(session, workspace_id=workspace_id, workflow_id=workflow_id)
    current = _get_current_version(session, workflow)
    versions = list(
        session.scalars(
            select(WorkflowVersion)
            .where(WorkflowVersion.workflow_id == workflow.id)
            .order_by(WorkflowVersion.version_number.desc())
        )
    )
    base = workflow_response(workflow, current)
    return WorkflowDetailResponse(
        **base.model_dump(),
        versions=[workflow_version_response(version) for version in versions],
    )


def publish_workflow_version(
    session: Session,
    *,
    workspace_id: UUID,
    workflow_id: UUID,
    payload: WorkflowVersionCreate,
) -> WorkflowVersionResponse:
    workflow = _get_workflow(session, workspace_id=workspace_id, workflow_id=workflow_id)
    validation = validate_phase3_graph(session, workspace_id=workspace_id, graph=payload.graph)
    next_version_number = (
        session.scalar(
            select(sa.func.max(WorkflowVersion.version_number)).where(
                WorkflowVersion.workflow_id == workflow.id
            )
        )
        or 0
    ) + 1

    version = WorkflowVersion(
        workflow_id=workflow.id,
        version_number=next_version_number,
        graph=payload.graph,
        node_snapshots=validation["node_snapshots"],
        referenced_agent_versions=validation["referenced_agent_versions"],
        referenced_tool_versions=[],
        status="published",
    )
    session.add(version)
    session.flush()
    workflow.current_version_id = version.id
    workflow.status = "active"
    session.flush()
    session.refresh(version)
    return workflow_version_response(version)


def create_run(
    session: Session,
    *,
    workspace_id: UUID,
    workflow_id: UUID,
    triggered_by: UUID,
    payload: RunCreate,
) -> RunResponse:
    workflow = _get_workflow(session, workspace_id=workspace_id, workflow_id=workflow_id)
    version = _get_current_version(session, workflow)
    if version is None:
        raise WorkflowValidationError("Workflow has no published version")

    start_node = _nodes_by_id(version.graph)[_start_node_id(version.graph)]
    input_schema = _node_config(start_node).get("input_schema")
    if isinstance(input_schema, dict):
        validate_input_schema(input_schema, payload.input)

    run = Run(
        workspace_id=workspace_id,
        workflow_id=workflow.id,
        workflow_version_id=version.id,
        triggered_by=triggered_by,
        status="queued",
        input=payload.input,
        output=None,
        state={"metadata": payload.metadata, "steps": {}},
    )
    session.add(run)
    session.flush()
    _trace_event(
        session,
        workspace_id=workspace_id,
        run=run,
        event_type="run.created",
        actor_type="user",
        actor_id=str(triggered_by),
        message="Run created",
        payload={
            "workflow_id": str(workflow.id),
            "workflow_version_id": str(version.id),
            "input_summary": redact_mapping(payload.input),
        },
    )
    _trace_event(
        session,
        workspace_id=workspace_id,
        run=run,
        event_type="run.queued",
        actor_type="system",
        message="Run queued",
        payload={},
    )
    session.flush()
    session.refresh(run)
    return get_run_detail(session, workspace_id=workspace_id, run_id=run.id)


def list_runs(session: Session, *, workspace_id: UUID, limit: int = 50) -> list[RunResponse]:
    runs = list(
        session.scalars(
            select(Run)
            .where(Run.workspace_id == workspace_id)
            .order_by(Run.created_at.desc())
            .limit(limit)
        )
    )
    return [run_response(session, run) for run in runs]


def get_run_detail(session: Session, *, workspace_id: UUID, run_id: UUID) -> RunResponse:
    run = _get_run(session, workspace_id=workspace_id, run_id=run_id)
    return run_response(session, run)


def execute_run(
    session: Session,
    *,
    workspace_id: UUID,
    run_id: UUID,
    llm_client: object,
    embedding_client: object | None = None,
) -> RunResponse:
    run = _get_run(session, workspace_id=workspace_id, run_id=run_id)
    if run.status == "succeeded":
        return run_response(session, run)
    if run.status not in {"pending", "queued", "failed"}:
        raise RunExecutionError(f"Run cannot be executed from status: {run.status}")

    version = session.get(WorkflowVersion, run.workflow_version_id)
    if version is None:
        raise RunExecutionError("Workflow version not found")

    run.status = "running"
    run.started_at = _now()
    run.error_type = None
    run.error_message = None
    _trace_event(
        session,
        workspace_id=workspace_id,
        run=run,
        event_type="run.started",
        actor_type="worker",
        message="Run started",
        payload={},
    )
    session.flush()

    try:
        _execute_run_from_index(
            session,
            workspace_id=workspace_id,
            run=run,
            version=version,
            llm_client=llm_client,
            embedding_client=embedding_client,
            start_index=0,
        )
    except RunWaitingForApproval:
        pass
    except Exception as exc:
        run.status = "failed"
        run.error_type = exc.__class__.__name__
        run.error_message = sanitize_provider_error(str(exc))
        run.finished_at = _now()
        _trace_event(
            session,
            workspace_id=workspace_id,
            run=run,
            event_type="run.failed",
            severity="error",
            actor_type="worker",
            message="Run failed",
            payload={"error_type": run.error_type, "error_message": run.error_message},
        )
    session.flush()
    session.refresh(run)
    return run_response(session, run)


def resume_run_after_approval(
    session: Session,
    *,
    workspace_id: UUID,
    approval_id: UUID,
    decided_by: UUID,
    comment: str,
    llm_client: object,
    embedding_client: object | None = None,
) -> RunResponse:
    approval = _get_approval(session, workspace_id=workspace_id, approval_id=approval_id)
    if approval.status != "pending":
        raise ApprovalStateError("Approval is not pending")
    run = _get_run(session, workspace_id=workspace_id, run_id=approval.run_id)
    if run.status != "waiting_approval":
        raise RunExecutionError(f"Run cannot resume from status: {run.status}")
    step = session.get(RunStep, approval.run_step_id)
    if step is None:
        raise RunExecutionError("Approval step not found")

    now = _now()
    approval.status = "approved"
    approval.decision = "approved"
    approval.decision_comment = comment
    approval.decided_by = decided_by
    approval.decided_at = now
    step.status = "succeeded"
    step.output = {
        "approval_id": str(approval.id),
        "decision": "approved",
        "comment": comment,
    }
    step.finished_at = now
    context = _run_context(run)
    context.setdefault("steps", {})[approval.node_id] = {"output": step.output}
    run.state = context
    run.status = "running"
    run.error_type = None
    run.error_message = None
    _trace_event(
        session,
        workspace_id=workspace_id,
        run=run,
        step=step,
        event_type="approval.approved",
        actor_type="user",
        actor_id=str(decided_by),
        message=f"Approval approved: {approval.node_name}",
        payload={"approval_id": str(approval.id), "comment": comment},
    )
    _trace_event(
        session,
        workspace_id=workspace_id,
        run=run,
        event_type="run.resumed",
        actor_type="worker",
        message="Run resumed after approval",
        payload={"approval_id": str(approval.id), "node_id": approval.node_id},
    )
    session.flush()

    version = session.get(WorkflowVersion, run.workflow_version_id)
    if version is None:
        raise RunExecutionError("Workflow version not found")
    sequence = execution_sequence(version.graph)
    next_index = _node_index(sequence, approval.node_id) + 1
    try:
        _execute_run_from_index(
            session,
            workspace_id=workspace_id,
            run=run,
            version=version,
            llm_client=llm_client,
            embedding_client=embedding_client,
            start_index=next_index,
        )
    except RunWaitingForApproval:
        pass
    except Exception as exc:
        run.status = "failed"
        run.error_type = exc.__class__.__name__
        run.error_message = sanitize_provider_error(str(exc))
        run.finished_at = _now()
        _trace_event(
            session,
            workspace_id=workspace_id,
            run=run,
            event_type="run.failed",
            severity="error",
            actor_type="worker",
            message="Run failed after approval resume",
            payload={"error_type": run.error_type, "error_message": run.error_message},
        )
    session.flush()
    session.refresh(run)
    return run_response(session, run)


def reject_approval(
    session: Session,
    *,
    workspace_id: UUID,
    approval_id: UUID,
    decided_by: UUID,
    comment: str,
) -> RunResponse:
    approval = _get_approval(session, workspace_id=workspace_id, approval_id=approval_id)
    if approval.status != "pending":
        raise ApprovalStateError("Approval is not pending")
    run = _get_run(session, workspace_id=workspace_id, run_id=approval.run_id)
    step = session.get(RunStep, approval.run_step_id)
    now = _now()
    approval.status = "rejected"
    approval.decision = "rejected"
    approval.decision_comment = comment
    approval.decided_by = decided_by
    approval.decided_at = now
    if step is not None:
        step.status = "failed"
        step.error_type = "ApprovalRejected"
        step.error_message = comment or "Approval rejected"
        step.finished_at = now
    run.status = "failed"
    run.error_type = "ApprovalRejected"
    run.error_message = comment or "Approval rejected"
    run.finished_at = now
    _trace_event(
        session,
        workspace_id=workspace_id,
        run=run,
        step=step,
        event_type="approval.rejected",
        severity="error",
        actor_type="user",
        actor_id=str(decided_by),
        message=f"Approval rejected: {approval.node_name}",
        payload={"approval_id": str(approval.id), "comment": comment},
    )
    _trace_event(
        session,
        workspace_id=workspace_id,
        run=run,
        event_type="run.failed",
        severity="error",
        actor_type="system",
        message="Run failed after approval rejection",
        payload={"approval_id": str(approval.id), "error_type": "ApprovalRejected"},
    )
    session.flush()
    session.refresh(run)
    return run_response(session, run)


def execute_next_queued_run(
    session: Session,
    *,
    workspace_id: UUID | None,
    llm_client: object,
    embedding_client: object | None = None,
) -> RunResponse | None:
    query = select(Run).where(Run.status == "queued").order_by(Run.created_at.asc())
    if workspace_id is not None:
        query = query.where(Run.workspace_id == workspace_id)
    run = session.scalar(query.limit(1))
    if run is None:
        return None
    return execute_run(
        session,
        workspace_id=run.workspace_id,
        run_id=run.id,
        llm_client=llm_client,
        embedding_client=embedding_client,
    )


def list_approvals(session: Session, *, workspace_id: UUID, status: str | None = None) -> list[ApprovalResponse]:
    query = select(Approval).where(Approval.workspace_id == workspace_id).order_by(Approval.created_at.desc())
    if status is not None:
        query = query.where(Approval.status == status)
    return [ApprovalResponse.model_validate(approval) for approval in session.scalars(query)]


def _execute_run_from_index(
    session: Session,
    *,
    workspace_id: UUID,
    run: Run,
    version: WorkflowVersion,
    llm_client: object,
    embedding_client: object | None,
    start_index: int,
) -> None:
    context = _run_context(run)
    sequence = execution_sequence(version.graph)
    try:
        for node in sequence[start_index:]:
            step_output = _execute_node(
                session,
                workspace_id=workspace_id,
                run=run,
                node=node,
                context=context,
                llm_client=llm_client,
                embedding_client=embedding_client,
            )
            context["steps"][str(node["id"])] = {"output": step_output}
            run.state = context
        run.status = "succeeded"
        run.output = _find_end_output(context, version.graph)
        run.state = context
        run.finished_at = _now()
        _trace_event(
            session,
            workspace_id=workspace_id,
            run=run,
            event_type="run.succeeded",
            actor_type="worker",
            message="Run succeeded",
            payload={"output_summary": redact_mapping(run.output or {})},
        )
    except RunWaitingForApproval:
        run.state = context
        raise


def _run_context(run: Run) -> dict[str, Any]:
    state = run.state if isinstance(run.state, dict) else {}
    steps = state.get("steps")
    if not isinstance(steps, dict):
        steps = {}
    metadata = state.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    return {
        **state,
        "run": {"input": run.input, "metadata": metadata},
        "steps": steps,
    }


def _node_index(sequence: list[dict[str, Any]], node_id: str) -> int:
    for index, node in enumerate(sequence):
        if node.get("id") == node_id:
            return index
    raise RunExecutionError("Approval node not found in workflow graph")


def validate_phase3_graph(
    session: Session,
    *,
    workspace_id: UUID,
    graph: dict[str, Any],
) -> dict[str, Any]:
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise WorkflowValidationError("Graph must contain nodes and edges arrays")
    if not nodes:
        raise WorkflowValidationError("Graph must contain at least one node")

    node_ids = [node.get("id") for node in nodes if isinstance(node, dict)]
    if len(node_ids) != len(nodes) or any(not isinstance(node_id, str) or not node_id for node_id in node_ids):
        raise WorkflowValidationError("Every node requires a string id")
    if len(set(node_ids)) != len(node_ids):
        raise WorkflowValidationError("Node ids must be unique")

    start_nodes = [node for node in nodes if isinstance(node, dict) and node.get("type") == "start"]
    if len(start_nodes) != 1:
        raise WorkflowValidationError("Graph must contain exactly one start node")

    end_nodes = [node for node in nodes if isinstance(node, dict) and node.get("type") == "end"]
    if not end_nodes:
        raise WorkflowValidationError("Graph must contain at least one end node")

    for node in nodes:
        if not isinstance(node, dict):
            raise WorkflowValidationError("Each node must be an object")
        node_type = node.get("type")
        if node_type in PLANNED_VISUAL_NODE_TYPES:
            raise WorkflowValidationError(f"Node type is planned but not executable in Phase 6 MVP: {node_type}")
        if node_type not in EXECUTABLE_PHASE6_NODE_TYPES:
            raise WorkflowValidationError(f"Node type is not supported in Phase 6 MVP: {node_type}")
        if not isinstance(node.get("name"), str) or not node["name"]:
            raise WorkflowValidationError("Every node requires a name")
        if node_type == "approval":
            config = _node_config(node)
            title = str(config.get("title") or node["name"] or "").strip()
            instructions = str(config.get("instructions") or "").strip()
            if not title and not instructions:
                raise WorkflowValidationError("Approval node requires title or instructions")

    edge_ids = [edge.get("id") for edge in edges if isinstance(edge, dict)]
    if len(edge_ids) != len(edges) or any(not isinstance(edge_id, str) or not edge_id for edge_id in edge_ids):
        raise WorkflowValidationError("Every edge requires a string id")
    if len(set(edge_ids)) != len(edge_ids):
        raise WorkflowValidationError("Edge ids must be unique")

    valid_node_ids = set(node_ids)
    for edge in edges:
        if not isinstance(edge, dict):
            raise WorkflowValidationError("Each edge must be an object")
        if edge.get("source") not in valid_node_ids or edge.get("target") not in valid_node_ids:
            raise WorkflowValidationError("Every edge source and target must reference existing nodes")

    sequence = execution_sequence(graph)
    if sequence[0].get("type") != "start" or sequence[-1].get("type") != "end":
        raise WorkflowValidationError("Phase 6 MVP graph must execute from start to end")
    if len(sequence) != len(nodes):
        raise WorkflowValidationError("Phase 6 MVP graph must be a single reachable sequential path")

    referenced_agent_versions: list[str] = []
    node_snapshots: dict[str, Any] = {}
    for node in sequence:
        if node.get("type") != "agent":
            if node.get("type") == "retrieval":
                knowledge_base_ids = _coerce_uuid_list(
                    _node_config(node).get("knowledge_base_ids"),
                    "Retrieval node requires knowledge_base_ids",
                )
                if not knowledge_base_ids:
                    raise WorkflowValidationError("Retrieval node requires knowledge_base_ids")
                try:
                    knowledge_bases.validate_knowledge_base_ids(
                        session,
                        workspace_id=workspace_id,
                        knowledge_base_ids=knowledge_base_ids,
                    )
                except knowledge_bases.KnowledgeBaseNotFoundError as exc:
                    raise WorkflowValidationError(str(exc)) from exc
                top_k = _node_config(node).get("top_k", 5)
                if not isinstance(top_k, int) or top_k < 1 or top_k > 20:
                    raise WorkflowValidationError("Retrieval node top_k must be between 1 and 20")
                node_snapshots[str(node["id"])] = {
                    "knowledge_base_ids": [str(knowledge_base_id) for knowledge_base_id in knowledge_base_ids],
                    "top_k": top_k,
                }
            elif node.get("type") == "approval":
                config = _node_config(node)
                node_snapshots[str(node["id"])] = {
                    "title": str(config.get("title") or node["name"]),
                    "risk_level": str(config.get("risk_level") or "medium"),
                }
            continue
        version_id = _coerce_uuid(_node_config(node).get("agent_version_id"), "Agent node requires agent_version_id")
        agent_version = session.scalar(
            select(AgentVersion)
            .join(Agent, AgentVersion.agent_id == Agent.id)
            .where(
                AgentVersion.id == version_id,
                Agent.workspace_id == workspace_id,
                AgentVersion.status == "published",
            )
        )
        if agent_version is None:
            raise WorkflowValidationError("Agent node must reference a published Agent Version")
        referenced_agent_versions.append(str(agent_version.id))
        node_snapshots[str(node["id"])] = {
            "agent_id": str(agent_version.agent_id),
            "agent_version_id": str(agent_version.id),
            "version_number": agent_version.version_number,
            "model_provider": agent_version.model_provider,
            "model_name": agent_version.model_name,
            "knowledge_base_ids": agent_version.knowledge_base_ids_snapshot,
        }

    return {
        "referenced_agent_versions": referenced_agent_versions,
        "node_snapshots": node_snapshots,
    }


def execution_sequence(graph: dict[str, Any]) -> list[dict[str, Any]]:
    nodes_by_id = _nodes_by_id(graph)
    edges = graph.get("edges", [])
    if not isinstance(edges, list):
        raise WorkflowValidationError("Graph edges must be an array")
    outgoing: dict[str, list[str]] = {}
    for edge in edges:
        if not isinstance(edge, dict):
            raise WorkflowValidationError("Each edge must be an object")
        source = edge.get("source")
        target = edge.get("target")
        if isinstance(source, str) and isinstance(target, str):
            outgoing.setdefault(source, []).append(target)

    current = _start_node_id(graph)
    visited: set[str] = set()
    sequence: list[dict[str, Any]] = []
    while True:
        if current in visited:
            raise WorkflowValidationError("Phase 6 MVP graph cannot contain cycles")
        visited.add(current)
        node = nodes_by_id[current]
        sequence.append(node)
        if node.get("type") == "end":
            return sequence
        targets = outgoing.get(current, [])
        if len(targets) != 1:
            raise WorkflowValidationError("Phase 6 MVP nodes must have exactly one default outgoing edge")
        current = targets[0]
        if current not in nodes_by_id:
            raise WorkflowValidationError("Every edge target must reference an existing node")


def workflow_response(workflow: Workflow, current_version: WorkflowVersion | None) -> WorkflowResponse:
    return WorkflowResponse(
        id=workflow.id,
        workspace_id=workflow.workspace_id,
        name=workflow.name,
        description=workflow.description,
        status=workflow.status,
        current_version_id=workflow.current_version_id,
        created_by=workflow.created_by,
        created_at=workflow.created_at,
        updated_at=workflow.updated_at,
        current_version=workflow_version_response(current_version) if current_version is not None else None,
    )


def workflow_version_response(version: WorkflowVersion) -> WorkflowVersionResponse:
    return WorkflowVersionResponse.model_validate(version)


def run_response(session: Session, run: Run) -> RunResponse:
    steps = list(
        session.scalars(
            select(RunStep)
            .where(RunStep.run_id == run.id)
            .order_by(RunStep.started_at.asc(), RunStep.created_at.asc(), RunStep.id.asc())
        )
    )
    calls = list(
        session.scalars(
            select(LLMCall).where(LLMCall.run_id == run.id).order_by(LLMCall.created_at.asc())
        )
    )
    events = list(
        session.scalars(
            select(TraceEvent).where(TraceEvent.run_id == run.id).order_by(TraceEvent.created_at.asc())
        )
    )
    approvals = list(
        session.scalars(
            select(Approval).where(Approval.run_id == run.id).order_by(Approval.created_at.asc(), Approval.id.asc())
        )
    )
    return RunResponse(
        id=run.id,
        workspace_id=run.workspace_id,
        workflow_id=run.workflow_id,
        workflow_version_id=run.workflow_version_id,
        triggered_by=run.triggered_by,
        status=run.status,
        input=run.input,
        output=run.output,
        error_type=run.error_type,
        error_message=run.error_message,
        started_at=run.started_at,
        finished_at=run.finished_at,
        cancelled_at=run.cancelled_at,
        created_at=run.created_at,
        updated_at=run.updated_at,
        steps=steps,
        llm_calls=calls,
        trace_events=[TraceEventResponse.model_validate(event) for event in events],
        approvals=[ApprovalResponse.model_validate(approval) for approval in approvals],
    )


def _execute_node(
    session: Session,
    *,
    workspace_id: UUID,
    run: Run,
    node: dict[str, Any],
    context: dict[str, Any],
    llm_client: object,
    embedding_client: object | None,
) -> dict[str, Any]:
    now = _now()
    step = RunStep(
        workspace_id=workspace_id,
        run_id=run.id,
        node_id=str(node["id"]),
        node_type=str(node["type"]),
        node_name=str(node["name"]),
        status="running",
        attempt=1,
        input={},
        started_at=now,
    )
    session.add(step)
    session.flush()
    _trace_event(
        session,
        workspace_id=workspace_id,
        run=run,
        step=step,
        event_type="step.started",
        actor_type="worker",
        message=f"Step started: {step.node_name}",
        payload={"node_id": step.node_id, "node_type": step.node_type},
    )

    try:
        if node["type"] == "start":
            output = {"input": run.input}
            step.input = run.input
        elif node["type"] == "agent":
            step_input = resolve_mapping(node.get("input_mapping", {}), context)
            step.input = step_input
            output = _execute_agent_node(
                session,
                workspace_id=workspace_id,
                run=run,
                step=step,
                node=node,
                node_input=step_input,
                llm_client=llm_client,
                embedding_client=embedding_client,
            )
        elif node["type"] == "retrieval":
            step_input = resolve_mapping(node.get("input_mapping", {}), context)
            step.input = step_input
            output = _execute_retrieval_node(
                session,
                workspace_id=workspace_id,
                node=node,
                node_input=step_input,
                embedding_client=embedding_client,
            )
        elif node["type"] == "approval":
            step_input = resolve_mapping(node.get("input_mapping", {}), context)
            step.input = step_input
            _execute_approval_node(
                session,
                workspace_id=workspace_id,
                run=run,
                step=step,
                node=node,
                node_input=step_input,
            )
            raise RunWaitingForApproval()
        elif node["type"] == "end":
            output = resolve_mapping(_node_config(node).get("output_mapping", {}), context)
            step.input = output
        else:
            raise WorkflowValidationError(f"Unsupported node type: {node['type']}")
        step.status = "succeeded"
        step.output = output
        step.finished_at = _now()
        _trace_event(
            session,
            workspace_id=workspace_id,
            run=run,
            step=step,
            event_type="step.succeeded",
            actor_type="worker",
            message=f"Step succeeded: {step.node_name}",
            payload={"node_id": step.node_id, "node_type": step.node_type},
        )
        session.flush()
        return output
    except RunWaitingForApproval:
        raise
    except Exception as exc:
        step.status = "failed"
        step.error_type = exc.__class__.__name__
        step.error_message = sanitize_provider_error(str(exc))
        step.finished_at = _now()
        _trace_event(
            session,
            workspace_id=workspace_id,
            run=run,
            step=step,
            event_type="step.failed",
            severity="error",
            actor_type="worker",
            message=f"Step failed: {step.node_name}",
            payload={
                "node_id": step.node_id,
                "node_type": step.node_type,
                "error_type": step.error_type,
                "error_message": step.error_message,
            },
        )
        session.flush()
        raise


def _execute_agent_node(
    session: Session,
    *,
    workspace_id: UUID,
    run: Run,
    step: RunStep,
    node: dict[str, Any],
    node_input: dict[str, Any],
    llm_client: object,
    embedding_client: object | None,
) -> dict[str, Any]:
    agent_version_id = _coerce_uuid(_node_config(node).get("agent_version_id"), "Agent node requires agent_version_id")
    version = session.get(AgentVersion, agent_version_id)
    if version is None:
        raise WorkflowValidationError("Agent Version not found")
    agent = session.get(Agent, version.agent_id)
    if agent is None:
        raise WorkflowValidationError("Agent not found")

    instruction = str(_node_config(node).get("instruction") or "")
    retrieval_results = _retrieve_for_agent_if_configured(
        session,
        workspace_id=workspace_id,
        version=version,
        node=node,
        node_input=node_input,
        embedding_client=embedding_client,
    )
    input_payload: dict[str, Any] = dict(node_input)
    citations: list[dict[str, Any]] = []
    if retrieval_results:
        input_payload["retrieval_context"] = knowledge_bases.retrieval_context(retrieval_results)
        citations = knowledge_bases.citation_payloads(retrieval_results)
        input_payload["citations"] = citations

    user_content = {
        "instruction": instruction,
        "input": input_payload,
    }
    messages = [
        {"role": "system", "content": f"{version.role_prompt}\n\n{version.system_prompt}"},
        {"role": "user", "content": _jsonish(user_content)},
    ]
    started = perf_counter()
    try:
        completion = llm_client.complete(
            messages=messages,
            model=version.model_name,
            temperature=float(version.temperature),
            max_output_tokens=version.max_output_tokens,
        )
    except LLMProviderError as exc:
        latency_ms = _elapsed_ms(started)
        message = sanitize_provider_error(str(exc))
        _log_llm_call(
            session,
            workspace_id=workspace_id,
            agent=agent,
            version=version,
            run=run,
            step=step,
            status="failed",
            latency_ms=latency_ms,
            error_message=message,
        )
        raise RunExecutionError(message) from exc

    _log_llm_call(
        session,
        workspace_id=workspace_id,
        agent=agent,
        version=version,
        run=run,
        step=step,
        status="succeeded",
        latency_ms=_elapsed_ms(started),
        prompt_tokens=completion.prompt_tokens,
        completion_tokens=completion.completion_tokens,
        total_tokens=completion.total_tokens,
    )
    output: dict[str, Any] = {"content": completion.content}
    if citations:
        output["citations"] = citations
    return output


def _execute_retrieval_node(
    session: Session,
    *,
    workspace_id: UUID,
    node: dict[str, Any],
    node_input: dict[str, Any],
    embedding_client: object | None,
) -> dict[str, Any]:
    if embedding_client is None:
        raise RunExecutionError("Retrieval node requires an embedding client")
    query = str(node_input.get("query") or node_input.get("question") or node_input.get("topic") or "").strip()
    if not query:
        raise WorkflowValidationError("Retrieval node input requires query")
    config = _node_config(node)
    knowledge_base_ids = _coerce_uuid_list(config.get("knowledge_base_ids"), "Retrieval node requires knowledge_base_ids")
    top_k = config.get("top_k", 5)
    if not isinstance(top_k, int):
        top_k = 5
    results = knowledge_bases.search_knowledge_bases(
        session,
        workspace_id=workspace_id,
        knowledge_base_ids=knowledge_base_ids,
        query=query,
        top_k=top_k,
        embedding_client=embedding_client,
    )
    return {
        "query": query,
        "context": knowledge_bases.retrieval_context(results),
        "citations": knowledge_bases.citation_payloads(results),
        "results": [
            {
                "chunk_id": str(result.chunk_id),
                "document_id": str(result.document_id),
                "knowledge_base_id": str(result.knowledge_base_id),
                "content": result.content,
                "score": result.score,
                "source": {
                    "knowledge_base_id": str(result.source.knowledge_base_id),
                    "document_id": str(result.source.document_id),
                    "chunk_id": str(result.source.chunk_id),
                    "filename": result.source.filename,
                    "ordinal": result.source.ordinal,
                    "metadata": result.source.metadata,
                },
            }
            for result in results
        ],
    }


def _execute_approval_node(
    session: Session,
    *,
    workspace_id: UUID,
    run: Run,
    step: RunStep,
    node: dict[str, Any],
    node_input: dict[str, Any],
) -> None:
    config = _node_config(node)
    title = str(config.get("title") or node.get("name") or "Approval required").strip()
    instructions = str(config.get("instructions") or "").strip()
    risk_level = str(config.get("risk_level") or "medium").strip() or "medium"
    existing = session.scalar(
        select(Approval).where(
            Approval.run_id == run.id,
            Approval.node_id == str(node["id"]),
            Approval.status == "pending",
        )
    )
    if existing is not None:
        run.status = "waiting_approval"
        step.status = "waiting_approval"
        session.flush()
        return

    approval = Approval(
        workspace_id=workspace_id,
        run_id=run.id,
        run_step_id=step.id,
        node_id=str(node["id"]),
        node_name=str(node["name"]),
        title=title,
        instructions=instructions,
        risk_level=risk_level,
        status="pending",
        requested_payload=redact_mapping(node_input),
        decision=None,
        decision_comment="",
    )
    session.add(approval)
    session.flush()
    step.status = "waiting_approval"
    step.output = {"approval_id": str(approval.id), "status": "pending"}
    run.status = "waiting_approval"
    _trace_event(
        session,
        workspace_id=workspace_id,
        run=run,
        step=step,
        event_type="approval.requested",
        actor_type="system",
        message=f"Approval requested: {step.node_name}",
        payload={
            "approval_id": str(approval.id),
            "node_id": step.node_id,
            "risk_level": risk_level,
            "input_summary": redact_mapping(node_input),
        },
    )
    session.flush()


def _retrieve_for_agent_if_configured(
    session: Session,
    *,
    workspace_id: UUID,
    version: AgentVersion,
    node: dict[str, Any],
    node_input: dict[str, Any],
    embedding_client: object | None,
) -> list[knowledge_bases.RetrievalResult]:
    config = _node_config(node)
    configured_ids = config.get("knowledge_base_ids") or version.knowledge_base_ids_snapshot
    knowledge_base_ids = _coerce_uuid_list(configured_ids, "Agent knowledge_base_ids must be UUIDs")
    if not knowledge_base_ids:
        return []
    if embedding_client is None:
        raise RunExecutionError("Agent knowledge-base retrieval requires an embedding client")
    query = str(
        config.get("retrieval_query")
        or node_input.get("query")
        or node_input.get("question")
        or node_input.get("topic")
        or _jsonish(node_input)
    ).strip()
    top_k = config.get("top_k", 5)
    if not isinstance(top_k, int):
        top_k = 5
    return knowledge_bases.search_knowledge_bases(
        session,
        workspace_id=workspace_id,
        knowledge_base_ids=knowledge_base_ids,
        query=query,
        top_k=top_k,
        embedding_client=embedding_client,
    )


def resolve_mapping(mapping: Any, context: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(mapping, dict):
        return {}
    resolved: dict[str, Any] = {}
    for key, value in mapping.items():
        if isinstance(value, str) and value.startswith("$."):
            resolved[str(key)] = _resolve_path(value, context)
        else:
            resolved[str(key)] = value
    return resolved


def _resolve_path(path: str, context: dict[str, Any]) -> Any:
    current: Any = context
    for part in path[2:].split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def _find_end_output(context: dict[str, Any], graph: dict[str, Any]) -> dict[str, Any] | None:
    for node in execution_sequence(graph):
        if node.get("type") == "end":
            output = context.get("steps", {}).get(str(node["id"]), {}).get("output")
            return output if isinstance(output, dict) else None
    return None


def _trace_event(
    session: Session,
    *,
    workspace_id: UUID,
    run: Run,
    event_type: str,
    actor_type: str,
    message: str,
    payload: dict[str, Any],
    step: RunStep | None = None,
    severity: str = "info",
    actor_id: str | None = None,
) -> TraceEvent:
    event = TraceEvent(
        workspace_id=workspace_id,
        run_id=run.id,
        run_step_id=step.id if step is not None else None,
        event_type=event_type,
        severity=severity,
        actor_type=actor_type,
        actor_id=actor_id,
        message=message,
        payload=payload,
    )
    session.add(event)
    session.flush()
    return event


def _log_llm_call(
    session: Session,
    *,
    workspace_id: UUID,
    agent: Agent,
    version: AgentVersion,
    run: Run,
    step: RunStep,
    status: str,
    latency_ms: int,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
    error_message: str | None = None,
) -> LLMCall:
    call = LLMCall(
        workspace_id=workspace_id,
        agent_id=agent.id,
        agent_version_id=version.id,
        run_id=run.id,
        run_step_id=step.id,
        provider=version.model_provider,
        model=version.model_name,
        status=status,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        latency_ms=latency_ms,
        error_message=error_message,
    )
    session.add(call)
    session.flush()
    return call


def _get_workflow(session: Session, *, workspace_id: UUID, workflow_id: UUID) -> Workflow:
    workflow = session.scalar(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.workspace_id == workspace_id)
    )
    if workflow is None:
        raise WorkflowNotFoundError("Workflow not found")
    return workflow


def _get_run(session: Session, *, workspace_id: UUID, run_id: UUID) -> Run:
    run = session.scalar(select(Run).where(Run.id == run_id, Run.workspace_id == workspace_id))
    if run is None:
        raise RunNotFoundError("Run not found")
    return run


def _get_approval(session: Session, *, workspace_id: UUID, approval_id: UUID) -> Approval:
    approval = session.scalar(
        select(Approval).where(Approval.id == approval_id, Approval.workspace_id == workspace_id)
    )
    if approval is None:
        raise ApprovalNotFoundError("Approval not found")
    return approval


def _get_current_version(session: Session, workflow: Workflow) -> WorkflowVersion | None:
    if workflow.current_version_id is None:
        return None
    return session.get(WorkflowVersion, workflow.current_version_id)


def _current_versions_by_workflow_id(session: Session, workflows: list[Workflow]) -> dict[UUID, WorkflowVersion]:
    version_ids = [
        workflow.current_version_id for workflow in workflows if workflow.current_version_id is not None
    ]
    if not version_ids:
        return {}
    versions = list(session.scalars(select(WorkflowVersion).where(WorkflowVersion.id.in_(version_ids))))
    return {version.workflow_id: version for version in versions}


def _nodes_by_id(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    nodes = graph.get("nodes", [])
    if not isinstance(nodes, list):
        raise WorkflowValidationError("Graph nodes must be an array")
    return {str(node["id"]): node for node in nodes if isinstance(node, dict) and "id" in node}


def _start_node_id(graph: dict[str, Any]) -> str:
    starts = [
        str(node["id"])
        for node in graph.get("nodes", [])
        if isinstance(node, dict) and node.get("type") == "start" and "id" in node
    ]
    if len(starts) != 1:
        raise WorkflowValidationError("Graph must contain exactly one start node")
    return starts[0]


def _node_config(node: dict[str, Any]) -> dict[str, Any]:
    config = node.get("config")
    return config if isinstance(config, dict) else {}


def _coerce_uuid(value: object, message: str) -> UUID:
    try:
        return UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise WorkflowValidationError(message) from exc


def _coerce_uuid_list(value: object, message: str) -> list[UUID]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise WorkflowValidationError(message)
    try:
        return [UUID(str(item)) for item in value]
    except (TypeError, ValueError) as exc:
        raise WorkflowValidationError(message) from exc


def _jsonish(value: Any) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _elapsed_ms(started: float) -> int:
    return max(0, round((perf_counter() - started) * 1000))


def _now() -> datetime:
    return datetime.now(UTC)
