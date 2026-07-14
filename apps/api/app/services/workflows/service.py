from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Approval, Run, RunStep, Workflow, WorkflowVersion
from app.schemas.workflows import (
    RunCreate,
    RunResponse,
    WorkflowCreate,
    WorkflowDetailResponse,
    WorkflowResponse,
    WorkflowVersionCreate,
    WorkflowVersionResponse,
)
from app.services.tools import redact_mapping, validate_input_schema

from .errors import RunExecutionError, WorkflowValidationError
from .events import _trace_event
from .executor import _clear_run_claim
from .graph import _node_config, _nodes_by_id, _start_node_id, validate_phase3_graph
from .repository import _current_versions_by_workflow_id, _get_current_version, _get_run, _get_workflow
from .responses import run_response, workflow_response, workflow_version_response
from .utils import _now


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
        referenced_tool_versions=validation["referenced_tool_versions"],
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


def cancel_run(
    session: Session,
    *,
    workspace_id: UUID,
    run_id: UUID,
    cancelled_by: UUID,
    comment: str,
) -> RunResponse:
    run = _get_run(session, workspace_id=workspace_id, run_id=run_id)
    if run.status not in {"queued", "waiting_approval"}:
        raise RunExecutionError(f"Run cannot be cancelled from status: {run.status}")

    now = _now()
    message = comment or "Run cancelled"
    run.status = "cancelled"
    run.error_type = "RunCancelled"
    run.error_message = message
    run.finished_at = now
    run.cancelled_at = now
    run.current_node_id = None
    _clear_run_claim(run)
    pending_approvals = list(
        session.scalars(
            select(Approval).where(
                Approval.run_id == run.id,
                Approval.status == "pending",
            )
        )
    )
    for approval in pending_approvals:
        approval.status = "cancelled"
        approval.decision = "cancelled"
        approval.decision_comment = comment
        approval.decided_by = cancelled_by
        approval.decided_at = now
    waiting_steps = list(
        session.scalars(
            select(RunStep).where(
                RunStep.run_id == run.id,
                RunStep.status == "waiting_approval",
            )
        )
    )
    for step in waiting_steps:
        step.status = "cancelled"
        step.output = {
            **(step.output if isinstance(step.output, dict) else {}),
            "status": "cancelled",
            "decision": "cancelled",
            "comment": comment,
        }
        step.error_type = "RunCancelled"
        step.error_message = message
        step.finished_at = now
        state = dict(run.state or {})
        state_steps = dict(state.get("steps") or {})
        current_step_state = dict(state_steps.get(step.node_id) or {})
        current_step_output = current_step_state.get("output")
        current_step_state["output"] = {
            **(current_step_output if isinstance(current_step_output, dict) else {}),
            "status": "cancelled",
            "decision": "cancelled",
            "comment": comment,
        }
        state_steps[step.node_id] = current_step_state
        state["steps"] = state_steps
        run.state = state
    _trace_event(
        session,
        workspace_id=workspace_id,
        run=run,
        event_type="run.cancelled",
        severity="warning",
        actor_type="user",
        actor_id=str(cancelled_by),
        message="Run cancelled",
        payload={"comment": comment},
    )
    session.flush()
    session.refresh(run)
    return run_response(session, run)


