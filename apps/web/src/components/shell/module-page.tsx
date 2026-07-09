type ModulePageProps = {
  title: string;
  eyebrow: string;
  metricLabel: string;
  metricValue: string;
  rows: Array<{
    label: string;
    value: string;
    tone: "neutral" | "ready" | "pending";
  }>;
};

const toneClassName = {
  neutral: "border-zinc-200 bg-white text-zinc-700",
  ready: "border-emerald-200 bg-emerald-50 text-emerald-700",
  pending: "border-amber-200 bg-amber-50 text-amber-700",
};

export function ModulePage({ title, eyebrow, metricLabel, metricValue, rows }: ModulePageProps) {
  return (
    <div className="space-y-6">
      <section className="border-b border-zinc-200 pb-5">
        <p className="text-xs font-semibold uppercase tracking-normal text-teal-700">{eyebrow}</p>
        <h1 className="mt-2 text-2xl font-semibold text-zinc-950">{title}</h1>
      </section>

      <section className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(280px,360px)]">
        <div className="rounded-lg border border-zinc-200 bg-white p-5">
          <div className="text-sm text-zinc-500">{metricLabel}</div>
          <div className="mt-3 text-4xl font-semibold text-zinc-950">{metricValue}</div>
        </div>
        <div className="space-y-2">
          {rows.map((row) => (
            <div
              className={`flex items-center justify-between rounded-md border px-3 py-2 text-sm ${toneClassName[row.tone]}`}
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

