from dataclasses import dataclass
from time import perf_counter
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Agent, AgentVersion, LLMCall
from app.schemas.agents import (
    AgentCreate,
    AgentDetailResponse,
    AgentResponse,
    AgentTestRunResponse,
    AgentUpdate,
    AgentVersionCreate,
    AgentVersionResponse,
    LLMCallResponse,
)
from app.services.llm import LLMProviderError, sanitize_provider_error
from app.services import knowledge_bases


class AgentNotFoundError(LookupError):
    pass


class AgentValidationError(ValueError):
    pass


@dataclass(frozen=True)
class AgentTestRunResult:
    response: AgentTestRunResponse | None = None
    error_message: str | None = None


def create_agent(session: Session, *, workspace_id: UUID, payload: AgentCreate) -> AgentResponse:
    agent = Agent(
        workspace_id=workspace_id,
        name=payload.name,
        description=payload.description,
        status="active",
    )
    session.add(agent)
    session.flush()

    version = _create_version(
        session,
        workspace_id=workspace_id,
        agent_id=agent.id,
        version_number=1,
        payload=payload,
    )
    agent.current_version_id = version.id
    session.flush()
    session.refresh(agent)
    session.refresh(version)
    return agent_response(agent, version)


def list_agents(session: Session, *, workspace_id: UUID) -> list[AgentResponse]:
    agents = list(
        session.scalars(
            select(Agent)
            .where(Agent.workspace_id == workspace_id)
            .order_by(Agent.created_at.desc(), Agent.name.asc())
        )
    )
    versions = _current_versions_by_agent_id(session, agents)
    return [agent_response(agent, versions.get(agent.id)) for agent in agents]


def get_agent_detail(session: Session, *, workspace_id: UUID, agent_id: UUID) -> AgentDetailResponse:
    agent = _get_agent(session, workspace_id=workspace_id, agent_id=agent_id)
    current_version = _get_current_version(session, agent)
    versions = list(
        session.scalars(
            select(AgentVersion)
            .where(AgentVersion.agent_id == agent.id)
            .order_by(AgentVersion.version_number.desc())
        )
    )
    calls = list(
        session.scalars(
            select(LLMCall)
            .where(LLMCall.agent_id == agent.id)
            .order_by(LLMCall.created_at.desc())
            .limit(10)
        )
    )
    base = agent_response(agent, current_version)
    return AgentDetailResponse(
        **base.model_dump(),
        versions=[version_response(version) for version in versions],
        recent_llm_calls=[llm_call_response(call) for call in calls],
    )


def update_agent(
    session: Session,
    *,
    workspace_id: UUID,
    agent_id: UUID,
    payload: AgentUpdate,
) -> AgentResponse:
    agent = _get_agent(session, workspace_id=workspace_id, agent_id=agent_id)
    changes = payload.model_dump(exclude_unset=True)
    for field in ("name", "description", "status"):
        if field in changes:
            setattr(agent, field, changes[field])
    session.flush()
    session.refresh(agent)
    return agent_response(agent, _get_current_version(session, agent))


def publish_agent_version(
    session: Session,
    *,
    workspace_id: UUID,
    agent_id: UUID,
    payload: AgentVersionCreate,
) -> AgentVersionResponse:
    agent = _get_agent(session, workspace_id=workspace_id, agent_id=agent_id)
    next_version_number = (
        session.scalar(
            select(sa.func.max(AgentVersion.version_number)).where(AgentVersion.agent_id == agent.id)
        )
        or 0
    ) + 1
    version = _create_version(
        session,
        workspace_id=workspace_id,
        agent_id=agent.id,
        version_number=next_version_number,
        payload=payload,
    )
    agent.current_version_id = version.id
    if agent.status == "draft":
        agent.status = "active"
    session.flush()
    session.refresh(version)
    return version_response(version)


def clone_agent(session: Session, *, workspace_id: UUID, agent_id: UUID) -> AgentResponse:
    source = _get_agent(session, workspace_id=workspace_id, agent_id=agent_id)
    current = _get_current_version(session, source)
    if current is None:
        raise AgentNotFoundError("Agent has no current version")

    clone_payload = AgentCreate(
        name=f"{source.name} Copy",
        description=source.description,
        role_prompt=current.role_prompt,
        system_prompt=current.system_prompt,
        model_provider=current.model_provider,
        model_name=current.model_name,
        temperature=float(current.temperature),
        max_output_tokens=current.max_output_tokens,
        output_schema=current.output_schema,
        knowledge_base_ids=[UUID(value) for value in current.knowledge_base_ids_snapshot],
    )
    return create_agent(session, workspace_id=workspace_id, payload=clone_payload)


def disable_agent(session: Session, *, workspace_id: UUID, agent_id: UUID) -> AgentResponse:
    agent = _get_agent(session, workspace_id=workspace_id, agent_id=agent_id)
    agent.status = "disabled"
    session.flush()
    session.refresh(agent)
    return agent_response(agent, _get_current_version(session, agent))


