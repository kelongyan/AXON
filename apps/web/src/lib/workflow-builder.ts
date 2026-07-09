import type { WorkflowEdge, WorkflowGraph, WorkflowNode } from "./workflows";

export type BuilderNodeType = "start" | "agent" | "retrieval" | "end" | "tool" | "condition" | "approval";

export type BuilderNodeData = {
  label: string;
  nodeType: BuilderNodeType;
  description?: string;
  config: Record<string, unknown>;
  input_mapping?: Record<string, unknown>;
  output_schema?: Record<string, unknown>;
  status?: string;
};

export type BuilderNode = {
  id: string;
  type: "workflowNode";
  position: { x: number; y: number };
  data: BuilderNodeData;
};

export type BuilderEdge = {
  id: string;
  source: string;
  target: string;
  type?: string;
  animated?: boolean;
};

export type BuilderGraph = {
  nodes: BuilderNode[];
  edges: BuilderEdge[];
};

export type RunStepLike = {
  node_id: string;
  status: string;
};

export function buildDefaultBuilderGraph(agentVersionId: string): BuilderGraph {
  return {
    nodes: [
      buildStartBuilderNode({ id: "node_start", x: 40, y: 120 }),
      buildAgentBuilderNode({ id: "node_agent", agentVersionId, x: 360, y: 120 }),
      buildEndBuilderNode({ id: "node_end", x: 680, y: 120 }),
    ],
    edges: [
      { id: "edge_start_agent", source: "node_start", target: "node_agent", type: "default" },
      { id: "edge_agent_end", source: "node_agent", target: "node_end", type: "default" },
    ],
  };
}

export function buildStartBuilderNode({ id, x, y }: { id: string; x: number; y: number }): BuilderNode {
  return {
    id,
    type: "workflowNode",
    position: { x, y },
    data: {
      label: "Start",
      nodeType: "start",
      config: {
        input_schema: {
          type: "object",
          required: ["topic"],
          properties: {
            topic: { type: "string" },
            audience: { type: "string" },
            max_words: { type: "integer" },
          },
        },
      },
    },
  };
}

export function buildAgentBuilderNode({
  agentVersionId,
  id,
  x,
  y,
}: {
  agentVersionId: string;
  id: string;
  x: number;
  y: number;
}): BuilderNode {
  return {
    id,
    type: "workflowNode",
    position: { x, y },
    data: {
      label: "Agent",
      nodeType: "agent",
      config: {
        agent_version_id: agentVersionId,
        instruction: "Use the input to produce a concise Markdown-ready result.",
      },
      input_mapping: {
        topic: "$.run.input.topic",
        audience: "$.run.input.audience",
        max_words: "$.run.input.max_words",
      },
    },
  };
}

export function buildRetrievalBuilderNode({
  id,
  knowledgeBaseIds,
  x,
  y,
}: {
  id: string;
  knowledgeBaseIds: string[];
  x: number;
  y: number;
}): BuilderNode {
  return {
    id,
    type: "workflowNode",
    position: { x, y },
    data: {
      label: "Retrieval",
      nodeType: "retrieval",
      config: {
        knowledge_base_ids: knowledgeBaseIds,
        top_k: 5,
      },
      input_mapping: { query: "$.run.input.topic" },
    },
  };
}

export function buildApprovalBuilderNode({ id, x, y }: { id: string; x: number; y: number }): BuilderNode {
  return {
    id,
    type: "workflowNode",
    position: { x, y },
    data: {
      label: "Human Review",
      nodeType: "approval",
      config: {
        title: "Human Review",
        instructions: "Approve this run before the next node executes.",
        risk_level: "medium",
      },
      input_mapping: {
        topic: "$.run.input.topic",
        audience: "$.run.input.audience",
      },
    },
  };
}

export function buildEndBuilderNode({ id, x, y }: { id: string; x: number; y: number }): BuilderNode {
  return {
    id,
    type: "workflowNode",
    position: { x, y },
    data: {
      label: "End",
      nodeType: "end",
      config: {
        output_mapping: {
          markdown: "$.steps.node_agent.output.content",
          citations: "$.steps.node_retrieval.output.citations",
        },
      },
    },
  };
}

export function builderGraphToWorkflowGraph(nodes: BuilderNode[], edges: BuilderEdge[]): WorkflowGraph {
  return {
    schema_version: "1.0",
    nodes: nodes.map(builderNodeToWorkflowNode),
    edges: edges.map(builderEdgeToWorkflowEdge),
    variables: {},
    settings: {},
  };
}

export function workflowGraphToBuilderGraph(graph: WorkflowGraph): BuilderGraph {
  return {
    nodes: graph.nodes.map((node, index) => ({
      id: node.id,
      type: "workflowNode",
      position: node.position ?? { x: 40 + index * 300, y: 120 },
      data: {
        label: node.name,
        nodeType: coerceBuilderNodeType(node.type),
        description: node.description,
        config: node.config ?? {},
        input_mapping: node.input_mapping,
        output_schema: node.output_schema,
      },
    })),
    edges: graph.edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      type: edge.type,
    })),
  };
}

export function mapRunStepsToNodeStatus(steps: RunStepLike[]): Record<string, string> {
  return Object.fromEntries(steps.map((step) => [step.node_id, step.status]));
}

export function applyNodeStatuses(nodes: BuilderNode[], statuses: Record<string, string>): BuilderNode[] {
  return nodes.map((node) => ({
    ...node,
    data: { ...node.data, status: statuses[node.id] },
  }));
}

function builderNodeToWorkflowNode(node: BuilderNode): WorkflowNode {
  return {
    id: node.id,
    type: node.data.nodeType,
    name: node.data.label,
    description: node.data.description,
    position: node.position,
    config: node.data.config,
    input_mapping: node.data.input_mapping,
    output_schema: node.data.output_schema,
  };
}

function builderEdgeToWorkflowEdge(edge: BuilderEdge): WorkflowEdge {
  return {
    id: edge.id,
    source: edge.source,
    target: edge.target,
    type: edge.type ?? "default",
  };
}

function coerceBuilderNodeType(type: string): BuilderNodeType {
  if (["start", "agent", "retrieval", "end", "tool", "condition", "approval"].includes(type)) {
    return type as BuilderNodeType;
  }
  return "agent";
}
