import { cn } from "@/lib/cn";
import { statusLabel, type Tone } from "@/lib/status-label";

const toneClass: Record<Tone, string> = {
  ready: "border-success/25 bg-success/8 text-success",
  neutral: "border-line bg-surface-solid text-ink-2",
  success: "border-success/25 bg-success/8 text-success",
  warning: "border-warning/25 bg-warning/8 text-warning",
  danger: "border-danger/25 bg-danger/8 text-danger",
  info: "border-info/25 bg-info/8 text-info",
};

type Size = "sm" | "md";

const sizeClass: Record<Size, string> = {
  sm: "px-2 py-0.5 text-[11px]",
  md: "px-2.5 py-1 text-xs",
};

export function StatusPill({
  label,
  value,
  tone = "neutral",
  status,
  size = "md",
}: {
  label?: string;
  value?: string;
  tone?: Tone;
  status?: string;
  size?: Size;
}) {
  const text = status ? statusLabel(status) : value ?? "";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-lg border font-medium",
        toneClass[tone],
        sizeClass[size],
      )}
    >
      <span className="h-1 w-1 rounded-full bg-current opacity-60" aria-hidden />
      {label ? `${label}: ` : ""}
      {text}
    </span>
  );
}
