from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Agent, AgentVersion, Tool
from app.services import knowledge_bases

from .errors import (
    EXECUTABLE_PHASE6_NODE_TYPES,
    PLANNED_VISUAL_NODE_TYPES,
    WorkflowValidationError,
)


def validate_phase3_graph(
    session: Session,
    *,
    workspace_id: UUID,
    graph: dict[str, Any],
) -> dict[str, Any]:
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise WorkflowValidationError("Graph must contain nodes and edges arrays")
    if not nodes:
        raise WorkflowValidationError("Graph must contain at least one node")

    node_ids = [node.get("id") for node in nodes if isinstance(node, dict)]
    if len(node_ids) != len(nodes) or any(not isinstance(node_id, str) or not node_id for node_id in node_ids):
        raise WorkflowValidationError("Every node requires a string id")
    if len(set(node_ids)) != len(node_ids):
        raise WorkflowValidationError("Node ids must be unique")

    start_nodes = [node for node in nodes if isinstance(node, dict) and node.get("type") == "start"]
    if len(start_nodes) != 1:
        raise WorkflowValidationError("Graph must contain exactly one start node")

    end_nodes = [node for node in nodes if isinstance(node, dict) and node.get("type") == "end"]
    if not end_nodes:
        raise WorkflowValidationError("Graph must contain at least one end node")

    for node in nodes:
        if not isinstance(node, dict):
            raise WorkflowValidationError("Each node must be an object")
        node_type = node.get("type")
        if node_type in PLANNED_VISUAL_NODE_TYPES:
            raise WorkflowValidationError(f"Node type is planned but not executable in Phase 6 MVP: {node_type}")
        if node_type not in EXECUTABLE_PHASE6_NODE_TYPES:
            raise WorkflowValidationError(f"Node type is not supported in Phase 6 MVP: {node_type}")
        if not isinstance(node.get("name"), str) or not node["name"]:
            raise WorkflowValidationError("Every node requires a name")
        if node_type == "approval":
            config = _node_config(node)
            title = str(config.get("title") or node["name"] or "").strip()
            instructions = str(config.get("instructions") or "").strip()
            if not title and not instructions:
                raise WorkflowValidationError("Approval node requires title or instructions")

    edge_ids = [edge.get("id") for edge in edges if isinstance(edge, dict)]
    if len(edge_ids) != len(edges) or any(not isinstance(edge_id, str) or not edge_id for edge_id in edge_ids):
        raise WorkflowValidationError("Every edge requires a string id")
    if len(set(edge_ids)) != len(edge_ids):
        raise WorkflowValidationError("Edge ids must be unique")

    valid_node_ids = set(node_ids)
    for edge in edges:
        if not isinstance(edge, dict):
            raise WorkflowValidationError("Each edge must be an object")
        if edge.get("source") not in valid_node_ids or edge.get("target") not in valid_node_ids:
            raise WorkflowValidationError("Every edge source and target must reference existing nodes")

    sequence = execution_sequence(graph)
    if sequence[0].get("type") != "start" or sequence[-1].get("type") != "end":
        raise WorkflowValidationError("Phase 6 MVP graph must execute from start to end")
    if len(sequence) != len(nodes):
        raise WorkflowValidationError("Phase 6 MVP graph must be a single reachable sequential path")

    referenced_agent_versions: list[str] = []
    referenced_tool_versions: list[dict[str, Any]] = []
    node_snapshots: dict[str, Any] = {}
    for node in sequence:
        if node.get("type") != "agent":
            if node.get("type") == "retrieval":
                knowledge_base_ids = _coerce_uuid_list(
                    _node_config(node).get("knowledge_base_ids"),
                    "Retrieval node requires knowledge_base_ids",
                )
                if not knowledge_base_ids:
                    raise WorkflowValidationError("Retrieval node requires knowledge_base_ids")
                try:
                    knowledge_bases.validate_knowledge_base_ids(
                        session,
                        workspace_id=workspace_id,
                        knowledge_base_ids=knowledge_base_ids,
                    )
                except knowledge_bases.KnowledgeBaseNotFoundError as exc:
                    raise WorkflowValidationError(str(exc)) from exc
                top_k = _node_config(node).get("top_k", 5)
                if not isinstance(top_k, int) or top_k < 1 or top_k > 20:
                    raise WorkflowValidationError("Retrieval node top_k must be between 1 and 20")
                node_snapshots[str(node["id"])] = {
                    "knowledge_base_ids": [str(knowledge_base_id) for knowledge_base_id in knowledge_base_ids],
                    "top_k": top_k,
                }
            elif node.get("type") == "approval":
                config = _node_config(node)
                node_snapshots[str(node["id"])] = {
                    "title": str(config.get("title") or node["name"]),
                    "risk_level": str(config.get("risk_level") or "medium"),
                }
            elif node.get("type") == "tool":
                config = _node_config(node)
                agent_id = _coerce_uuid(config.get("agent_id"), "Tool node requires agent_id")
                tool_id = _coerce_uuid(config.get("tool_id"), "Tool node requires tool_id")
                agent = session.scalar(
                    select(Agent).where(Agent.id == agent_id, Agent.workspace_id == workspace_id)
                )
                if agent is None:
                    raise WorkflowValidationError("Tool node must reference an Agent in this workspace")
                tool = session.scalar(
                    select(Tool).where(Tool.id == tool_id, Tool.workspace_id == workspace_id)
                )
                if tool is None:
                    raise WorkflowValidationError("Tool node must reference a Tool in this workspace")
                snapshot = {
                    "agent_id": str(agent.id),
                    "tool_id": str(tool.id),
                    "tool_name": tool.name,
                    "version": tool.version,
                    "risk_level": tool.risk_level,
                    "requires_approval": tool.requires_approval,
                }
                node_snapshots[str(node["id"])] = snapshot
                referenced_tool_versions.append(snapshot)
            continue
        version_id = _coerce_uuid(_node_config(node).get("agent_version_id"), "Agent node requires agent_version_id")
        agent_version = session.scalar(
            select(AgentVersion)
            .join(Agent, AgentVersion.agent_id == Agent.id)
            .where(
                AgentVersion.id == version_id,
                Agent.workspace_id == workspace_id,
                AgentVersion.status == "published",
            )
        )
        if agent_version is None:
            raise WorkflowValidationError("Agent node must reference a published Agent Version")
        referenced_agent_versions.append(str(agent_version.id))
        node_snapshots[str(node["id"])] = {
            "agent_id": str(agent_version.agent_id),
            "agent_version_id": str(agent_version.id),
            "version_number": agent_version.version_number,
            "model_provider": agent_version.model_provider,
            "model_name": agent_version.model_name,
            "knowledge_base_ids": agent_version.knowledge_base_ids_snapshot,
        }

    return {
        "referenced_agent_versions": referenced_agent_versions,
        "referenced_tool_versions": referenced_tool_versions,
        "node_snapshots": node_snapshots,
    }


