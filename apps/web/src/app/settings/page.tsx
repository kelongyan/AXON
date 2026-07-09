import { ModulePage } from "@/components/shell/module-page";

export default function SettingsPage() {
  return (
    <ModulePage
      eyebrow="Configuration"
      metricLabel="Model execution mode"
      metricValue="API"
      rows={[
        { label: "OpenAI-compatible", value: "Enabled", tone: "ready" },
        { label: "API key in frontend", value: "Never", tone: "ready" },
        { label: "Local model runtime", value: "Excluded", tone: "neutral" },
      ]}
      title="Settings"
    />
  );
}

