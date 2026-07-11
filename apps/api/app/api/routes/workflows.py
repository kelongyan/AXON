from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from fastapi.exceptions import HTTPException
from sqlalchemy.orm import Session

from app.api.routes.agents import get_request_context
from app.db.session import get_session
from app.schemas.workflows import (
    ApprovalDecisionRequest,
    ApprovalListResponse,
    RunCancelRequest,
    RunCreate,
    RunListResponse,
    RunResponse,
    WorkflowCreate,
    WorkflowDetailResponse,
    WorkflowListResponse,
    WorkflowResponse,
    WorkflowVersionCreate,
    WorkflowVersionResponse,
)
from app.services import workflows
from app.services.context import RequestContext

router = APIRouter(tags=["workflows"])


@router.get("/workflows", response_model=WorkflowListResponse)
def list_workflows(
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
) -> WorkflowListResponse:
    return WorkflowListResponse(items=workflows.list_workflows(session, workspace_id=context.workspace.id))


@router.post("/workflows", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
def create_workflow(
    payload: WorkflowCreate,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
) -> WorkflowResponse:
    return workflows.create_workflow(
        session,
        workspace_id=context.workspace.id,
        created_by=context.user.id,
        payload=payload,
    )


@router.get("/workflows/{workflow_id}", response_model=WorkflowDetailResponse)
def get_workflow(
    workflow_id: UUID,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
) -> WorkflowDetailResponse:
    try:
        return workflows.get_workflow_detail(session, workspace_id=context.workspace.id, workflow_id=workflow_id)
    except workflows.WorkflowNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/workflows/{workflow_id}/versions",
    response_model=WorkflowVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
def publish_workflow_version(
    workflow_id: UUID,
    payload: WorkflowVersionCreate,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
) -> WorkflowVersionResponse:
    try:
        return workflows.publish_workflow_version(
            session,
            workspace_id=context.workspace.id,
            workflow_id=workflow_id,
            payload=payload,
        )
    except workflows.WorkflowNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except workflows.WorkflowValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/workflows/{workflow_id}/runs", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
def create_run(
    workflow_id: UUID,
    payload: RunCreate,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
) -> RunResponse:
    try:
        return workflows.create_run(
            session,
            workspace_id=context.workspace.id,
            workflow_id=workflow_id,
            triggered_by=context.user.id,
            payload=payload,
        )
    except workflows.WorkflowNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except workflows.WorkflowValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/runs", response_model=RunListResponse)
def list_runs(
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
) -> RunListResponse:
    return RunListResponse(items=workflows.list_runs(session, workspace_id=context.workspace.id))


@router.get("/approvals", response_model=ApprovalListResponse)
def list_approvals(
    status: str | None = None,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
) -> ApprovalListResponse:
    return ApprovalListResponse(
        items=workflows.list_approvals(session, workspace_id=context.workspace.id, status=status)
    )


@router.get("/runs/{run_id}", response_model=RunResponse)
def get_run(
    run_id: UUID,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
) -> RunResponse:
    try:
        return workflows.get_run_detail(session, workspace_id=context.workspace.id, run_id=run_id)
    except workflows.RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/runs/{run_id}/execute", response_model=RunResponse)
def execute_run(
    run_id: UUID,
    request: Request,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
) -> RunResponse:
    try:
        return workflows.execute_run(
            session,
            workspace_id=context.workspace.id,
            run_id=run_id,
            llm_client=request.app.state.llm_client,
            embedding_client=request.app.state.embedding_client,
        )
    except workflows.RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except workflows.RunExecutionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/runs/{run_id}/cancel", response_model=RunResponse)
def cancel_run(
    run_id: UUID,
    payload: RunCancelRequest,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
) -> RunResponse:
    try:
        return workflows.cancel_run(
            session,
            workspace_id=context.workspace.id,
            run_id=run_id,
            cancelled_by=context.user.id,
            comment=payload.comment,
        )
    except workflows.RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except workflows.RunExecutionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/approvals/{approval_id}/approve", response_model=RunResponse)
def approve_approval(
    approval_id: UUID,
    payload: ApprovalDecisionRequest,
    request: Request,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
) -> RunResponse:
    try:
        return workflows.resume_run_after_approval(
            session,
            workspace_id=context.workspace.id,
            approval_id=approval_id,
            decided_by=context.user.id,
            comment=payload.comment,
            llm_client=request.app.state.llm_client,
            embedding_client=request.app.state.embedding_client,
        )
    except workflows.ApprovalNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except workflows.ApprovalStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except workflows.RunExecutionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/approvals/{approval_id}/reject", response_model=RunResponse)
def reject_approval(
    approval_id: UUID,
    payload: ApprovalDecisionRequest,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
) -> RunResponse:
    try:
        return workflows.reject_approval(
            session,
            workspace_id=context.workspace.id,
            approval_id=approval_id,
            decided_by=context.user.id,
            comment=payload.comment,
        )
    except workflows.ApprovalNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except workflows.ApprovalStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
