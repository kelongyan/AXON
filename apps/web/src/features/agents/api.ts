import { apiRequest } from "../../lib/api-client";

export type AgentFormValues = {
  name: string;
  description: string;
  rolePrompt: string;
  systemPrompt: string;
  modelName: string;
  temperature: string;
  maxOutputTokens: string;
};

export type AgentVersionPayload = {
  role_prompt: string;
  system_prompt: string;
  model_provider: string;
  model_name: string;
  temperature: number;
  max_output_tokens: number;
};

export type AgentPayload = AgentVersionPayload & {
  name: string;
  description: string;
};

export type AgentVersion = AgentVersionPayload & {
  id: string;
  agent_id: string;
  version_number: number;
  output_schema: Record<string, unknown> | null;
  status: string;
  published_at: string;
};

export type LlmCall = {
  id: string;
  agent_id: string;
  agent_version_id: string;
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

export type Agent = {
  id: string;
  workspace_id: string;
  name: string;
  description: string;
  status: string;
  current_version_id: string | null;
  created_at: string;
  updated_at: string;
  current_version: AgentVersion | null;
};

export type AgentDetail = Agent & {
  versions: AgentVersion[];
  recent_llm_calls: LlmCall[];
};

export type MeContext = {
  user: {
    id: string;
    email: string | null;
    display_name: string;
    avatar_url: string | null;
    status: string;
  };
  workspace: {
    id: string;
    name: string;
    slug: string;
    status: string;
  };
  membership: {
    role: string;
  };
};

export type AgentTestRun = {
  output: string;
  llm_call: LlmCall;
};

export function buildAgentPayload(values: AgentFormValues): AgentPayload {
  return {
    name: trim(values.name),
    description: trim(values.description),
    ...buildVersionPayload(values),
  };
}

export function buildVersionPayload(values: AgentFormValues): AgentVersionPayload {
  return {
    role_prompt: trim(values.rolePrompt),
    system_prompt: trim(values.systemPrompt),
    model_provider: "openai_compatible",
    model_name: trim(values.modelName),
    temperature: coerceNumber(values.temperature, 0.2),
    max_output_tokens: coerceInteger(values.maxOutputTokens, 1000),
  };
}

export async function fetchMe(): Promise<MeContext> {
  return apiRequest<MeContext>("/me");
}

export async function fetchAgents(): Promise<Agent[]> {
  const response = await apiRequest<{ items: Agent[] }>("/agents");
  return response.items;
}

export async function fetchAgent(agentId: string): Promise<AgentDetail> {
  return apiRequest<AgentDetail>(`/agents/${agentId}`);
}

export async function createAgent(values: AgentFormValues): Promise<Agent> {
  return apiRequest<Agent>("/agents", {
    method: "POST",
    body: JSON.stringify(buildAgentPayload(values)),
  });
}

export async function publishAgentVersion(agentId: string, values: AgentFormValues): Promise<AgentVersion> {
  return apiRequest<AgentVersion>(`/agents/${agentId}/versions`, {
    method: "POST",
    body: JSON.stringify(buildVersionPayload(values)),
  });
}

export async function cloneAgent(agentId: string): Promise<Agent> {
  return apiRequest<Agent>(`/agents/${agentId}/clone`, { method: "POST" });
}

export async function disableAgent(agentId: string): Promise<Agent> {
  return apiRequest<Agent>(`/agents/${agentId}/disable`, { method: "POST" });
}

export async function runAgentTest(agentId: string, input: string): Promise<AgentTestRun> {
  return apiRequest<AgentTestRun>(`/agents/${agentId}/test-runs`, {
    method: "POST",
    body: JSON.stringify({ input }),
  });
}

function trim(value: string): string {
  return value.trim();
}

function coerceNumber(value: string, fallback: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function coerceInteger(value: string, fallback: number): number {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) ? parsed : fallback;
}
