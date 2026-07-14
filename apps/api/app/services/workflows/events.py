from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import Agent, AgentVersion, LLMCall, Run, RunStep, TraceEvent


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


