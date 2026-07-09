import { describe, expect, it } from "vitest";

import { parseApiError } from "./api-client";
import { buildAgentPayload, buildVersionPayload } from "./agents";

const formValues = {
  name: "  Researcher Agent  ",
  description: "  Finds facts  ",
  rolePrompt: "  You are careful.  ",
  systemPrompt: "  Return bullets.  ",
  modelName: "  gpt-4.1-mini  ",
  temperature: "0.2",
  maxOutputTokens: "700",
};

describe("agent payload helpers", () => {
  it("builds a trimmed create payload with API-only provider defaults", () => {
    expect(buildAgentPayload(formValues)).toEqual({
      name: "Researcher Agent",
      description: "Finds facts",
      role_prompt: "You are careful.",
      system_prompt: "Return bullets.",
      model_provider: "openai_compatible",
      model_name: "gpt-4.1-mini",
      temperature: 0.2,
      max_output_tokens: 700,
    });
  });

  it("builds a version payload without mutable Agent metadata", () => {
    expect(buildVersionPayload(formValues)).toEqual({
      role_prompt: "You are careful.",
      system_prompt: "Return bullets.",
      model_provider: "openai_compatible",
      model_name: "gpt-4.1-mini",
      temperature: 0.2,
      max_output_tokens: 700,
    });
  });

  it("normalizes invalid numeric fields to safe API values", () => {
    expect(
      buildAgentPayload({
        ...formValues,
        temperature: "not-a-number",
        maxOutputTokens: "",
      }),
    ).toMatchObject({
      temperature: 0.2,
      max_output_tokens: 1000,
    });
  });
});

describe("parseApiError", () => {
  it("prefers FastAPI detail without exposing generic response text", async () => {
    const response = new Response(JSON.stringify({ detail: "provider returned 401" }), {
      status: 502,
      statusText: "Bad Gateway",
    });

    await expect(parseApiError(response)).resolves.toBe("provider returned 401");
  });
});
