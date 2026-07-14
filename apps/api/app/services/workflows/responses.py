from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Approval, LLMCall, Run, RunStep, ToolCall, TraceEvent, Workflow, WorkflowVersion
from app.schemas.workflows import (
    ApprovalResponse,
    RunResponse,
    TraceEventResponse,
    WorkflowResponse,
    WorkflowVersionResponse,
)
from app.services import tools as tool_services


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
    tool_calls = list(
        session.scalars(
            select(ToolCall).where(ToolCall.run_id == run.id).order_by(ToolCall.created_at.asc())
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
        worker_id=run.worker_id,
        lease_expires_at=run.lease_expires_at,
        current_node_id=run.current_node_id,
        started_at=run.started_at,
        finished_at=run.finished_at,
        cancelled_at=run.cancelled_at,
        created_at=run.created_at,
        updated_at=run.updated_at,
        steps=steps,
        llm_calls=calls,
        tool_calls=[tool_services.tool_call_response(call) for call in tool_calls],
        trace_events=[TraceEventResponse.model_validate(event) for event in events],
        approvals=[ApprovalResponse.model_validate(approval) for approval in approvals],
    )


