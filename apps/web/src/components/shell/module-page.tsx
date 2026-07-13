import { type Tone } from "@/lib/status-label";
import { GlassCard } from "@/components/ui/glass-card";

type ModulePageProps = {
  title: string;
  eyebrow: string;
  metricLabel: string;
  metricValue: string;
  rows: Array<{
    label: string;
    value: string;
    tone: Tone;
  }>;
};

const rowToneClass: Record<Tone, string> = {
  ready: "border-success/30 bg-success/10 text-success",
  success: "border-success/30 bg-success/10 text-success",
  warning: "border-warning/30 bg-warning/10 text-warning",
  danger: "border-danger/30 bg-danger/10 text-danger",
  info: "border-info/30 bg-info/10 text-info",
  neutral: "border-line bg-surface-solid text-ink-2",
};

export function ModulePage({ title, eyebrow, metricLabel, metricValue, rows }: ModulePageProps) {
  return (
    <div className="space-y-6">
      <section className="border-b border-line pb-5">
        <p className="text-xs font-semibold uppercase tracking-wide text-accent">{eyebrow}</p>
        <h1 className="mt-2 text-2xl font-semibold text-ink">{title}</h1>
      </section>

      <section className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(280px,360px)]">
        <GlassCard className="p-5">
          <div className="text-sm text-ink-3">{metricLabel}</div>
          <div className="mt-3 text-4xl font-semibold text-ink">{metricValue}</div>
        </GlassCard>
        <div className="space-y-2">
          {rows.map((row) => (
            <div
              className={`flex items-center justify-between rounded-xl border px-3 py-2 text-sm ${rowToneClass[row.tone]}`}
              key={row.label}
            >
              <span>{row.label}</span>
              <span className="font-medium">{row.value}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
