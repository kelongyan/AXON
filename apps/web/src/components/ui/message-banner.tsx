import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

type BannerTone = "info" | "success" | "danger";

export function MessageBanner({
  message,
  tone = "info",
}: {
  message: ReactNode;
  tone?: BannerTone;
}) {
  const toneClass: Record<BannerTone, string> = {
    info: "border-line bg-surface-solid text-ink-2",
    success: "border-success/30 bg-success/10 text-success",
    danger: "border-danger/30 bg-danger/10 text-danger",
  };
  return (
    <div className={cn("rounded-xl border px-4 py-3 text-sm", toneClass[tone])} role="status">
      {message}
    </div>
  );
}
