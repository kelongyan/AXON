import { describe, expect, it } from "vitest";

import { buildGrantLabel, parseToolInput } from "./tools";

describe("parseToolInput", () => {
  it("parses JSON object input", () => {
    expect(parseToolInput('{"data":{"title":"Report"},"select_keys":["title"]}')).toEqual({
      data: { title: "Report" },
      select_keys: ["title"],
    });
  });

  it("rejects invalid JSON with a readable error", () => {
    expect(() => parseToolInput("{bad json")).toThrow("Tool input must be valid JSON");
  });

  it("rejects non-object JSON", () => {
    expect(() => parseToolInput("[1,2,3]")).toThrow("Tool input must be a JSON object");
  });
});

describe("buildGrantLabel", () => {
  it("combines agent and tool names", () => {
    expect(buildGrantLabel("Researcher Agent", "JSON Transform")).toBe("Researcher Agent -> JSON Transform");
  });
});

