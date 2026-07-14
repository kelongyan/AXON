import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

export function ListItem({
  selected = false,
  title,
  subtitle,
  badge,
  onClick,
  className,
}: {
  selected?: boolean;
  title: ReactNode;
  subtitle?: ReactNode;
  badge?: ReactNode;
  onClick?: () => void;
  className?: string;
}) {
  return (
    <button
      className={cn(
        "w-full border-l-2 px-3 py-3 text-left transition-colors",
        selected
          ? "border-accent bg-accent-soft"
          : "border-transparent hover:bg-surface",
        className,
      )}
      onClick={onClick}
      type="button"
    >
      <div className="flex items-center justify-between gap-3">
        <span className={cn("text-sm font-medium", selected ? "text-accent" : "text-ink")}>
          {title}
        </span>
        {badge}
      </div>
      {subtitle ? (
        <div className={cn("mt-1 text-xs", selected ? "text-accent/70" : "text-ink-3")}>
          {subtitle}
        </div>
      ) : null}
    </button>
  );
}
