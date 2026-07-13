import { cn } from "@/lib/cn";
import { statusLabel, type Tone } from "@/lib/status-label";

const toneClass: Record<Tone, string> = {
  ready: "border-success/30 bg-success/10 text-success",
  neutral: "border-line bg-surface-solid text-ink-2",
  success: "border-success/30 bg-success/10 text-success",
  warning: "border-warning/30 bg-warning/10 text-warning",
  danger: "border-danger/30 bg-danger/10 text-danger",
  info: "border-info/30 bg-info/10 text-info",
};

export function StatusPill({
  label,
  value,
  tone = "neutral",
  status,
}: {
  label?: string;
  value?: string;
  tone?: Tone;
  status?: string;
}) {
  const text = status ? statusLabel(status) : value ?? "";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium",
        toneClass[tone],
      )}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current opacity-70" aria-hidden />
      {label ? `${label}: ` : ""}
      {text}
    </span>
  );
}
