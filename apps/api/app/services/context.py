from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import User, Workspace, WorkspaceMember


@dataclass(frozen=True)
class RequestContext:
    user: User
    workspace: Workspace
    membership: WorkspaceMember


def ensure_default_context(session: Session, settings: Settings) -> RequestContext:
    return ensure_request_context(
        session,
        user_email=settings.dev_user_email,
        user_display_name=settings.dev_user_display_name,
        workspace_slug=settings.default_workspace_slug,
        workspace_name=settings.default_workspace_name,
    )


def ensure_request_context(
    session: Session,
    *,
    user_email: str,
    user_display_name: str,
    workspace_slug: str,
    workspace_name: str,
) -> RequestContext:
    user = session.scalar(select(User).where(User.email == user_email))
    if user is None:
        user = User(
            email=user_email,
            display_name=user_display_name,
            status="active",
        )
        session.add(user)
        session.flush()

    workspace = session.scalar(select(Workspace).where(Workspace.slug == workspace_slug))
    if workspace is None:
        workspace = Workspace(
            name=workspace_name,
            slug=workspace_slug,
            status="active",
            settings={},
        )
        session.add(workspace)
        session.flush()

    membership = session.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace.id,
            WorkspaceMember.user_id == user.id,
        )
    )
    if membership is None:
        membership = WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="admin")
        session.add(membership)
        session.flush()

    return RequestContext(user=user, workspace=workspace, membership=membership)
