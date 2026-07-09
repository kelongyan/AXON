from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.config import Settings
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
from app.services.context import RequestContext, ensure_default_context, ensure_request_context

router = APIRouter(tags=["agents"])


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_request_context(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    api_key: str | None = Header(default=None, alias="X-AgentFlow-API-Key"),
    workspace_slug: str | None = Header(default=None, alias="X-AgentFlow-Workspace-Slug"),
    workspace_name: str | None = Header(default=None, alias="X-AgentFlow-Workspace-Name"),
    user_email: str | None = Header(default=None, alias="X-AgentFlow-User-Email"),
    user_name: str | None = Header(default=None, alias="X-AgentFlow-User-Name"),
) -> RequestContext:
    configured_key = settings.api_auth_key.get_secret_value()
    if settings.environment != "development" and not configured_key:
        raise HTTPException(status_code=500, detail="AGENTFLOW_API_AUTH_KEY is required outside development")
    if configured_key and api_key != configured_key:
        raise HTTPException(status_code=401, detail="Invalid or missing AgentFlow API key")
    if not any([workspace_slug, workspace_name, user_email, user_name]):
        return ensure_default_context(session, settings)
    return ensure_request_context(
        session,
        user_email=(user_email or settings.dev_user_email).strip() or settings.dev_user_email,
        user_display_name=(user_name or settings.dev_user_display_name).strip() or settings.dev_user_display_name,
        workspace_slug=(workspace_slug or settings.default_workspace_slug).strip() or settings.default_workspace_slug,
        workspace_name=(workspace_name or workspace_slug or settings.default_workspace_name).strip()
        or settings.default_workspace_name,
    )


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
