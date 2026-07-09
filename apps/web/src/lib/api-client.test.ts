import { describe, expect, it, vi } from "vitest";

describe("api client headers", () => {
  it("omits optional security headers when console auth is not configured", async () => {
    vi.stubEnv("NEXT_PUBLIC_AGENTFLOW_API_KEY", "");
    vi.stubEnv("NEXT_PUBLIC_AGENTFLOW_WORKSPACE_SLUG", "");

    const { buildApiHeaders } = await import("./api-client");

    expect(buildApiHeaders()).toEqual({ "Content-Type": "application/json" });
  });

  it("adds console auth and workspace headers from public console config", async () => {
    vi.stubEnv("NEXT_PUBLIC_AGENTFLOW_API_KEY", "console-secret");
    vi.stubEnv("NEXT_PUBLIC_AGENTFLOW_WORKSPACE_SLUG", "customer-a");
    vi.stubEnv("NEXT_PUBLIC_AGENTFLOW_USER_EMAIL", "operator@example.com");
    vi.resetModules();

    const { buildApiHeaders } = await import("./api-client");

    expect(buildApiHeaders()).toMatchObject({
      "Content-Type": "application/json",
      "X-AgentFlow-API-Key": "console-secret",
      "X-AgentFlow-Workspace-Slug": "customer-a",
      "X-AgentFlow-User-Email": "operator@example.com",
    });
  });
});
