import { describe, expect, it } from "vitest";

import {
  buildApprovalBuilderNode,
  buildDefaultBuilderGraph,
  buildRetrievalBuilderNode,
  builderGraphToWorkflowGraph,
  mapRunStepsToNodeStatus,
} from "./workflow-builder";

describe("workflow builder helpers", () => {
  it("builds a default visual graph from an Agent Version", () => {
    const graph = buildDefaultBuilderGraph("agent-version-1");

    expect(graph.nodes.map((node) => node.type)).toEqual(["workflowNode", "workflowNode", "workflowNode"]);
    expect(graph.nodes.map((node) => node.data.nodeType)).toEqual(["start", "agent", "end"]);
    expect(graph.nodes[1].data.config.agent_version_id).toBe("agent-version-1");
    expect(graph.edges).toHaveLength(2);
  });

  it("adds a configured retrieval node for the builder palette", () => {
    const node = buildRetrievalBuilderNode({ id: "node_retrieval", knowledgeBaseIds: ["kb-1"], x: 260, y: 80 });

    expect(node.data.nodeType).toBe("retrieval");
    expect(node.data.config.knowledge_base_ids).toEqual(["kb-1"]);
    expect(node.data.input_mapping).toEqual({ query: "$.run.input.topic" });
  });

  it("adds a configured approval node for the builder palette", () => {
    const node = buildApprovalBuilderNode({ id: "node_approval", x: 300, y: 160 });

    expect(node.data.nodeType).toBe("approval");
    expect(node.data.config).toMatchObject({
      title: "Human Review",
      instructions: "Approve this run before the next node executes.",
      risk_level: "medium",
    });
    expect(node.data.input_mapping).toEqual({
      topic: "$.run.input.topic",
      audience: "$.run.input.audience",
    });
  });

  it("converts builder nodes and edges into workflow graph JSON", () => {
    const graph = buildDefaultBuilderGraph("agent-version-1");
    const workflowGraph = builderGraphToWorkflowGraph(graph.nodes, graph.edges);

    expect(workflowGraph.schema_version).toBe("1.0");
    expect(workflowGraph.nodes[0]).toMatchObject({
      id: "node_start",
      type: "start",
      name: "Start",
      position: { x: 40, y: 120 },
    });
    expect(workflowGraph.nodes[1].config.agent_version_id).toBe("agent-version-1");
    expect(workflowGraph.edges[0]).toEqual({
      id: "edge_start_agent",
      source: "node_start",
      target: "node_agent",
      type: "default",
    });
  });

  it("maps run steps to node status badges", () => {
    const status = mapRunStepsToNodeStatus([
      { node_id: "node_start", status: "succeeded" },
      { node_id: "node_agent", status: "running" },
    ]);

    expect(status).toEqual({ node_start: "succeeded", node_agent: "running" });
  });
});
