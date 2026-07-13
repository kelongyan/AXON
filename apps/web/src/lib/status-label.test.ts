import { describe, expect, it } from "vitest";

import { statusLabel, statusTone } from "./status-label";

describe("statusLabel", () => {
  it("maps known English enum values to Chinese", () => {
    expect(statusLabel("active")).toBe("启用");
    expect(statusLabel("succeeded")).toBe("成功");
    expect(statusLabel("waiting_approval")).toBe("待审批");
  });

  it("is case-insensitive", () => {
    expect(statusLabel("ACTIVE")).toBe("启用");
    expect(statusLabel("Succeeded")).toBe("成功");
  });

  it("falls back to the raw value for unknown inputs", () => {
    expect(statusLabel("custom_status")).toBe("custom_status");
  });

  it("returns empty string for nullish input", () => {
    expect(statusLabel(null)).toBe("");
    expect(statusLabel(undefined)).toBe("");
  });
});

describe("statusTone", () => {
  it("maps success and danger statuses", () => {
    expect(statusTone("succeeded")).toBe("success");
    expect(statusTone("failed")).toBe("danger");
    expect(statusTone("critical")).toBe("danger");
  });

  it("maps in-progress statuses to info", () => {
    expect(statusTone("running")).toBe("info");
    expect(statusTone("draft")).toBe("info");
  });

  it("maps pending statuses to warning", () => {
    expect(statusTone("waiting_approval")).toBe("warning");
    expect(statusTone("queued")).toBe("warning");
  });

  it("defaults to neutral for unknown or nullish input", () => {
    expect(statusTone("something_unknown")).toBe("neutral");
    expect(statusTone(null)).toBe("neutral");
  });
});
