from dataclasses import dataclass
from time import perf_counter
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Agent, AgentTool, Tool, ToolCall
from app.schemas.tools import (
    AgentToolResponse,
    ToolCallResponse,
    ToolCreate,
    ToolResponse,
)

APPROVAL_RISK_LEVELS = {"external_effect", "sensitive_data", "destructive", "high_cost"}
SENSITIVE_FIELD_NAMES = {
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "set-cookie",
    "private_key",
    "access_key",
    "refresh_token",
}


class ToolValidationError(ValueError):
    pass


class ToolNotFoundError(LookupError):
    pass


class ToolAgentNotFoundError(LookupError):
    pass


@dataclass(frozen=True)
class ToolExecutionRejected(Exception):
    status_code: int
    detail: str
    tool_call: ToolCall | None = None


BUILT_IN_TOOLS: list[ToolCreate] = [
    ToolCreate(
        name="web_search",
        display_name="Web Search",
        description="Search public web pages. Execution is reserved for a later connector.",
        risk_level="read_only",
        input_schema={
            "type": "object",
            "required": ["query"],
            "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}},
        },
        output_schema={"type": "object"},
        timeout_seconds=20,
        requires_approval=False,
    ),
    ToolCreate(
        name="http_request",
        display_name="HTTP Request",
        description="Call an allowlisted external HTTP endpoint. Blocked pending approval workflow.",
        risk_level="external_effect",
        input_schema={
            "type": "object",
            "required": ["method", "url"],
            "properties": {
                "method": {"type": "string"},
                "url": {"type": "string"},
                "headers": {"type": "object"},
                "body": {"type": "object"},
            },
        },
        output_schema={"type": "object"},
        timeout_seconds=30,
        requires_approval=True,
    ),
    ToolCreate(
        name="document_parse",
        display_name="Document Parse",
        description="Parse uploaded documents. Handler is reserved for the Knowledge Base phase.",
        risk_level="low_write",
        input_schema={
            "type": "object",
            "required": ["object_key"],
            "properties": {"object_key": {"type": "string"}, "content_type": {"type": "string"}},
        },
        output_schema={"type": "object"},
        timeout_seconds=60,
        requires_approval=False,
    ),
    ToolCreate(
        name="code_runner",
        display_name="Code Runner",
        description="Run code in an isolated sandbox. Blocked until sandbox and approval are implemented.",
        risk_level="high_cost",
        input_schema={
            "type": "object",
            "required": ["language", "code"],
            "properties": {"language": {"type": "string"}, "code": {"type": "string"}},
        },
        output_schema={"type": "object"},
        timeout_seconds=30,
        requires_approval=True,
    ),
    ToolCreate(
        name="database_query",
        display_name="Database Query",
        description="Run controlled read-only SQL. Blocked pending approval and SQL policy.",
        risk_level="sensitive_data",
        input_schema={
            "type": "object",
            "required": ["query"],
            "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}},
        },
        output_schema={"type": "object"},
        timeout_seconds=20,
        requires_approval=True,
    ),
    ToolCreate(
        name="file_artifact_create",
        display_name="File Artifact Create",
        description="Create an internal file artifact. Handler is reserved for artifact storage.",
        risk_level="low_write",
        input_schema={
            "type": "object",
            "required": ["filename", "content"],
            "properties": {"filename": {"type": "string"}, "content": {"type": "string"}},
        },
        output_schema={"type": "object"},
        timeout_seconds=20,
        requires_approval=False,
    ),
    ToolCreate(
        name="json_transform",
        display_name="JSON Transform",
        description="Select fields from a JSON object and return a new object.",
        risk_level="low_write",
        input_schema={
            "type": "object",
            "required": ["data", "select_keys"],
            "properties": {"data": {"type": "object"}, "select_keys": {"type": "array"}},
        },
        output_schema={"type": "object"},
        timeout_seconds=10,
        requires_approval=False,
    ),
    ToolCreate(
        name="markdown_report_generate",
        display_name="Markdown Report Generate",
        description="Generate a Markdown report from title and sections.",
        risk_level="low_write",
        input_schema={
            "type": "object",
            "required": ["title", "sections"],
            "properties": {"title": {"type": "string"}, "sections": {"type": "array"}},
        },
        output_schema={"type": "object"},
        timeout_seconds=10,
        requires_approval=False,
    ),
]


def seed_built_in_tools(session: Session, *, workspace_id: UUID) -> tuple[int, int, list[ToolResponse]]:
    created = 0
    updated = 0
    items: list[ToolResponse] = []
    for definition in BUILT_IN_TOOLS:
        tool = session.scalar(
            select(Tool).where(Tool.workspace_id == workspace_id, Tool.name == definition.name)
        )
        if tool is None:
            tool = Tool(workspace_id=workspace_id, **definition.model_dump())
            session.add(tool)
            created += 1
        else:
            for field, value in definition.model_dump().items():
                setattr(tool, field, value)
            updated += 1
        session.flush()
        session.refresh(tool)
        items.append(tool_response(tool))
    return created, updated, items


