export type NavigationItem = {
  label: string;
  href: string;
};

export const navigationItems: NavigationItem[] = [
  { label: "Dashboard", href: "/" },
  { label: "Agents", href: "/agents" },
  { label: "Workflows", href: "/workflows" },
  { label: "Runs", href: "/runs" },
  { label: "Knowledge Bases", href: "/knowledge-bases" },
  { label: "Tools", href: "/tools" },
  { label: "Evaluations", href: "/evaluations" },
  { label: "Settings", href: "/settings" },
];