def execution_sequence(graph: dict[str, Any]) -> list[dict[str, Any]]:
    nodes_by_id = _nodes_by_id(graph)
    edges = graph.get("edges", [])
    if not isinstance(edges, list):
        raise WorkflowValidationError("Graph edges must be an array")
    outgoing: dict[str, list[str]] = {}
    for edge in edges:
        if not isinstance(edge, dict):
            raise WorkflowValidationError("Each edge must be an object")
        source = edge.get("source")
        target = edge.get("target")
        if isinstance(source, str) and isinstance(target, str):
            outgoing.setdefault(source, []).append(target)

    current = _start_node_id(graph)
    visited: set[str] = set()
    sequence: list[dict[str, Any]] = []
    while True:
        if current in visited:
            raise WorkflowValidationError("Phase 6 MVP graph cannot contain cycles")
        visited.add(current)
        node = nodes_by_id[current]
        sequence.append(node)
        if node.get("type") == "end":
            return sequence
        targets = outgoing.get(current, [])
        if len(targets) != 1:
            raise WorkflowValidationError("Phase 6 MVP nodes must have exactly one default outgoing edge")
        current = targets[0]
        if current not in nodes_by_id:
            raise WorkflowValidationError("Every edge target must reference an existing node")




def _nodes_by_id(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    nodes = graph.get("nodes", [])
    if not isinstance(nodes, list):
        raise WorkflowValidationError("Graph nodes must be an array")
    return {str(node["id"]): node for node in nodes if isinstance(node, dict) and "id" in node}


def _start_node_id(graph: dict[str, Any]) -> str:
    starts = [
        str(node["id"])
        for node in graph.get("nodes", [])
        if isinstance(node, dict) and node.get("type") == "start" and "id" in node
    ]
    if len(starts) != 1:
        raise WorkflowValidationError("Graph must contain exactly one start node")
    return starts[0]


def _node_config(node: dict[str, Any]) -> dict[str, Any]:
    config = node.get("config")
    return config if isinstance(config, dict) else {}


def _coerce_uuid(value: object, message: str) -> UUID:
    try:
        return UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise WorkflowValidationError(message) from exc


def _coerce_uuid_list(value: object, message: str) -> list[UUID]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise WorkflowValidationError(message)
    try:
        return [UUID(str(item)) for item in value]
    except (TypeError, ValueError) as exc:
        raise WorkflowValidationError(message) from exc