def create_tool(session: Session, *, workspace_id: UUID, payload: ToolCreate) -> ToolResponse:
    tool = Tool(workspace_id=workspace_id, **payload.model_dump())
    session.add(tool)
    session.flush()
    session.refresh(tool)
    return tool_response(tool)


def list_tools(session: Session, *, workspace_id: UUID) -> list[ToolResponse]:
    tools = list(
        session.scalars(
            select(Tool).where(Tool.workspace_id == workspace_id).order_by(Tool.name.asc())
        )
    )
    return [tool_response(tool) for tool in tools]


def get_tool(session: Session, *, workspace_id: UUID, tool_id: UUID) -> Tool:
    tool = session.scalar(select(Tool).where(Tool.id == tool_id, Tool.workspace_id == workspace_id))
    if tool is None:
        raise ToolNotFoundError("Tool not found")
    return tool


def set_tool_status(session: Session, *, workspace_id: UUID, tool_id: UUID, status: str) -> ToolResponse:
    tool = get_tool(session, workspace_id=workspace_id, tool_id=tool_id)
    tool.status = status
    session.flush()
    session.refresh(tool)
    return tool_response(tool)


def grant_tool_to_agent(
    session: Session,
    *,
    workspace_id: UUID,
    agent_id: UUID,
    tool_id: UUID,
    granted_by: UUID,
    policy: dict[str, Any] | None = None,
) -> AgentToolResponse:
    agent = _get_agent(session, workspace_id=workspace_id, agent_id=agent_id)
    tool = get_tool(session, workspace_id=workspace_id, tool_id=tool_id)
    grant = session.scalar(
        select(AgentTool).where(AgentTool.agent_id == agent.id, AgentTool.tool_id == tool.id)
    )
    if grant is None:
        grant = AgentTool(
            agent_id=agent.id,
            tool_id=tool.id,
            granted_by=granted_by,
            policy=policy or {},
        )
        session.add(grant)
    else:
        grant.granted_by = granted_by
        grant.policy = policy or {}
    session.flush()
    session.refresh(grant)
    return agent_tool_response(grant)


def revoke_tool_from_agent(session: Session, *, workspace_id: UUID, agent_id: UUID, tool_id: UUID) -> None:
    agent = _get_agent(session, workspace_id=workspace_id, agent_id=agent_id)
    tool = get_tool(session, workspace_id=workspace_id, tool_id=tool_id)
    grant = session.scalar(
        select(AgentTool).where(AgentTool.agent_id == agent.id, AgentTool.tool_id == tool.id)
    )
    if grant is not None:
        session.delete(grant)
        session.flush()


def invoke_tool(
    session: Session,
    *,
    workspace_id: UUID,
    tool_id: UUID,
    agent_id: UUID,
    tool_input: dict[str, Any],
) -> tuple[dict[str, Any], ToolCall]:
    tool = get_tool(session, workspace_id=workspace_id, tool_id=tool_id)
    agent = _get_agent(session, workspace_id=workspace_id, agent_id=agent_id)
    started = perf_counter()

    if tool.status != "active":
        call = _log_tool_call(
            session,
            workspace_id=workspace_id,
            agent_id=agent.id,
            tool=tool,
            status="blocked",
            started=started,
            tool_input=tool_input,
            error_message="Tool is disabled",
        )
        raise ToolExecutionRejected(status_code=409, detail="Tool is disabled", tool_call=call)

    grant = session.scalar(
        select(AgentTool).where(AgentTool.agent_id == agent.id, AgentTool.tool_id == tool.id)
    )
    if grant is None:
        call = _log_tool_call(
            session,
            workspace_id=workspace_id,
            agent_id=agent.id,
            tool=tool,
            status="blocked",
            started=started,
            tool_input=tool_input,
            error_message="Agent is not authorized to use this tool",
        )
        raise ToolExecutionRejected(
            status_code=403,
            detail="Agent is not authorized to use this tool",
            tool_call=call,
        )

    try:
        validate_input_schema(tool.input_schema, tool_input)
    except ToolValidationError as exc:
        call = _log_tool_call(
            session,
            workspace_id=workspace_id,
            agent_id=agent.id,
            tool=tool,
            status="failed",
            started=started,
            tool_input=tool_input,
            error_message=str(exc),
        )
        raise ToolExecutionRejected(status_code=422, detail=str(exc), tool_call=call) from exc

    if tool.requires_approval or tool.risk_level in APPROVAL_RISK_LEVELS:
        call = _log_tool_call(
            session,
            workspace_id=workspace_id,
            agent_id=agent.id,
            tool=tool,
            status="blocked",
            started=started,
            tool_input=tool_input,
            error_message="Tool requires approval before execution",
        )
        raise ToolExecutionRejected(
            status_code=409,
            detail="Tool requires approval before execution",
            tool_call=call,
        )

    try:
        output = execute_builtin_tool(tool.name, tool_input)
    except ToolValidationError as exc:
        call = _log_tool_call(
            session,
            workspace_id=workspace_id,
            agent_id=agent.id,
            tool=tool,
            status="failed",
            started=started,
            tool_input=tool_input,
            error_message=str(exc),
        )
        raise ToolExecutionRejected(status_code=422, detail=str(exc), tool_call=call) from exc

    call = _log_tool_call(
        session,
        workspace_id=workspace_id,
        agent_id=agent.id,
        tool=tool,
        status="succeeded",
        started=started,
        tool_input=tool_input,
        output_summary=redact_mapping(output),
    )
    return output, call


