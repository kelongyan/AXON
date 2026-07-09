from time import perf_counter
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Evaluation, EvaluationCase, EvaluationResult, LLMCall, Workflow
from app.schemas.evaluations import EvaluationCreate, EvaluationResponse
from app.schemas.workflows import RunCreate
from app.services import workflows
from app.services.llm import sanitize_provider_error


class EvaluationNotFoundError(LookupError):
    pass


class EvaluationValidationError(ValueError):
    pass


def create_evaluation(
    session: Session,
    *,
    workspace_id: UUID,
    created_by: UUID,
    payload: EvaluationCreate,
) -> EvaluationResponse:
    workflow = session.scalar(
        select(Workflow).where(Workflow.id == payload.workflow_id, Workflow.workspace_id == workspace_id)
    )
    if workflow is None:
        raise EvaluationValidationError("Workflow not found")
    if workflow.current_version_id is None:
        raise EvaluationValidationError("Workflow must have a published version")

    evaluation = Evaluation(
        workspace_id=workspace_id,
        workflow_id=payload.workflow_id,
        name=payload.name,
        description=payload.description,
        status="draft",
        settings=payload.settings,
        summary=_empty_summary(case_count=len(payload.cases)),
        created_by=created_by,
    )
    session.add(evaluation)
    session.flush()
    for index, case_payload in enumerate(payload.cases, start=1):
        session.add(
            EvaluationCase(
                workspace_id=workspace_id,
                evaluation_id=evaluation.id,
                ordinal=index,
                name=case_payload.name,
                input=case_payload.input,
                expected=case_payload.expected,
            )
        )
    session.flush()
    session.refresh(evaluation)
    return get_evaluation_detail(session, workspace_id=workspace_id, evaluation_id=evaluation.id)


def list_evaluations(session: Session, *, workspace_id: UUID) -> list[EvaluationResponse]:
    evaluations = list(
        session.scalars(
            select(Evaluation)
            .where(Evaluation.workspace_id == workspace_id)
            .order_by(Evaluation.created_at.desc(), Evaluation.name.asc())
        )
    )
    return [_evaluation_response(session, evaluation) for evaluation in evaluations]


def get_evaluation_detail(
    session: Session,
    *,
    workspace_id: UUID,
    evaluation_id: UUID,
) -> EvaluationResponse:
    evaluation = _get_evaluation(session, workspace_id=workspace_id, evaluation_id=evaluation_id)
    return _evaluation_response(session, evaluation)


def run_evaluation(
    session: Session,
    *,
    workspace_id: UUID,
    evaluation_id: UUID,
    triggered_by: UUID,
    llm_client: object,
    embedding_client: object | None,
) -> EvaluationResponse:
    evaluation = _get_evaluation(session, workspace_id=workspace_id, evaluation_id=evaluation_id)
    cases = _evaluation_cases(session, evaluation.id)
    evaluation.status = "running"
    session.execute(sa.delete(EvaluationResult).where(EvaluationResult.evaluation_id == evaluation.id))
    session.flush()

    for case in cases:
        started = perf_counter()
        run_id: UUID | None = None
        output: dict[str, Any] | None = None
        error_message: str | None = None
        status = "failed"
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0
        try:
            run = workflows.create_run(
                session,
                workspace_id=workspace_id,
                workflow_id=evaluation.workflow_id,
                triggered_by=triggered_by,
                payload=RunCreate(input=case.input, metadata={"evaluation_id": str(evaluation.id), "case_id": str(case.id)}),
            )
            run_id = run.id
            executed = workflows.execute_run(
                session,
                workspace_id=workspace_id,
                run_id=run.id,
                llm_client=llm_client,
                embedding_client=embedding_client,
            )
            output = executed.output
            status = "succeeded" if executed.status == "succeeded" else "failed"
            error_message = executed.error_message
            token_row = session.execute(
                select(
                    sa.func.coalesce(sa.func.sum(LLMCall.prompt_tokens), 0),
                    sa.func.coalesce(sa.func.sum(LLMCall.completion_tokens), 0),
                    sa.func.coalesce(sa.func.sum(LLMCall.total_tokens), 0),
                ).where(LLMCall.run_id == run.id)
            ).one()
            prompt_tokens = int(token_row[0] or 0)
            completion_tokens = int(token_row[1] or 0)
            total_tokens = int(token_row[2] or 0)
        except Exception as exc:
            error_message = sanitize_provider_error(str(exc))
        latency_ms = max(0, round((perf_counter() - started) * 1000))
        session.add(
            EvaluationResult(
                workspace_id=workspace_id,
                evaluation_id=evaluation.id,
                case_id=case.id,
                run_id=run_id,
                status=status,
                output=output,
                error_message=error_message,
                latency_ms=latency_ms,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            )
        )
        session.flush()

    evaluation.status = "completed"
    evaluation.summary = _summary_for_evaluation(session, evaluation=evaluation, case_count=len(cases))
    session.flush()
    session.refresh(evaluation)
    return _evaluation_response(session, evaluation)


