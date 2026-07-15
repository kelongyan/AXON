export const runtime = "nodejs";

type RouteContext = {
  params: Promise<{
    path: string[];
  }>;
};

const API_BASE_URL = process.env.AGENTFLOW_API_BASE_URL ?? "http://localhost:8000";
const HOP_BY_HOP_HEADERS = [
  "accept-encoding",
  "connection",
  "content-length",
  "host",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
];
const AGENTFLOW_HEADERS = [
  "x-agentflow-api-key",
  "x-agentflow-workspace-slug",
  "x-agentflow-workspace-name",
  "x-agentflow-user-email",
  "x-agentflow-user-name",
];

export async function GET(request: Request, context: RouteContext): Promise<Response> {
  return proxyAgentflowRequest(request, context);
}

export async function POST(request: Request, context: RouteContext): Promise<Response> {
  return proxyAgentflowRequest(request, context);
}

export async function PATCH(request: Request, context: RouteContext): Promise<Response> {
  return proxyAgentflowRequest(request, context);
}

export async function PUT(request: Request, context: RouteContext): Promise<Response> {
  return proxyAgentflowRequest(request, context);
}

export async function DELETE(request: Request, context: RouteContext): Promise<Response> {
  return proxyAgentflowRequest(request, context);
}

export async function OPTIONS(request: Request, context: RouteContext): Promise<Response> {
  return proxyAgentflowRequest(request, context);
}

async function proxyAgentflowRequest(request: Request, context: RouteContext): Promise<Response> {
  const { path } = await context.params;
  const upstreamUrl = buildUpstreamUrl(request.url, path);
  const response = await fetch(upstreamUrl, {
    method: request.method,
    headers: buildUpstreamHeaders(request.headers),
    body: hasRequestBody(request.method) ? await request.arrayBuffer() : undefined,
    redirect: "manual",
  });

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: buildDownstreamHeaders(response.headers),
  });
}

function buildUpstreamUrl(requestUrl: string, path: string[]): string {
  const sourceUrl = new URL(requestUrl);
  const baseUrl = API_BASE_URL.endsWith("/") ? API_BASE_URL : `${API_BASE_URL}/`;
  const upstreamUrl = new URL(path.map(encodeURIComponent).join("/"), baseUrl);
  upstreamUrl.search = sourceUrl.search;
  return upstreamUrl.toString();
}

function buildUpstreamHeaders(requestHeaders: Headers): Headers {
  const headers = new Headers(requestHeaders);
  for (const name of [...HOP_BY_HOP_HEADERS, ...AGENTFLOW_HEADERS]) {
    headers.delete(name);
  }

  setHeader(headers, "X-AgentFlow-API-Key", process.env.AGENTFLOW_API_AUTH_KEY);
  setHeader(headers, "X-AgentFlow-Workspace-Slug", process.env.AGENTFLOW_CONSOLE_WORKSPACE_SLUG);
  setHeader(headers, "X-AgentFlow-Workspace-Name", process.env.AGENTFLOW_CONSOLE_WORKSPACE_NAME);
  setHeader(headers, "X-AgentFlow-User-Email", process.env.AGENTFLOW_CONSOLE_USER_EMAIL);
  setHeader(headers, "X-AgentFlow-User-Name", process.env.AGENTFLOW_CONSOLE_USER_NAME);
  return headers;
}

function buildDownstreamHeaders(responseHeaders: Headers): Headers {
  const headers = new Headers(responseHeaders);
  for (const name of HOP_BY_HOP_HEADERS) {
    headers.delete(name);
  }
  headers.delete("content-encoding");
  return headers;
}

function hasRequestBody(method: string): boolean {
  return method !== "GET" && method !== "HEAD";
}

function setHeader(headers: Headers, name: string, value: string | undefined): void {
  const trimmed = value?.trim();
  if (trimmed) {
    headers.set(name, trimmed);
  }
}