def list_tool_calls(session: Session, *, workspace_id: UUID, limit: int = 50) -> list[ToolCallResponse]:
    calls = list(
        session.scalars(
            select(ToolCall)
            .where(ToolCall.workspace_id == workspace_id)
            .order_by(ToolCall.created_at.desc())
            .limit(limit)
        )
    )
    return [tool_call_response(call) for call in calls]


def validate_input_schema(schema: dict[str, Any], value: dict[str, Any]) -> None:
    if schema.get("type", "object") != "object":
        raise ToolValidationError("Input schema root must be object")
    required = schema.get("required", [])
    if isinstance(required, list):
        for field in required:
            if isinstance(field, str) and field not in value:
                raise ToolValidationError(f"Missing required field: {field}")

    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        return

    for field, definition in properties.items():
        if field not in value or not isinstance(definition, dict):
            continue
        expected_type = definition.get("type")
        if expected_type is None:
            continue
        if not _matches_json_type(value[field], expected_type):
            raise ToolValidationError(f"{field} must be {expected_type}")


def execute_builtin_tool(name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
    if name == "json_transform":
        data = tool_input.get("data")
        select_keys = tool_input.get("select_keys")
        if not isinstance(data, dict) or not isinstance(select_keys, list):
            raise ToolValidationError("json_transform requires data object and select_keys array")
        result = {key: data[key] for key in select_keys if isinstance(key, str) and key in data}
        return {"result": result}

    if name == "markdown_report_generate":
        title = tool_input.get("title")
        sections = tool_input.get("sections")
        if not isinstance(title, str) or not isinstance(sections, list):
            raise ToolValidationError("markdown_report_generate requires title and sections")
        parts = [f"# {title.strip()}"]
        for section in sections:
            if not isinstance(section, dict):
                raise ToolValidationError("sections must contain objects")
            heading = str(section.get("heading", "")).strip()
            content = str(section.get("content", "")).strip()
            if not heading or not content:
                raise ToolValidationError("each section requires heading and content")
            parts.append(f"## {heading}\n\n{content}")
        return {"markdown": "\n\n".join(parts)}

    raise ToolValidationError(f"Tool handler is not implemented: {name}")


def redact_mapping(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if _is_sensitive_key(str(key)):
                redacted[str(key)] = "[REDACTED]"
            else:
                redacted[str(key)] = redact_mapping(item)
        return redacted
    if isinstance(value, list):
        return [redact_mapping(item) for item in value]
    return value


def tool_response(tool: Tool) -> ToolResponse:
    return ToolResponse.model_validate(tool)


def tool_call_response(call: ToolCall) -> ToolCallResponse:
    return ToolCallResponse.model_validate(call)


def agent_tool_response(grant: AgentTool) -> AgentToolResponse:
    return AgentToolResponse(
        agent_id=grant.agent_id,
        tool_id=grant.tool_id,
        granted_by=grant.granted_by,
        granted_at=grant.granted_at,
        policy=grant.policy,
    )


def _get_agent(session: Session, *, workspace_id: UUID, agent_id: UUID) -> Agent:
    agent = session.scalar(select(Agent).where(Agent.id == agent_id, Agent.workspace_id == workspace_id))
    if agent is None:
        raise ToolAgentNotFoundError("Agent not found")
    return agent


def _log_tool_call(
    session: Session,
    *,
    workspace_id: UUID,
    agent_id: UUID,
    tool: Tool,
    status: str,
    started: float,
    tool_input: dict[str, Any],
    output_summary: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> ToolCall:
    call = ToolCall(
        workspace_id=workspace_id,
        agent_id=agent_id,
        tool_id=tool.id,
        tool_name=tool.name,
        status=status,
        risk_level=tool.risk_level,
        input_summary=redact_mapping(tool_input),
        output_summary=output_summary,
        latency_ms=max(0, round((perf_counter() - started) * 1000)),
        error_message=error_message,
    )
    session.add(call)
    session.flush()
    session.refresh(call)
    return call


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return normalized in SENSITIVE_FIELD_NAMES


def _matches_json_type(value: Any, expected_type: Any) -> bool:
    if isinstance(expected_type, list):
        return any(_matches_json_type(value, item) for item in expected_type)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return (isinstance(value, int | float)) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "null":
        return value is None
    return True

