from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Approval, Run, Workflow, WorkflowVersion

from .errors import ApprovalNotFoundError, RunNotFoundError, WorkflowNotFoundError


def _get_workflow(session: Session, *, workspace_id: UUID, workflow_id: UUID) -> Workflow:
    workflow = session.scalar(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.workspace_id == workspace_id)
    )
    if workflow is None:
        raise WorkflowNotFoundError("Workflow not found")
    return workflow


def _get_run(session: Session, *, workspace_id: UUID, run_id: UUID) -> Run:
    run = session.scalar(select(Run).where(Run.id == run_id, Run.workspace_id == workspace_id))
    if run is None:
        raise RunNotFoundError("Run not found")
    return run


def _get_approval(session: Session, *, workspace_id: UUID, approval_id: UUID) -> Approval:
    approval = session.scalar(
        select(Approval).where(Approval.id == approval_id, Approval.workspace_id == workspace_id)
    )
    if approval is None:
        raise ApprovalNotFoundError("Approval not found")
    return approval


def _get_current_version(session: Session, workflow: Workflow) -> WorkflowVersion | None:
    if workflow.current_version_id is None:
        return None
    return session.get(WorkflowVersion, workflow.current_version_id)


def _current_versions_by_workflow_id(session: Session, workflows: list[Workflow]) -> dict[UUID, WorkflowVersion]:
    version_ids = [
        workflow.current_version_id for workflow in workflows if workflow.current_version_id is not None
    ]
    if not version_ids:
        return {}
    versions = list(session.scalars(select(WorkflowVersion).where(WorkflowVersion.id.in_(version_ids))))
    return {version.workflow_id: version for version in versions}


