import json
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
            quality = evaluate_expected_output(case.expected, output)
            status = "succeeded" if executed.status == "succeeded" and quality["passed"] else "failed"
            error_message = executed.error_message
            if executed.status == "succeeded" and not quality["passed"]:
                error_message = quality["message"]
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
        "quality_pass_count": success_count,
        "quality_fail_count": failure_count,
        "quality_score_average": round(success_count / case_count, 4) if case_count else 0.0,
    }


def evaluate_expected_output(expected: dict[str, Any], output: dict[str, Any] | None) -> dict[str, Any]:
    if not expected:
        return {"passed": True, "score": 1.0, "message": ""}
    output_text = _json_text(output)
    checks: list[tuple[bool, str]] = []

    if "contains" in expected:
        required = _string_list(expected["contains"])
        missing = [value for value in required if value.lower() not in output_text.lower()]
        checks.append((not missing, f"missing expected text: {', '.join(missing)}"))
    if "not_contains" in expected:
        forbidden = _string_list(expected["not_contains"])
        present = [value for value in forbidden if value.lower() in output_text.lower()]
        checks.append((not present, f"found forbidden text: {', '.join(present)}"))
    if "equals" in expected:
        checks.append((output == expected["equals"], "output did not equal expected value"))
    if "json_path_equals" in expected:
        path_checks = expected["json_path_equals"]
        if isinstance(path_checks, dict):
            mismatches = [
                path
                for path, value in path_checks.items()
                if not isinstance(path, str) or _resolve_path(path, output or {}) != value
            ]
            checks.append((not mismatches, f"json path mismatch: {', '.join(mismatches)}"))
        else:
            checks.append((False, "json_path_equals must be an object"))
    if "required_citations" in expected:
        required_count = _coerce_int(expected["required_citations"])
        citations = output.get("citations") if isinstance(output, dict) else None
        actual_count = len(citations) if isinstance(citations, list) else 0
        checks.append((actual_count >= required_count, f"expected at least {required_count} citations"))

    if not checks:
        return {"passed": True, "score": 1.0, "message": ""}
    passed_count = sum(1 for passed, _ in checks if passed)
    failed_messages = [message for passed, message in checks if not passed]
    return {
        "passed": not failed_messages,
        "score": round(passed_count / len(checks), 4),
        "message": "; ".join(failed_messages),
    }


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _coerce_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _resolve_path(path: str, value: Any) -> Any:
    if not path.startswith("$."):
        return None
    current = value
    for part in path[2:].split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current
