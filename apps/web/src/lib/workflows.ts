import { apiRequest } from "./api-client";

export type WorkflowFormValues = {
  name: string;
  description: string;
};

export type WorkflowPayload = {
  name: string;
  description: string;
};

export type WorkflowNode = {
  id: string;
  type: "start" | "agent" | "end" | string;
  name: string;
  description?: string;
  position?: { x: number; y: number };
  config: Record<string, unknown>;
  input_mapping?: Record<string, unknown>;
  output_schema?: Record<string, unknown>;
};

export type WorkflowEdge = {
  id: string;
  source: string;
  target: string;
  type: string;
  condition?: unknown;
};

export type WorkflowGraph = {
  schema_version: string;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  variables?: Record<string, unknown>;
  settings?: Record<string, unknown>;
};

export type WorkflowVersion = {
  id: string;
  workflow_id: string;
  version_number: number;
  graph: WorkflowGraph;
  node_snapshots: Record<string, unknown>;
  referenced_agent_versions: string[];
  referenced_tool_versions: Array<Record<string, unknown>>;
  status: string;
  published_at: string;
};

export type Workflow = {
  id: string;
  workspace_id: string;
  name: string;
  description: string;
  status: string;
  current_version_id: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
  current_version: WorkflowVersion | null;
};

export type WorkflowDetail = Workflow & {
  versions: WorkflowVersion[];
};

export type RunStep = {
  id: string;
  workspace_id: string;
  run_id: string;
  node_id: string;
  node_type: string;
  node_name: string;
  status: string;
  attempt: number;
  input: Record<string, unknown>;
  output: Record<string, unknown> | null;
  error_type: string | null;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
};

export type RunLlmCall = {
  id: string;
  workspace_id: string;
  agent_id: string;
  agent_version_id: string;
  run_id: string | null;
  run_step_id: string | null;
  provider: string;
  model: string;
  status: string;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  total_tokens: number | null;
  latency_ms: number;
  error_message: string | null;
  created_at: string;
};

export type TraceEvent = {
  id: string;
  workspace_id: string;
  run_id: string;
  run_step_id: string | null;
  event_type: string;
  severity: string;
  actor_type: string;
  actor_id: string | null;
  message: string;
  payload: Record<string, unknown>;
  created_at: string;
};

export type Approval = {
  id: string;
  workspace_id: string;
  run_id: string;
  run_step_id: string;
  node_id: string;
  node_name: string;
  title: string;
  instructions: string;
  risk_level: string;
  status: string;
  requested_payload: Record<string, unknown>;
  decision: string | null;
  decision_comment: string;
  decided_by: string | null;
  decided_at: string | null;
  created_at: string;
  updated_at: string;
};

export type WorkflowRun = {
  id: string;
  workspace_id: string;
  workflow_id: string;
  workflow_version_id: string;
  triggered_by: string;
  status: string;
  input: Record<string, unknown>;
  output: Record<string, unknown> | null;
  error_type: string | null;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
  cancelled_at: string | null;
  created_at: string;
  updated_at: string;
  steps: RunStep[];
  llm_calls: RunLlmCall[];
  trace_events: TraceEvent[];
  approvals: Approval[];
};

export type RunCostSummary = {
  totalTokens: number;
  promptTokens: number;
  completionTokens: number;
  totalLatencyMs: number;
};

export function buildWorkflowPayload(values: WorkflowFormValues): WorkflowPayload {
  return {
    name: values.name.trim(),
    description: values.description.trim(),
  };
}

export function parseWorkflowGraph(value: string): WorkflowGraph {
  const parsed = parseJsonObject(value, "Workflow graph");
  return parsed as WorkflowGraph;
}

export function parseRunInput(value: string): Record<string, unknown> {
  return parseJsonObject(value, "Run input");
}

