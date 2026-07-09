import { apiRequest } from "./api-client";

export type Tool = {
  id: string;
  workspace_id: string;
  name: string;
  display_name: string;
  description: string;
  version: string;
  risk_level: string;
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
  timeout_seconds: number;
  requires_approval: boolean;
  status: string;
  created_at: string;
  updated_at: string;
};

export type ToolCall = {
  id: string;
  workspace_id: string;
  agent_id: string | null;
  tool_id: string;
  tool_name: string;
  status: string;
  risk_level: string;
  input_summary: Record<string, unknown>;
  output_summary: Record<string, unknown> | null;
  latency_ms: number;
  error_message: string | null;
  created_at: string;
};

export type ToolInvokeResult = {
  status: string;
  output: Record<string, unknown> | null;
  tool_call: ToolCall;
};

export type ToolSeedResult = {
  created: number;
  updated: number;
  items: Tool[];
};

export function parseToolInput(value: string): Record<string, unknown> {
  let parsed: unknown;
  try {
    parsed = JSON.parse(value);
  } catch (error) {
    throw new Error("Tool input must be valid JSON");
  }

  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("Tool input must be a JSON object");
  }
  return parsed as Record<string, unknown>;
}

export function buildGrantLabel(agentName: string, toolName: string): string {
  return `${agentName} -> ${toolName}`;
}

export async function seedBuiltInTools(): Promise<ToolSeedResult> {
  return apiRequest<ToolSeedResult>("/tools/seed-built-ins", { method: "POST" });
}

export async function fetchTools(): Promise<Tool[]> {
  const response = await apiRequest<{ items: Tool[] }>("/tools");
  return response.items;
}

export async function grantTool(agentId: string, toolId: string): Promise<void> {
  await apiRequest(`/agents/${agentId}/tools/${toolId}/grant`, { method: "POST" });
}

export async function revokeTool(agentId: string, toolId: string): Promise<void> {
  await apiRequest(`/agents/${agentId}/tools/${toolId}`, { method: "DELETE" });
}

export async function invokeTool(
  toolId: string,
  agentId: string,
  input: Record<string, unknown>,
): Promise<ToolInvokeResult> {
  return apiRequest<ToolInvokeResult>(`/tools/${toolId}/invoke`, {
    method: "POST",
    body: JSON.stringify({ agent_id: agentId, input }),
  });
}

export async function fetchToolCalls(): Promise<ToolCall[]> {
  const response = await apiRequest<{ items: ToolCall[] }>("/tools/calls");
  return response.items;
}
