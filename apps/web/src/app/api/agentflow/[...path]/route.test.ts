import { afterEach, describe, expect, it, vi } from "vitest";

describe("agentflow proxy route", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it("injects server-side console headers and ignores browser-supplied AgentFlow headers", async () => {
    vi.stubEnv("AGENTFLOW_API_BASE_URL", "http://api.internal:8000");
    vi.stubEnv("AGENTFLOW_API_AUTH_KEY", "server-secret");
    vi.stubEnv("AGENTFLOW_CONSOLE_WORKSPACE_SLUG", "customer-a");

    const fetchMock = vi.fn(
      async () => new Response(JSON.stringify({ ok: true }), { headers: { "content-type": "application/json" } }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const { GET } = await import("./route");
    const response = await GET(
      new Request("http://localhost/api/agentflow/me?include=workspace", {
        headers: {
          "X-AgentFlow-API-Key": "browser-secret",
          "X-AgentFlow-Workspace-Slug": "browser-workspace",
        },
      }),
      { params: Promise.resolve({ path: ["me"] }) },
    );

    const [, init] = fetchMock.mock.calls[0];
    const headers = init?.headers as Headers;

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.internal:8000/me?include=workspace",
      expect.objectContaining({ method: "GET" }),
    );
    expect(headers.get("X-AgentFlow-API-Key")).toBe("server-secret");
    expect(headers.get("X-AgentFlow-Workspace-Slug")).toBe("customer-a");
  });
});