export function buildDefaultWorkflowGraph(agentVersionId: string): WorkflowGraph {
  return {
    schema_version: "1.0",
    nodes: [
      {
        id: "node_start",
        type: "start",
        name: "Start",
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
      {
        id: "node_agent",
        type: "agent",
        name: "Agent",
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
      {
        id: "node_end",
        type: "end",
        name: "End",
        config: {
          output_mapping: {
            markdown: "$.steps.node_agent.output.content",
          },
        },
      },
    ],
    edges: [
      { id: "edge_start_agent", source: "node_start", target: "node_agent", type: "default" },
      { id: "edge_agent_end", source: "node_agent", target: "node_end", type: "default" },
    ],
  };
}

export async function fetchWorkflows(): Promise<Workflow[]> {
  const response = await apiRequest<{ items: Workflow[] }>("/workflows");
  return response.items;
}

export async function fetchWorkflow(workflowId: string): Promise<WorkflowDetail> {
  return apiRequest<WorkflowDetail>(`/workflows/${workflowId}`);
}

export async function createWorkflow(values: WorkflowFormValues): Promise<Workflow> {
  return apiRequest<Workflow>("/workflows", {
    method: "POST",
    body: JSON.stringify(buildWorkflowPayload(values)),
  });
}

export async function publishWorkflowVersion(workflowId: string, graph: WorkflowGraph): Promise<WorkflowVersion> {
  return apiRequest<WorkflowVersion>(`/workflows/${workflowId}/versions`, {
    method: "POST",
    body: JSON.stringify({ graph }),
  });
}

export async function createWorkflowRun(
  workflowId: string,
  input: Record<string, unknown>,
): Promise<WorkflowRun> {
  return apiRequest<WorkflowRun>(`/workflows/${workflowId}/runs`, {
    method: "POST",
    body: JSON.stringify({ input }),
  });
}

export async function executeRun(runId: string): Promise<WorkflowRun> {
  return apiRequest<WorkflowRun>(`/runs/${runId}/execute`, { method: "POST" });
}

export async function fetchApprovals(status?: string): Promise<Approval[]> {
  const suffix = status ? `?status=${encodeURIComponent(status)}` : "";
  const response = await apiRequest<{ items: Approval[] }>(`/approvals${suffix}`);
  return response.items;
}

export async function approveApproval(approvalId: string, comment: string): Promise<WorkflowRun> {
  return apiRequest<WorkflowRun>(`/approvals/${approvalId}/approve`, {
    method: "POST",
    body: JSON.stringify({ comment }),
  });
}

export async function rejectApproval(approvalId: string, comment: string): Promise<WorkflowRun> {
  return apiRequest<WorkflowRun>(`/approvals/${approvalId}/reject`, {
    method: "POST",
    body: JSON.stringify({ comment }),
  });
}

export async function fetchRuns(): Promise<WorkflowRun[]> {
  const response = await apiRequest<{ items: WorkflowRun[] }>("/runs");
  return response.items;
}

export async function fetchRun(runId: string): Promise<WorkflowRun> {
  return apiRequest<WorkflowRun>(`/runs/${runId}`);
}

function parseJsonObject(value: string, label: string): Record<string, unknown> {
  let parsed: unknown;
  try {
    parsed = JSON.parse(value);
  } catch {
    throw new Error(`${label} must be valid JSON`);
  }

  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error(`${label} must be a JSON object`);
  }
  return parsed as Record<string, unknown>;
}

export function formatRunCostSummary(run: Pick<WorkflowRun, "llm_calls">): RunCostSummary {
  return run.llm_calls.reduce(
    (summary, call) => ({
      totalTokens: summary.totalTokens + (call.total_tokens ?? 0),
      promptTokens: summary.promptTokens + (call.prompt_tokens ?? 0),
      completionTokens: summary.completionTokens + (call.completion_tokens ?? 0),
      totalLatencyMs: summary.totalLatencyMs + call.latency_ms,
    }),
    { totalTokens: 0, promptTokens: 0, completionTokens: 0, totalLatencyMs: 0 },
  );
}
