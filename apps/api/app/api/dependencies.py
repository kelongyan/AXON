from fastapi import Depends, Header, Request
from fastapi.exceptions import HTTPException
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.session import get_session
from app.services.context import RequestContext, ensure_default_context, ensure_request_context


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
