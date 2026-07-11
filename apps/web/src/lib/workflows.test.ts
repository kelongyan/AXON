import { afterEach, describe, expect, it, vi } from "vitest";

import {
  buildDefaultWorkflowGraph,
  buildWorkflowPayload,
  canCancelRunStatus,
  cancelRun,
  formatRunCostSummary,
  formatRunRuntimeSummary,
  parseRunInput,
  parseWorkflowGraph,
  shouldPollRunStatus,
} from "./workflows";

describe("workflow helpers", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

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

  it("formats run worker runtime observability", () => {
    expect(
      formatRunRuntimeSummary({
        worker_id: "worker-a",
        lease_expires_at: "2026-07-11T12:00:00Z",
        current_node_id: "node_tool",
      }),
    ).toEqual({
      worker: "worker-a",
      leaseExpiresAt: "2026-07-11T12:00:00Z",
      checkpoint: "node_tool",
    });

    expect(
      formatRunRuntimeSummary({
        worker_id: null,
        lease_expires_at: null,
        current_node_id: null,
      }),
    ).toEqual({
      worker: "Unclaimed",
      leaseExpiresAt: "No active lease",
      checkpoint: "None",
    });
  });

  it("identifies active worker-backed run statuses for polling", () => {
    expect(shouldPollRunStatus("queued")).toBe(true);
    expect(shouldPollRunStatus("running")).toBe(true);
    expect(shouldPollRunStatus("waiting_approval")).toBe(false);
    expect(shouldPollRunStatus("succeeded")).toBe(false);
    expect(shouldPollRunStatus("failed")).toBe(false);
  });

  it("identifies run statuses that can be cancelled", () => {
    expect(canCancelRunStatus("queued")).toBe(true);
    expect(canCancelRunStatus("waiting_approval")).toBe(true);
    expect(canCancelRunStatus("running")).toBe(false);
    expect(canCancelRunStatus("succeeded")).toBe(false);
    expect(canCancelRunStatus("failed")).toBe(false);
    expect(canCancelRunStatus("cancelled")).toBe(false);
  });

  it("sends run cancellation requests with a comment", async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ id: "run-1", status: "cancelled" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await cancelRun("run-1", "No longer needed.");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/runs/run-1/cancel",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ comment: "No longer needed." }),
      }),
    );
  });
});
