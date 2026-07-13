import { describe, expect, it } from "vitest";

import { navigationItems } from "./navigation";

describe("navigationItems", () => {
  it("exposes the Phase 0 console routes in display order", () => {
    expect(navigationItems).toEqual([
      { label: "仪表盘", href: "/" },
      { label: "智能体", href: "/agents" },
      { label: "工作流", href: "/workflows" },
      { label: "运行记录", href: "/runs" },
      { label: "知识库", href: "/knowledge-bases" },
      { label: "工具", href: "/tools" },
      { label: "评估", href: "/evaluations" },
      { label: "设置", href: "/settings" },
    ]);
  });
});

