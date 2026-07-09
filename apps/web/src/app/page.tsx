const metrics = [
  { label: "API service", value: "Ready", tone: "ready" },
  { label: "Database", value: "Compose", tone: "pending" },
  { label: "Redis", value: "Compose", tone: "pending" },
  { label: "MinIO", value: "Compose", tone: "pending" },
] as const;

const modules = [
  ["Agents", "Versioned roles and model settings"],
  ["Workflows", "Reusable DAG definitions"],
  ["Runs", "Execution state and trace"],
  ["Tools", "Registry and risk controls"],
];

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <section className="border-b border-zinc-200 pb-5">
        <p className="text-xs font-semibold uppercase tracking-normal text-teal-700">Dashboard</p>
        <h1 className="mt-2 text-2xl font-semibold text-zinc-950">Phase 0 Foundation</h1>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map((metric) => (
          <div className="rounded-lg border border-zinc-200 bg-white p-4" key={metric.label}>
            <div className="text-sm text-zinc-500">{metric.label}</div>
            <div className="mt-3 text-2xl font-semibold text-zinc-950">{metric.value}</div>
          </div>
        ))}
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        {modules.map(([name, description]) => (
          <div className="rounded-lg border border-zinc-200 bg-white p-5" key={name}>
            <div className="text-base font-semibold text-zinc-950">{name}</div>
            <div className="mt-2 text-sm text-zinc-600">{description}</div>
          </div>
        ))}
      </section>
    </div>
  );
}