def run_agent_test(
    session: Session,
    *,
    workspace_id: UUID,
    agent_id: UUID,
    user_input: str,
    llm_client: object,
) -> AgentTestRunResult:
    agent = _get_agent(session, workspace_id=workspace_id, agent_id=agent_id)
    version = _get_current_version(session, agent)
    if version is None:
        raise AgentNotFoundError("Agent has no current version")

    messages = [
        {"role": "system", "content": f"{version.role_prompt}\n\n{version.system_prompt}"},
        {"role": "user", "content": user_input},
    ]
    started = perf_counter()

    try:
        completion = llm_client.complete(
            messages=messages,
            model=version.model_name,
            temperature=float(version.temperature),
            max_output_tokens=version.max_output_tokens,
        )
    except LLMProviderError as exc:
        latency_ms = _elapsed_ms(started)
        message = sanitize_provider_error(str(exc))
        call = _log_llm_call(
            session,
            workspace_id=workspace_id,
            agent=agent,
            version=version,
            status="failed",
            latency_ms=latency_ms,
            error_message=message,
        )
        return AgentTestRunResult(error_message=message, response=None)

    latency_ms = _elapsed_ms(started)
    call = _log_llm_call(
        session,
        workspace_id=workspace_id,
        agent=agent,
        version=version,
        status="succeeded",
        latency_ms=latency_ms,
        prompt_tokens=completion.prompt_tokens,
        completion_tokens=completion.completion_tokens,
        total_tokens=completion.total_tokens,
    )
    return AgentTestRunResult(
        response=AgentTestRunResponse(output=completion.content, llm_call=llm_call_response(call))
    )


def _create_version(
    session: Session,
    *,
    workspace_id: UUID,
    agent_id: UUID,
    version_number: int,
    payload: AgentVersionCreate,
) -> AgentVersion:
    try:
        knowledge_bases.validate_knowledge_base_ids(
            session,
            workspace_id=workspace_id,
            knowledge_base_ids=payload.knowledge_base_ids,
        )
    except knowledge_bases.KnowledgeBaseNotFoundError as exc:
        raise AgentValidationError(str(exc)) from exc

    version = AgentVersion(
        agent_id=agent_id,
        version_number=version_number,
        role_prompt=payload.role_prompt,
        system_prompt=payload.system_prompt,
        model_provider=payload.model_provider,
        model_name=payload.model_name,
        temperature=payload.temperature,
        max_output_tokens=payload.max_output_tokens,
        output_schema=payload.output_schema,
        tool_ids_snapshot=[],
        knowledge_base_ids_snapshot=[str(knowledge_base_id) for knowledge_base_id in payload.knowledge_base_ids],
        status="published",
    )
    session.add(version)
    session.flush()
    return version


def _get_agent(session: Session, *, workspace_id: UUID, agent_id: UUID) -> Agent:
    agent = session.scalar(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.workspace_id == workspace_id,
        )
    )
    if agent is None:
        raise AgentNotFoundError("Agent not found")
    return agent


def _get_current_version(session: Session, agent: Agent) -> AgentVersion | None:
    if agent.current_version_id is None:
        return None
    return session.get(AgentVersion, agent.current_version_id)


def _current_versions_by_agent_id(session: Session, agents: list[Agent]) -> dict[UUID, AgentVersion]:
    version_ids = [agent.current_version_id for agent in agents if agent.current_version_id is not None]
    if not version_ids:
        return {}
    versions = list(session.scalars(select(AgentVersion).where(AgentVersion.id.in_(version_ids))))
    return {version.agent_id: version for version in versions}


def _log_llm_call(
    session: Session,
    *,
    workspace_id: UUID,
    agent: Agent,
    version: AgentVersion,
    status: str,
    latency_ms: int,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
    error_message: str | None = None,
) -> LLMCall:
    call = LLMCall(
        workspace_id=workspace_id,
        agent_id=agent.id,
        agent_version_id=version.id,
        provider=version.model_provider,
        model=version.model_name,
        status=status,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        latency_ms=latency_ms,
        error_message=error_message,
    )
    session.add(call)
    session.flush()
    session.refresh(call)
    return call


def agent_response(agent: Agent, current_version: AgentVersion | None) -> AgentResponse:
    return AgentResponse(
        id=agent.id,
        workspace_id=agent.workspace_id,
        name=agent.name,
        description=agent.description,
        status=agent.status,
        current_version_id=agent.current_version_id,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
        current_version=version_response(current_version) if current_version is not None else None,
    )


def version_response(version: AgentVersion) -> AgentVersionResponse:
    return AgentVersionResponse(
        id=version.id,
        agent_id=version.agent_id,
        version_number=version.version_number,
        role_prompt=version.role_prompt,
        system_prompt=version.system_prompt,
        model_provider=version.model_provider,
        model_name=version.model_name,
        temperature=float(version.temperature),
        max_output_tokens=version.max_output_tokens,
        output_schema=version.output_schema,
        knowledge_base_ids_snapshot=version.knowledge_base_ids_snapshot,
        status=version.status,
        published_at=version.published_at,
    )


def llm_call_response(call: LLMCall) -> LLMCallResponse:
    return LLMCallResponse.model_validate(call)


def _elapsed_ms(started: float) -> int:
    return max(0, round((perf_counter() - started) * 1000))
