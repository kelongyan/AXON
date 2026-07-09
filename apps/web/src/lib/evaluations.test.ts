import { describe, expect, it } from "vitest";

import { buildEvaluationPayload, parseEvaluationCases, summarizeEvaluationResults } from "./evaluations";

describe("evaluation helpers", () => {
  it("parses evaluation case JSON arrays", () => {
    expect(parseEvaluationCases('[{"name":"A","input":{"topic":"AgentFlow"},"expected":{}}]')).toEqual([
      { name: "A", input: { topic: "AgentFlow" }, expected: {} },
    ]);
  });

  it("rejects non-array evaluation cases", () => {
    expect(() => parseEvaluationCases('{"name":"A"}')).toThrow("Evaluation cases must be a JSON array");
  });

  it("builds a trimmed evaluation payload", () => {
    expect(
      buildEvaluationPayload({
        name: "  Smoke Eval  ",
        description: "  Batch check  ",
        workflowId: "workflow-1",
        tokenPricePer1k: "0.002",
        casesText: '[{"name":"A","input":{"topic":"AgentFlow"},"expected":{}}]',
      }),
    ).toEqual({
      name: "Smoke Eval",
      description: "Batch check",
      workflow_id: "workflow-1",
      settings: { token_price_per_1k: 0.002 },
      cases: [{ name: "A", input: { topic: "AgentFlow" }, expected: {} }],
    });
  });

  it("summarizes result collections", () => {
    expect(
      summarizeEvaluationResults([
        { status: "succeeded", total_tokens: 12, latency_ms: 50 },
        { status: "failed", total_tokens: 0, latency_ms: 25 },
      ]),
    ).toEqual({ successCount: 1, failureCount: 1, totalTokens: 12, averageLatencyMs: 38 });
  });
});
