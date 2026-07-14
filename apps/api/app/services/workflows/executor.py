from time import perf_counter
from typing import Any
from uuid import UUID, uuid4
from datetime import timedelta

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Agent, AgentVersion, Approval, Run, RunStep, Tool, WorkflowVersion
from app.schemas.workflows import ApprovalResponse, RunResponse
from app.services import knowledge_bases, tools as tool_services
from app.services.llm import LLMProviderError, sanitize_provider_error
from app.services.tools import ToolExecutionRejected, redact_mapping

from .errors import (
    ApprovalStateError,
    RunExecutionError,
    RunWaitingForApproval,
    TERMINAL_RUN_STATUSES,
    WorkflowValidationError,
)
from .events import _log_llm_call, _trace_event
from .graph import _coerce_uuid, _coerce_uuid_list, _node_config, execution_sequence
from .repository import _get_approval, _get_run
from .responses import run_response
from .utils import _elapsed_ms, _jsonish, _now


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

    return _execute_running_run(
        session,
        workspace_id=workspace_id,
        run=run,
        version=version,
        llm_client=llm_client,
        embedding_client=embedding_client,
    )


def execute_claimed_run(
    session: Session,
    *,
    workspace_id: UUID,
    run_id: UUID,
    claim_token: str,
    llm_client: object,
    embedding_client: object | None = None,
) -> RunResponse:
    run = _get_run(session, workspace_id=workspace_id, run_id=run_id)
    if run.status != "running" or run.claim_token != claim_token:
        raise RunExecutionError("Run is not claimed by this worker")
    version = session.get(WorkflowVersion, run.workflow_version_id)
    if version is None:
        raise RunExecutionError("Workflow version not found")
    start_index = 0
    if run.current_node_id:
        sequence = execution_sequence(version.graph)
        node_index = _node_index(sequence, run.current_node_id)
        step = _latest_run_step(session, run_id=run.id, node_id=run.current_node_id)
        if step is not None and step.node_type == "tool" and step.status == "waiting_approval":
            approval = _approved_approval_for_node(session, run=run, node_id=run.current_node_id)
            return _resume_tool_node_after_approval(
                session,
                workspace_id=workspace_id,
                approval=approval,
                run=run,
                step=step,
                llm_client=llm_client,
                embedding_client=embedding_client,
                clear_claim=True,
                expected_claim_token=claim_token,
            )
        start_index = node_index + 1 if step is not None and step.status == "succeeded" else node_index
    return _execute_running_run(
        session,
        workspace_id=workspace_id,
        run=run,
        version=version,
        llm_client=llm_client,
        embedding_client=embedding_client,
        start_index=start_index,
        clear_claim=True,
        expected_claim_token=claim_token,
    )


