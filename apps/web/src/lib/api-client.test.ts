import { describe, expect, it, vi } from "vitest";

describe("api client headers", () => {
  it("builds JSON headers without browser-visible console credentials", async () => {
    const { buildApiHeaders } = await import("./api-client");

    expect(buildApiHeaders()).toEqual({ "Content-Type": "application/json" });
  });

  it("does not add console auth from public environment variables", async () => {
    vi.stubEnv("NEXT_PUBLIC_AGENTFLOW_API_KEY", "console-secret");
    vi.stubEnv("NEXT_PUBLIC_AGENTFLOW_WORKSPACE_SLUG", "customer-a");
    vi.stubEnv("NEXT_PUBLIC_AGENTFLOW_USER_EMAIL", "operator@example.com");
    vi.resetModules();

    const { buildApiHeaders } = await import("./api-client");

    expect(buildApiHeaders()).toEqual({ "Content-Type": "application/json" });
  });
});
