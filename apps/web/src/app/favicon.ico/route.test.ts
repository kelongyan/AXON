import { describe, expect, it } from "vitest";

import { GET } from "./route";

describe("favicon route", () => {
  it("serves an SVG favicon for default browser favicon requests", async () => {
    const response = GET();

    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toBe("image/svg+xml");
    expect(await response.text()).toContain("<svg");
  });
});