def _execute_running_run(
    session: Session,
    *,
    workspace_id: UUID,
    run: Run,
    version: WorkflowVersion,
    llm_client: object,
    embedding_client: object | None,
    start_index: int = 0,
    clear_claim: bool = False,
    expected_claim_token: str | None = None,
) -> RunResponse:
    try:
        _execute_run_from_index(
            session,
            workspace_id=workspace_id,
            run=run,
            version=version,
            llm_client=llm_client,
            embedding_client=embedding_client,
            start_index=start_index,
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
    if clear_claim and expected_claim_token is not None:
        _assert_claim_still_owned(session, run_id=run.id, claim_token=expected_claim_token)
    if clear_claim:
        _clear_run_claim(run)
    if run.status in TERMINAL_RUN_STATUSES:
        run.current_node_id = None
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
    if step.node_type == "tool":
        return _queue_tool_node_after_approval(
            session,
            workspace_id=workspace_id,
            approval=approval,
            run=run,
            step=step,
            decided_by=decided_by,
            comment=comment,
        )

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
    run.status = "queued"
    run.current_node_id = approval.node_id
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
        event_type="run.queued",
        actor_type="system",
        message="Run queued after approval",
        payload={"approval_id": str(approval.id), "node_id": approval.node_id},
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


def claim_next_queued_run(
    session: Session,
    *,
    workspace_id: UUID | None,
    worker_id: str,
    lease_seconds: int = 60,
) -> Run | None:
    worker_id = worker_id.strip()
    if not worker_id:
        raise RunExecutionError("worker_id is required")

    now = _now()
    claimable_filter = sa.or_(
        Run.status == "queued",
        sa.and_(Run.status == "running", Run.lease_expires_at.is_not(None), Run.lease_expires_at < now),
    )
    query = select(Run).where(claimable_filter).order_by(Run.created_at.asc(), Run.id.asc()).limit(1)
    if workspace_id is not None:
        query = query.where(Run.workspace_id == workspace_id)
    run = session.scalar(query.with_for_update(skip_locked=True))
    if run is None:
        return None

    claim_token = str(uuid4())
    result = session.execute(
        sa.update(Run)
        .where(Run.id == run.id, claimable_filter)
        .values(
            status="running",
            worker_id=worker_id,
            claim_token=claim_token,
            lease_expires_at=now + timedelta(seconds=max(1, lease_seconds)),
            started_at=run.started_at or now,
            error_type=None,
            error_message=None,
        )
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        return None
    session.flush()
    session.refresh(run)
    _trace_event(
        session,
        workspace_id=run.workspace_id,
        run=run,
        event_type="run.started",
        actor_type="worker",
        actor_id=worker_id,
        message="Run claimed by worker",
        payload={"worker_id": worker_id, "lease_expires_at": run.lease_expires_at.isoformat()},
    )
    session.flush()
    session.refresh(run)
    return run


def renew_run_lease(
    session: Session,
    *,
    workspace_id: UUID | None,
    run_id: UUID,
    claim_token: str,
    lease_seconds: int = 60,
) -> bool:
    claim_token = claim_token.strip()
    if not claim_token:
        raise RunExecutionError("claim_token is required")

    query = (
        sa.update(Run)
        .where(
            Run.id == run_id,
            Run.status == "running",
            Run.claim_token == claim_token,
        )
        .values(lease_expires_at=_now() + timedelta(seconds=max(1, lease_seconds)))
        .execution_options(synchronize_session="fetch")
    )
    if workspace_id is not None:
        query = query.where(Run.workspace_id == workspace_id)
    result = session.execute(query)
    session.flush()
    return result.rowcount == 1


def _clear_run_claim(run: Run) -> None:
    run.worker_id = None
    run.claim_token = None
    run.lease_expires_at = None


def _assert_claim_still_owned(session: Session, *, run_id: UUID, claim_token: str) -> None:
    with session.no_autoflush:
        current_token = session.scalar(select(Run.__table__.c.claim_token).where(Run.__table__.c.id == run_id))
    if current_token != claim_token:
        raise RunExecutionError("Run claim was lost before execution completed")


def _queue_tool_node_after_approval(
    session: Session,
    *,
    workspace_id: UUID,
    approval: Approval,
    run: Run,
    step: RunStep,
    decided_by: UUID,
    comment: str,
) -> RunResponse:
    now = _now()
    approval.status = "approved"
    approval.decision = "approved"
    approval.decision_comment = comment
    approval.decided_by = decided_by
    approval.decided_at = now
    run.status = "queued"
    run.current_node_id = approval.node_id
    run.error_type = None
    run.error_message = None
    step.status = "waiting_approval"
    step.error_type = None
    step.error_message = None
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
        event_type="run.queued",
        actor_type="system",
        message="Run queued after approval",
        payload={"approval_id": str(approval.id), "node_id": approval.node_id},
    )
    session.flush()
    session.refresh(run)
    return run_response(session, run)


def _resume_tool_node_after_approval(
    session: Session,
    *,
    workspace_id: UUID,
    approval: Approval,
    run: Run,
    step: RunStep,
    llm_client: object,
    embedding_client: object | None,
    clear_claim: bool = False,
    expected_claim_token: str | None = None,
) -> RunResponse:
    run.status = "running"
    run.error_type = None
    run.error_message = None
    step.status = "running"
    step.error_type = None
    step.error_message = None
    session.flush()

    version = session.get(WorkflowVersion, run.workflow_version_id)
    if version is None:
        raise RunExecutionError("Workflow version not found")
    sequence = execution_sequence(version.graph)
    node_index = _node_index(sequence, approval.node_id)
    node = sequence[node_index]
    context = _run_context(run)

    try:
        output = _execute_tool_node(
            session,
            workspace_id=workspace_id,
            run=run,
            step=step,
            node=node,
            node_input=step.input,
            approval_granted=True,
        )
        step.status = "succeeded"
        step.output = output
        step.finished_at = _now()
        context.setdefault("steps", {})[approval.node_id] = {"output": output}
        run.state = context
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
        _execute_run_from_index(
            session,
            workspace_id=workspace_id,
            run=run,
            version=version,
            llm_client=llm_client,
            embedding_client=embedding_client,
            start_index=node_index + 1,
        )
    except RunWaitingForApproval:
        pass
    except Exception as exc:
        if step.status != "succeeded":
            step.status = "failed"
            step.error_type = exc.__class__.__name__
            step.error_message = sanitize_provider_error(str(exc))
            step.finished_at = _now()
        run.status = "failed"
        run.error_type = exc.__class__.__name__
        run.error_message = sanitize_provider_error(str(exc))
        run.finished_at = _now()
        if step.status == "failed":
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
    if clear_claim and expected_claim_token is not None:
        _assert_claim_still_owned(session, run_id=run.id, claim_token=expected_claim_token)
    if clear_claim:
        _clear_run_claim(run)
    if run.status in TERMINAL_RUN_STATUSES:
        run.current_node_id = None
    session.flush()
    session.refresh(run)
    return run_response(session, run)


def execute_next_queued_run(
    session: Session,
    *,
    workspace_id: UUID | None,
    llm_client: object,
    embedding_client: object | None = None,
    worker_id: str = "worker",
    lease_seconds: int = 60,
) -> RunResponse | None:
    run = claim_next_queued_run(
        session,
        workspace_id=workspace_id,
        worker_id=worker_id,
        lease_seconds=lease_seconds,
    )
    if run is None:
        return None
    if run.claim_token is None:
        raise RunExecutionError("Claimed run is missing claim token")
    return execute_claimed_run(
        session,
        workspace_id=run.workspace_id,
        run_id=run.id,
        claim_token=run.claim_token,
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


def _latest_run_step(session: Session, *, run_id: UUID, node_id: str) -> RunStep | None:
    return session.scalar(
        select(RunStep)
        .where(RunStep.run_id == run_id, RunStep.node_id == node_id)
        .order_by(RunStep.attempt.desc(), RunStep.created_at.desc(), RunStep.id.desc())
        .limit(1)
    )


def _approved_approval_for_node(session: Session, *, run: Run, node_id: str) -> Approval:
    approval = session.scalar(
        select(Approval)
        .where(
            Approval.run_id == run.id,
            Approval.node_id == node_id,
            Approval.status == "approved",
        )
        .order_by(Approval.decided_at.desc(), Approval.created_at.desc(), Approval.id.desc())
        .limit(1)
    )
    if approval is None:
        raise RunExecutionError("Approved approval not found for checkpoint")
    return approval




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
    run.current_node_id = str(node["id"])
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
        elif node["type"] == "tool":
            step_input = resolve_mapping(node.get("input_mapping", {}), context)
            step.input = step_input
            output = _execute_tool_node(
                session,
                workspace_id=workspace_id,
                run=run,
                step=step,
                node=node,
                node_input=step_input,
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


def _execute_tool_node(
    session: Session,
    *,
    workspace_id: UUID,
    run: Run,
    step: RunStep,
    node: dict[str, Any],
    node_input: dict[str, Any],
    approval_granted: bool = False,
) -> dict[str, Any]:
    config = _node_config(node)
    agent_id = _coerce_uuid(config.get("agent_id"), "Tool node requires agent_id")
    tool_id = _coerce_uuid(config.get("tool_id"), "Tool node requires tool_id")
    tool = tool_services.get_tool(session, workspace_id=workspace_id, tool_id=tool_id)
    if _tool_requires_approval(tool) and not approval_granted:
        _request_tool_approval(
            session,
            workspace_id=workspace_id,
            run=run,
            step=step,
            node=node,
            node_input=node_input,
            tool=tool,
        )
        raise RunWaitingForApproval()
    try:
        output, call = tool_services.invoke_tool(
            session,
            workspace_id=workspace_id,
            tool_id=tool_id,
            agent_id=agent_id,
            tool_input=node_input,
            run_id=run.id,
            run_step_id=step.id,
            approval_granted=approval_granted,
        )
    except ToolExecutionRejected as exc:
        if exc.tool_call is not None:
            _trace_event(
                session,
                workspace_id=workspace_id,
                run=run,
                step=step,
                event_type="tool.failed",
                severity="error",
                actor_type="worker",
                message=f"Tool failed: {exc.tool_call.tool_name}",
                payload={
                    "tool_call_id": str(exc.tool_call.id),
                    "tool_name": exc.tool_call.tool_name,
                    "status": exc.tool_call.status,
                    "error_message": exc.detail,
                },
            )
        raise
    _trace_event(
        session,
        workspace_id=workspace_id,
        run=run,
        step=step,
        event_type="tool.succeeded",
        actor_type="worker",
        message=f"Tool succeeded: {call.tool_name}",
        payload={
            "tool_call_id": str(call.id),
            "tool_name": call.tool_name,
            "output_summary": redact_mapping(output),
        },
    )
    return output


def _request_tool_approval(
    session: Session,
    *,
    workspace_id: UUID,
    run: Run,
    step: RunStep,
    node: dict[str, Any],
    node_input: dict[str, Any],
    tool: Tool,
) -> None:
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

    config = _node_config(node)
    title = str(config.get("approval_title") or f"Approve tool: {tool.display_name}").strip()
    instructions = str(config.get("approval_instructions") or tool.description or "").strip()
    approval = Approval(
        workspace_id=workspace_id,
        run_id=run.id,
        run_step_id=step.id,
        node_id=str(node["id"]),
        node_name=str(node["name"]),
        title=title,
        instructions=instructions,
        risk_level=tool.risk_level,
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
            "tool_id": str(tool.id),
            "tool_name": tool.name,
            "risk_level": tool.risk_level,
            "input_summary": redact_mapping(node_input),
        },
    )
    session.flush()


def _tool_requires_approval(tool: Tool) -> bool:
    return tool.requires_approval or tool.risk_level in tool_services.APPROVAL_RISK_LEVELS


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
        resolved[str(key)] = _resolve_value(value, context)
    return resolved


def _resolve_value(value: Any, context: dict[str, Any]) -> Any:
    if isinstance(value, str) and value.startswith("$."):
        return _resolve_path(value, context)
    if isinstance(value, list):
        return [_resolve_value(item, context) for item in value]
    if isinstance(value, dict):
        return {str(key): _resolve_value(item, context) for key, item in value.items()}
    return value


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


