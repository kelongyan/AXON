import { type Tone } from "@/lib/status-label";
import { Card } from "@/components/ui/glass-card";
import { StatusPill } from "@/components/ui/status-pill";

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

export function ModulePage({ title, eyebrow, metricLabel, metricValue, rows }: ModulePageProps) {
  return (
    <div className="space-y-6">
      {/* Header */}
      <section className="border-b border-line pb-5">
        <p className="text-label text-accent">{eyebrow}</p>
        <h1 className="mt-2 text-page-title text-ink">{title}</h1>
      </section>

      {/* Metric highlight */}
      <section className="space-y-6">
        <Card className="p-5">
          <div className="text-sm text-ink-3">{metricLabel}</div>
          <div className="mt-3 text-metric text-ink">{metricValue}</div>
        </Card>

        {/* Settings rows */}
        <Card className="divide-y divide-line">
          {rows.map((row) => (
            <div
              className="flex items-center justify-between px-5 py-3.5"
              key={row.label}
            >
              <span className="text-sm text-ink-2">{row.label}</span>
              <StatusPill value={row.value} tone={row.tone} size="sm" />
            </div>
          ))}
        </Card>
      </section>
    </div>
  );
}
