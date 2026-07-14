from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_request_context
from app.db.session import get_session
from app.schemas.agents import (
    AgentCreate,
    AgentDetailResponse,
    AgentListResponse,
    AgentResponse,
    AgentTestRunRequest,
    AgentUpdate,
    AgentVersionCreate,
    AgentVersionResponse,
    MeResponse,
    MembershipResponse,
)
from app.services import agents
from app.services.context import RequestContext

router = APIRouter(tags=["agents"])


@router.get("/me", response_model=MeResponse)
def read_me(context: RequestContext = Depends(get_request_context)) -> MeResponse:
    return MeResponse(
        user=context.user,
        workspace=context.workspace,
        membership=MembershipResponse(role=context.membership.role),
    )


@router.get("/agents", response_model=AgentListResponse)
def list_agents(
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
) -> AgentListResponse:
    return AgentListResponse(items=agents.list_agents(session, workspace_id=context.workspace.id))


@router.post("/agents", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
def create_agent(
    payload: AgentCreate,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
) -> AgentResponse:
    try:
        return agents.create_agent(session, workspace_id=context.workspace.id, payload=payload)
    except agents.AgentValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/agents/{agent_id}", response_model=AgentDetailResponse)
def get_agent(
    agent_id: UUID,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
) -> AgentDetailResponse:
    try:
        return agents.get_agent_detail(session, workspace_id=context.workspace.id, agent_id=agent_id)
    except agents.AgentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/agents/{agent_id}", response_model=AgentResponse)
def update_agent(
    agent_id: UUID,
    payload: AgentUpdate,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
) -> AgentResponse:
    try:
        return agents.update_agent(
            session,
            workspace_id=context.workspace.id,
            agent_id=agent_id,
            payload=payload,
        )
    except agents.AgentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/agents/{agent_id}/versions",
    response_model=AgentVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
def publish_agent_version(
    agent_id: UUID,
    payload: AgentVersionCreate,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
) -> AgentVersionResponse:
    try:
        return agents.publish_agent_version(
            session,
            workspace_id=context.workspace.id,
            agent_id=agent_id,
            payload=payload,
        )
    except agents.AgentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except agents.AgentValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/agents/{agent_id}/clone", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
def clone_agent(
    agent_id: UUID,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
) -> AgentResponse:
    try:
        return agents.clone_agent(session, workspace_id=context.workspace.id, agent_id=agent_id)
    except agents.AgentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/agents/{agent_id}/disable", response_model=AgentResponse)
def disable_agent(
    agent_id: UUID,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
) -> AgentResponse:
    try:
        return agents.disable_agent(session, workspace_id=context.workspace.id, agent_id=agent_id)
    except agents.AgentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/agents/{agent_id}/test-runs")
def test_agent(
    agent_id: UUID,
    payload: AgentTestRunRequest,
    request: Request,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
) -> object:
    try:
        result = agents.run_agent_test(
            session,
            workspace_id=context.workspace.id,
            agent_id=agent_id,
            user_input=payload.input,
            llm_client=request.app.state.llm_client,
        )
    except agents.AgentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if result.error_message is not None:
        return JSONResponse(status_code=502, content={"detail": result.error_message})
    return result.response