def _evaluation_response(session: Session, evaluation: Evaluation) -> EvaluationResponse:
    return EvaluationResponse(
        id=evaluation.id,
        workspace_id=evaluation.workspace_id,
        workflow_id=evaluation.workflow_id,
        name=evaluation.name,
        description=evaluation.description,
        status=evaluation.status,
        settings=evaluation.settings,
        summary=evaluation.summary,
        created_by=evaluation.created_by,
        created_at=evaluation.created_at,
        updated_at=evaluation.updated_at,
        cases=_evaluation_cases(session, evaluation.id),
        results=_evaluation_results(session, evaluation.id),
    )


def _get_evaluation(session: Session, *, workspace_id: UUID, evaluation_id: UUID) -> Evaluation:
    evaluation = session.scalar(
        select(Evaluation).where(Evaluation.id == evaluation_id, Evaluation.workspace_id == workspace_id)
    )
    if evaluation is None:
        raise EvaluationNotFoundError("Evaluation not found")
    return evaluation


def _evaluation_cases(session: Session, evaluation_id: UUID) -> list[EvaluationCase]:
    return list(
        session.scalars(
            select(EvaluationCase)
            .where(EvaluationCase.evaluation_id == evaluation_id)
            .order_by(EvaluationCase.ordinal.asc())
        )
    )


def _evaluation_results(session: Session, evaluation_id: UUID) -> list[EvaluationResult]:
    return list(
        session.scalars(
            select(EvaluationResult)
            .join(EvaluationCase, EvaluationResult.case_id == EvaluationCase.id)
            .where(EvaluationResult.evaluation_id == evaluation_id)
            .order_by(EvaluationCase.ordinal.asc(), EvaluationResult.created_at.asc(), EvaluationResult.id.asc())
        )
    )


def _empty_summary(*, case_count: int) -> dict[str, Any]:
    return {
        "case_count": case_count,
        "success_count": 0,
        "failure_count": 0,
        "average_latency_ms": 0,
        "total_tokens": 0,
        "estimated_cost": 0.0,
    }


def _summary_for_evaluation(session: Session, *, evaluation: Evaluation, case_count: int) -> dict[str, Any]:
    results = _evaluation_results(session, evaluation.id)
    success_count = sum(1 for result in results if result.status == "succeeded")
    failure_count = sum(1 for result in results if result.status != "succeeded")
    total_latency = sum(result.latency_ms for result in results)
    total_tokens = sum(result.total_tokens for result in results)
    token_price = evaluation.settings.get("token_price_per_1k", 0.0)
    try:
        token_price_float = float(token_price)
    except (TypeError, ValueError):
        token_price_float = 0.0
    return {
        "case_count": case_count,
        "success_count": success_count,
        "failure_count": failure_count,
        "average_latency_ms": round(total_latency / len(results)) if results else 0,
        "total_tokens": total_tokens,
        "estimated_cost": round((total_tokens / 1000) * token_price_float, 8),
    }
