import { describe, expect, it } from "vitest";

import { navigationItems } from "./navigation";

describe("navigationItems", () => {
  it("exposes the console routes in display order with icons", () => {
    const routeInfo = navigationItems.map(({ label, href }) => ({ label, href }));
    expect(routeInfo).toEqual([
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

  it("each item has an icon component", () => {
    for (const item of navigationItems) {
      expect(item.icon).toBeDefined();
      expect(typeof item.icon).toBe("object");
    }
  });
});

