from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.routes.agents import get_request_context
from app.db.session import get_session
from app.schemas.tools import (
    ToolCallListResponse,
    ToolCreate,
    ToolGrantRequest,
    ToolInvokeRequest,
    ToolInvokeResponse,
    ToolListResponse,
    ToolResponse,
    ToolSeedResponse,
)
from app.services import tools
from app.services.context import RequestContext

router = APIRouter(tags=["tools"])


@router.post("/tools/seed-built-ins", response_model=ToolSeedResponse, status_code=status.HTTP_201_CREATED)
def seed_built_ins(
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
) -> ToolSeedResponse:
    created, updated, items = tools.seed_built_in_tools(session, workspace_id=context.workspace.id)
    return ToolSeedResponse(created=created, updated=updated, items=items)


@router.get("/tools", response_model=ToolListResponse)
def list_tools(
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
) -> ToolListResponse:
    return ToolListResponse(items=tools.list_tools(session, workspace_id=context.workspace.id))


@router.post("/tools", response_model=ToolResponse, status_code=status.HTTP_201_CREATED)
def create_tool(
    payload: ToolCreate,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
) -> ToolResponse:
    try:
        return tools.create_tool(session, workspace_id=context.workspace.id, payload=payload)
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Tool name already exists") from exc


@router.get("/tools/calls", response_model=ToolCallListResponse)
def list_tool_calls(
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
) -> ToolCallListResponse:
    return ToolCallListResponse(items=tools.list_tool_calls(session, workspace_id=context.workspace.id))


@router.get("/tools/{tool_id}", response_model=ToolResponse)
def get_tool(
    tool_id: UUID,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
) -> ToolResponse:
    try:
        return tools.tool_response(tools.get_tool(session, workspace_id=context.workspace.id, tool_id=tool_id))
    except tools.ToolNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/tools/{tool_id}/enable", response_model=ToolResponse)
def enable_tool(
    tool_id: UUID,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
) -> ToolResponse:
    try:
        return tools.set_tool_status(session, workspace_id=context.workspace.id, tool_id=tool_id, status="active")
    except tools.ToolNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/tools/{tool_id}/disable", response_model=ToolResponse)
def disable_tool(
    tool_id: UUID,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
) -> ToolResponse:
    try:
        return tools.set_tool_status(session, workspace_id=context.workspace.id, tool_id=tool_id, status="disabled")
    except tools.ToolNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/agents/{agent_id}/tools/{tool_id}/grant", status_code=status.HTTP_201_CREATED)
def grant_tool_to_agent(
    agent_id: UUID,
    tool_id: UUID,
    payload: ToolGrantRequest | None = None,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
) -> object:
    try:
        return tools.grant_tool_to_agent(
            session,
            workspace_id=context.workspace.id,
            agent_id=agent_id,
            tool_id=tool_id,
            granted_by=context.user.id,
            policy=payload.policy if payload is not None else {},
        )
    except (tools.ToolNotFoundError, tools.ToolAgentNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/agents/{agent_id}/tools/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_tool_from_agent(
    agent_id: UUID,
    tool_id: UUID,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
) -> None:
    try:
        tools.revoke_tool_from_agent(
            session,
            workspace_id=context.workspace.id,
            agent_id=agent_id,
            tool_id=tool_id,
        )
    except (tools.ToolNotFoundError, tools.ToolAgentNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/tools/{tool_id}/invoke")
def invoke_tool(
    tool_id: UUID,
    payload: ToolInvokeRequest,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
) -> object:
    try:
        output, call = tools.invoke_tool(
            session,
            workspace_id=context.workspace.id,
            tool_id=tool_id,
            agent_id=payload.agent_id,
            tool_input=payload.input,
        )
    except (tools.ToolNotFoundError, tools.ToolAgentNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except tools.ToolExecutionRejected as exc:
        content = {"detail": exc.detail}
        if exc.tool_call is not None:
            content["tool_call"] = tools.tool_call_response(exc.tool_call).model_dump(mode="json")
        return JSONResponse(status_code=exc.status_code, content=content)

    return ToolInvokeResponse(
        status="succeeded",
        output=output,
        tool_call=tools.tool_call_response(call),
    )

