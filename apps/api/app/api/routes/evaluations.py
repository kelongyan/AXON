from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from fastapi.exceptions import HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_request_context
from app.db.session import get_session
from app.schemas.evaluations import EvaluationCreate, EvaluationListResponse, EvaluationResponse
from app.services import evaluations
from app.services.context import RequestContext

router = APIRouter(tags=["evaluations"])


@router.get("/evaluations", response_model=EvaluationListResponse)
def list_evaluations(
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
) -> EvaluationListResponse:
    return EvaluationListResponse(items=evaluations.list_evaluations(session, workspace_id=context.workspace.id))


@router.post("/evaluations", response_model=EvaluationResponse, status_code=status.HTTP_201_CREATED)
def create_evaluation(
    payload: EvaluationCreate,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
) -> EvaluationResponse:
    try:
        return evaluations.create_evaluation(
            session,
            workspace_id=context.workspace.id,
            created_by=context.user.id,
            payload=payload,
        )
    except evaluations.EvaluationValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/evaluations/{evaluation_id}", response_model=EvaluationResponse)
def get_evaluation(
    evaluation_id: UUID,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
) -> EvaluationResponse:
    try:
        return evaluations.get_evaluation_detail(
            session,
            workspace_id=context.workspace.id,
            evaluation_id=evaluation_id,
        )
    except evaluations.EvaluationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/evaluations/{evaluation_id}/run", response_model=EvaluationResponse)
def run_evaluation(
    evaluation_id: UUID,
    request: Request,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
) -> EvaluationResponse:
    try:
        return evaluations.run_evaluation(
            session,
            workspace_id=context.workspace.id,
            evaluation_id=evaluation_id,
            triggered_by=context.user.id,
            llm_client=request.app.state.llm_client,
            embedding_client=request.app.state.embedding_client,
        )
    except evaluations.EvaluationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
