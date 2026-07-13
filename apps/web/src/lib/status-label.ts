const STATUS_LABELS: Record<string, string> = {
  // 生命周期
  active: "启用",
  inactive: "停用",
  disabled: "已停用",
  draft: "草稿",
  published: "已发布",
  // 运行 / 调用
  queued: "排队中",
  running: "运行中",
  succeeded: "成功",
  failed: "失败",
  waiting_approval: "待审批",
  blocked: "已拦截",
  cancelled: "已取消",
  processed: "已处理",
  parsing: "解析中",
  indexing: "索引中",
  archived: "已归档",
  // 节点类型
  agent: "智能体",
  retrieval: "检索",
  tool: "工具",
  approval: "审批",
  end: "结束",
  start: "开始",
  none: "无",
  // 风险
  low: "低",
  medium: "中",
  high: "高",
  critical: "严重",
  // 其它
  ready: "就绪",
  on: "开启",
  off: "关闭",
  compose: "编排中",
};

export function statusLabel(value: string | undefined | null): string {
  if (!value) return "";
  return STATUS_LABELS[value.toLowerCase()] ?? value;
}

export type Tone = "ready" | "neutral" | "success" | "warning" | "danger" | "info";

const TONE_MAP: Record<string, Tone> = {
  // 成功 / 就绪
  succeeded: "success",
  active: "success",
  enabled: "success",
  published: "success",
  ready: "ready",
  on: "success",
  processed: "success",
  // 等待 / 进行中（中性偏警示）
  queued: "warning",
  waiting_approval: "warning",
  compose: "warning",
  parsing: "warning",
  indexing: "warning",
  blocked: "warning",
  inactive: "warning",
  // 失败 / 终止 / 危险
  failed: "danger",
  cancelled: "danger",
  critical: "danger",
  archived: "danger",
  disabled: "danger",
  // 运行 / 草稿 / 等级 / 节点类型（信息）
  running: "info",
  draft: "info",
  low: "info",
  medium: "info",
  high: "info",
  start: "info",
  end: "info",
  agent: "info",
  retrieval: "info",
  tool: "info",
  approval: "info",
  none: "neutral",
};

export function statusTone(value: string | undefined | null): Tone {
  if (!value) return "neutral";
  return TONE_MAP[value.toLowerCase()] ?? "neutral";
}
