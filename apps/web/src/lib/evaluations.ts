import { apiRequest } from "./api-client";

export type EvaluationCaseForm = {
  name: string;
  input: Record<string, unknown>;
  expected: Record<string, unknown>;
};

export type EvaluationFormValues = {
  name: string;
  description: string;
  workflowId: string;
  tokenPricePer1k: string;
  casesText: string;
};

export type EvaluationPayload = {
  name: string;
  description: string;
  workflow_id: string;
  settings: Record<string, unknown>;
  cases: EvaluationCaseForm[];
};

export type EvaluationCase = EvaluationCaseForm & {
  id: string;
  workspace_id: string;
  evaluation_id: string;
  ordinal: number;
  created_at: string;
};

export type EvaluationResult = {
  id: string;
  workspace_id: string;
  evaluation_id: string;
  case_id: string;
  run_id: string | null;
  status: string;
  output: Record<string, unknown> | null;
  error_message: string | null;
  latency_ms: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  created_at: string;
};

export type Evaluation = {
  id: string;
  workspace_id: string;
  workflow_id: string;
  name: string;
  description: string;
  status: string;
  settings: Record<string, unknown>;
  summary: Record<string, unknown>;
  created_by: string;
  created_at: string;
  updated_at: string;
  cases: EvaluationCase[];
  results: EvaluationResult[];
};

export type EvaluationResultSummary = {
  successCount: number;
  failureCount: number;
  totalTokens: number;
  averageLatencyMs: number;
};

export function parseEvaluationCases(value: string): EvaluationCaseForm[] {
  let parsed: unknown;
  try {
    parsed = JSON.parse(value);
  } catch {
    throw new Error("Evaluation cases must be valid JSON");
  }
  if (!Array.isArray(parsed)) {
    throw new Error("Evaluation cases must be a JSON array");
  }
  return parsed.map((item, index) => {
    if (!item || typeof item !== "object" || Array.isArray(item)) {
      throw new Error(`Evaluation case ${index + 1} must be an object`);
    }
    const candidate = item as Partial<EvaluationCaseForm>;
    if (typeof candidate.name !== "string" || candidate.name.trim().length === 0) {
      throw new Error(`Evaluation case ${index + 1} requires a name`);
    }
    return {
      name: candidate.name.trim(),
      input: isRecord(candidate.input) ? candidate.input : {},
      expected: isRecord(candidate.expected) ? candidate.expected : {},
    };
  });
}

export function buildEvaluationPayload(values: EvaluationFormValues): EvaluationPayload {
  return {
    name: values.name.trim(),
    description: values.description.trim(),
    workflow_id: values.workflowId,
    settings: { token_price_per_1k: coerceNumber(values.tokenPricePer1k, 0) },
    cases: parseEvaluationCases(values.casesText),
  };
}

export function summarizeEvaluationResults(results: Pick<EvaluationResult, "status" | "total_tokens" | "latency_ms">[]): EvaluationResultSummary {
  const successCount = results.filter((result) => result.status === "succeeded").length;
  const failureCount = results.length - successCount;
  const totalTokens = results.reduce((total, result) => total + result.total_tokens, 0);
  const totalLatency = results.reduce((total, result) => total + result.latency_ms, 0);
  return {
    successCount,
    failureCount,
    totalTokens,
    averageLatencyMs: results.length ? Math.round(totalLatency / results.length) : 0,
  };
}

export async function fetchEvaluations(): Promise<Evaluation[]> {
  const response = await apiRequest<{ items: Evaluation[] }>("/evaluations");
  return response.items;
}

export async function createEvaluation(values: EvaluationFormValues): Promise<Evaluation> {
  return apiRequest<Evaluation>("/evaluations", {
    method: "POST",
    body: JSON.stringify(buildEvaluationPayload(values)),
  });
}

export async function fetchEvaluation(evaluationId: string): Promise<Evaluation> {
  return apiRequest<Evaluation>(`/evaluations/${evaluationId}`);
}

export async function runEvaluation(evaluationId: string): Promise<Evaluation> {
  return apiRequest<Evaluation>(`/evaluations/${evaluationId}/run`, { method: "POST" });
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function coerceNumber(value: string, fallback: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}
