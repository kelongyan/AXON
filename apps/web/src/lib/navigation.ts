import {
  BarChart3,
  BookOpen,
  Bot,
  LayoutDashboard,
  PlayCircle,
  Settings,
  Workflow,
  Wrench,
  type LucideIcon,
} from "lucide-react";

export type NavigationItem = {
  label: string;
  href: string;
  icon: LucideIcon;
};

export const navigationItems: NavigationItem[] = [
  { label: "仪表盘", href: "/", icon: LayoutDashboard },
  { label: "智能体", href: "/agents", icon: Bot },
  { label: "工作流", href: "/workflows", icon: Workflow },
  { label: "运行记录", href: "/runs", icon: PlayCircle },
  { label: "知识库", href: "/knowledge-bases", icon: BookOpen },
  { label: "工具", href: "/tools", icon: Wrench },
  { label: "评估", href: "/evaluations", icon: BarChart3 },
  { label: "设置", href: "/settings", icon: Settings },
];

