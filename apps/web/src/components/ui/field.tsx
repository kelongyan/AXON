import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

export function Field({
  label,
  className,
  children,
}: {
  label: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <label className={cn("block", className)}>
      <span className="text-xs font-semibold uppercase tracking-wide text-ink-3">{label}</span>
      <div className="mt-1.5">{children}</div>
    </label>
  );
}
