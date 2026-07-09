export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function parseApiError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown; error?: { message?: unknown } };
    if (typeof body.detail === "string") {
      return body.detail;
    }
    if (typeof body.error?.message === "string") {
      return body.error.message;
    }
  } catch {
    // Fall through to the status text below.
  }
  return response.statusText || `Request failed with ${response.status}`;
}

export function buildApiHeaders(initHeaders?: HeadersInit, includeJson = true): HeadersInit {
  const headers: Record<string, string> = {};
  if (includeJson) {
    headers["Content-Type"] = "application/json";
  }
  addHeader(headers, "X-AgentFlow-API-Key", process.env.NEXT_PUBLIC_AGENTFLOW_API_KEY);
  addHeader(headers, "X-AgentFlow-Workspace-Slug", process.env.NEXT_PUBLIC_AGENTFLOW_WORKSPACE_SLUG);
  addHeader(headers, "X-AgentFlow-Workspace-Name", process.env.NEXT_PUBLIC_AGENTFLOW_WORKSPACE_NAME);
  addHeader(headers, "X-AgentFlow-User-Email", process.env.NEXT_PUBLIC_AGENTFLOW_USER_EMAIL);
  addHeader(headers, "X-AgentFlow-User-Name", process.env.NEXT_PUBLIC_AGENTFLOW_USER_NAME);
  return {
    ...headers,
    ...initHeaders,
  };
}

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: buildApiHeaders(init.headers),
  });

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export async function apiFormRequest<T>(path: string, data: FormData): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    body: data,
    headers: buildApiHeaders(undefined, false),
  });
  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }
  return (await response.json()) as T;
}

function addHeader(headers: Record<string, string>, name: string, value: string | undefined): void {
  const trimmed = value?.trim();
  if (trimmed) {
    headers[name] = trimmed;
  }
}
