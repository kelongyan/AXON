import { describe, expect, it } from "vitest";

import {
  buildDefaultWorkflowGraph,
  buildWorkflowPayload,
  formatRunCostSummary,
  parseRunInput,
  parseWorkflowGraph,
  shouldPollRunStatus,
} from "./workflows";

describe("workflow helpers", () => {
  it("builds a trimmed workflow create payload", () => {
    expect(buildWorkflowPayload({ name: "  Report Flow  ", description: "  Draft reports  " })).toEqual({
      name: "Report Flow",
      description: "Draft reports",
    });
  });

  it("parses workflow graph JSON objects", () => {
    expect(parseWorkflowGraph('{"schema_version":"1.0","nodes":[],"edges":[]}')).toEqual({
      schema_version: "1.0",
      nodes: [],
      edges: [],
    });
  });

  it("rejects invalid workflow graph JSON", () => {
    expect(() => parseWorkflowGraph("{bad json")).toThrow("Workflow graph must be valid JSON");
    expect(() => parseWorkflowGraph("[1,2,3]")).toThrow("Workflow graph must be a JSON object");
  });

  it("parses run input JSON objects", () => {
    expect(parseRunInput('{"topic":"AgentFlow","audience":"CTO"}')).toEqual({
      topic: "AgentFlow",
      audience: "CTO",
    });
  });

  it("builds a default Start Agent End graph from an Agent Version", () => {
    const graph = buildDefaultWorkflowGraph("agent-version-1");

    expect(graph.nodes.map((node) => node.type)).toEqual(["start", "agent", "end"]);
    expect(graph.nodes[1].config.agent_version_id).toBe("agent-version-1");
    expect(graph.edges).toHaveLength(2);
  });

  it("formats run token and cost summaries", () => {
    expect(
      formatRunCostSummary({
        llm_calls: [
          { total_tokens: 10, prompt_tokens: 6, completion_tokens: 4, latency_ms: 120 },
          { total_tokens: 15, prompt_tokens: 8, completion_tokens: 7, latency_ms: 180 },
        ],
      }),
    ).toEqual({
      totalTokens: 25,
      promptTokens: 14,
      completionTokens: 11,
      totalLatencyMs: 300,
    });
  });

  it("identifies active worker-backed run statuses for polling", () => {
    expect(shouldPollRunStatus("queued")).toBe(true);
    expect(shouldPollRunStatus("running")).toBe(true);
    expect(shouldPollRunStatus("waiting_approval")).toBe(false);
    expect(shouldPollRunStatus("succeeded")).toBe(false);
    expect(shouldPollRunStatus("failed")).toBe(false);
  });
});
