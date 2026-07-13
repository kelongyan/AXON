export type NavigationItem = {
  label: string;
  href: string;
};

export const navigationItems: NavigationItem[] = [
  { label: "仪表盘", href: "/" },
  { label: "智能体", href: "/agents" },
  { label: "工作流", href: "/workflows" },
  { label: "运行记录", href: "/runs" },
  { label: "知识库", href: "/knowledge-bases" },
  { label: "工具", href: "/tools" },
  { label: "评估", href: "/evaluations" },
  { label: "设置", href: "/settings" },
];

