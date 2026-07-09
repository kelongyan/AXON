import { describe, expect, it } from "vitest";

import { navigationItems } from "./navigation";

describe("navigationItems", () => {
  it("exposes the Phase 0 console routes in display order", () => {
    expect(navigationItems).toEqual([
      { label: "Dashboard", href: "/" },
      { label: "Agents", href: "/agents" },
      { label: "Workflows", href: "/workflows" },
      { label: "Runs", href: "/runs" },
      { label: "Knowledge Bases", href: "/knowledge-bases" },
      { label: "Tools", href: "/tools" },
      { label: "Evaluations", href: "/evaluations" },
      { label: "Settings", href: "/settings" },
    ]);
  });
});

