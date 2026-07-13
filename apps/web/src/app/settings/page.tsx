import { ModulePage } from "@/components/shell/module-page";

export default function SettingsPage() {
  return (
    <ModulePage
      eyebrow="配置"
      metricLabel="模型执行模式"
      metricValue="API"
      rows={[
        { label: "OpenAI 兼容", value: "已启用", tone: "ready" },
        { label: "前端 API 密钥", value: "从不", tone: "ready" },
        { label: "本地模型运行时", value: "已排除", tone: "neutral" },
      ]}
      title="设置"
    />
  );
}

