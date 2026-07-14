"use client";

import {
  ChevronDown,
  ChevronRight,
  Play,
  XCircle,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import {
  type Approval,
  type WorkflowRun,
  approveApproval,
  cancelRun,
  canCancelRunStatus,
  executeRun,
  fetchApprovals,
  fetchRun,
  fetchRuns,
  formatRunCostSummary,
  formatRunRuntimeSummary,
  rejectApproval,
  shouldPollRunStatus,
} from "@/lib/workflows";
import { errorMessage } from "@/lib/error-message";
import { statusLabel, statusTone } from "@/lib/status-label";
import { useRunAction } from "@/lib/use-run-action";
import { Button } from "@/components/ui/button";
import { Card, MetricCard } from "@/components/ui/glass-card";
import { ListItem } from "@/components/ui/list-item";
import { MessageBanner } from "@/components/ui/message-banner";
import { StatusPill } from "@/components/ui/status-pill";

function statusTextClass(status: string): string {
  switch (statusTone(status)) {
    case "success":
      return "text-success";
    case "warning":
      return "text-warning";
    case "danger":
      return "text-danger";
    case "info":
      return "text-info";
    default:
      return "text-ink-2";
  }
}

function statusBorderClass(status: string): string {
  switch (statusTone(status)) {
    case "success":
      return "border-l-success";
    case "warning":
      return "border-l-warning";
    case "danger":
      return "border-l-danger";
    case "info":
      return "border-l-info";
    default:
      return "border-l-ink-3";
  }
}

function shortId(value: string): string {
  return value.slice(0, 8);
}

export function RunsConsole() {
  const [runs, setRuns] = useState<WorkflowRun[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [detail, setDetail] = useState<WorkflowRun | null>(null);
  const [pendingApprovals, setPendingApprovals] = useState<Approval[]>([]);
  const [approvalComment, setApprovalComment] = useState("阶段 6 冒烟测试评审意见。");
  const { busy, message, run, setMessage } = useRunAction();

  const [stepsExpanded, setStepsExpanded] = useState(true);
  const [llmExpanded, setLlmExpanded] = useState(false);
  const [toolsExpanded, setToolsExpanded] = useState(false);
  const [eventsExpanded, setEventsExpanded] = useState(false);
  const [outputExpanded, setOutputExpanded] = useState(true);

  const selectedRun = useMemo(
    () => runs.find((run) => run.id === selectedRunId) ?? null,
    [runs, selectedRunId],
  );
  const runCost = useMemo(
    () => (detail ? formatRunCostSummary(detail) : { totalTokens: 0, promptTokens: 0, completionTokens: 0, totalLatencyMs: 0 }),
    [detail],
  );
  const runRuntime = useMemo(
    () =>
      detail
        ? formatRunRuntimeSummary(detail)
        : { worker: "Unclaimed", leaseExpiresAt: "No active lease", checkpoint: "None" },
    [detail],
  );
  const selectedRunApprovals = detail?.approvals.filter((approval) => approval.status === "pending") ?? [];
  const canCancelSelectedRun = detail ? canCancelRunStatus(detail.status) : selectedRun ? canCancelRunStatus(selectedRun.status) : false;
  const hasPollingRun = useMemo(
    () => runs.some((run) => shouldPollRunStatus(run.status)) || (detail ? shouldPollRunStatus(detail.status) : false),
    [detail, runs],
  );

  useEffect(() => {
    void loadRuns();
  }, []);

  useEffect(() => {
    if (selectedRunId) {
      void loadRunDetail(selectedRunId);
    } else {
      setDetail(null);
    }
  }, [selectedRunId]);

  useEffect(() => {
    if (!hasPollingRun) {
      return;
    }
    const timer = window.setInterval(() => {
      void refreshRunSnapshot();
    }, 3000);
    return () => window.clearInterval(timer);
  }, [hasPollingRun, selectedRunId]);

  async function loadRuns() {
    await run(async () => {
      const [nextRuns, approvals] = await Promise.all([fetchRuns(), fetchApprovals("pending")]);
      setRuns(nextRuns);
      setPendingApprovals(approvals);
      setSelectedRunId((current) => current ?? nextRuns[0]?.id ?? null);
    });
  }

  async function loadRunDetail(runId: string) {
    try {
      setDetail(await fetchRun(runId));
    } catch (error) {
      setMessage(errorMessage(error));
    }
  }

  async function refreshRunSnapshot() {
    try {
      const [nextRuns, approvals, nextDetail] = await Promise.all([
        fetchRuns(),
        fetchApprovals("pending"),
        selectedRunId ? fetchRun(selectedRunId) : Promise.resolve(null),
      ]);
      setRuns(nextRuns);
      setPendingApprovals(approvals);
      if (nextDetail) {
        setDetail(nextDetail);
      }
    } catch (error) {
      setMessage(errorMessage(error));
    }
  }

  async function handleExecute() {
    if (!selectedRunId) {
      return;
    }
    await run(async () => {
      const run = await executeRun(selectedRunId);
      setDetail(run);
      setMessage(`运行 ${statusLabel(run.status)}`);
      const [nextRuns, approvals] = await Promise.all([fetchRuns(), fetchApprovals("pending")]);
      setRuns(nextRuns);
      setPendingApprovals(approvals);
    });
  }

  async function handleCancel() {
    if (!selectedRunId) {
      return;
    }
    await run(async () => {
      const run = await cancelRun(selectedRunId, "Cancelled from the Runs console.");
      setDetail(run);
      setSelectedRunId(run.id);
      setMessage(`运行 ${statusLabel(run.status)}`);
      const [nextRuns, approvals] = await Promise.all([fetchRuns(), fetchApprovals("pending")]);
      setRuns(nextRuns);
      setPendingApprovals(approvals);
    });
  }

  async function decideApproval(approvalId: string, decision: "approve" | "reject") {
    await run(async () => {
      const run =
        decision === "approve"
          ? await approveApproval(approvalId, approvalComment)
          : await rejectApproval(approvalId, approvalComment);
      setDetail(run);
      setSelectedRunId(run.id);
      setMessage(`审批${decision === "approve" ? "通过" : "驳回"}；运行 ${statusLabel(run.status)}`);
      const [nextRuns, approvals] = await Promise.all([fetchRuns(), fetchApprovals("pending")]);
      setRuns(nextRuns);
      setPendingApprovals(approvals);
    });
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <header className="border-b border-line pb-4">
        <h1 className="text-page-title text-ink">运行记录</h1>
        <p className="mt-1 text-sm text-ink-3">查看工作流执行过程、步骤、模型/工具调用与链路事件。</p>
        <div className="mt-3 flex flex-wrap gap-2 text-xs">
          <StatusPill label="运行记录" value={String(runs.length)} tone="neutral" />
          <StatusPill label="待审批" value={String(pendingApprovals.length)} tone={pendingApprovals.length ? "warning" : "success"} />
          <StatusPill label="链路" value="Phase 6" tone="success" />
        </div>
      </header>

      {message ? <MessageBanner message={message} /> : null}

      {/* Two-column layout */}
      <section className="grid gap-5 xl:grid-cols-[320px_minmax(0,1fr)]">
        {/* Left: Run list */}
        <Card className="overflow-hidden">
          <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
            <div>
              <div className="text-sm font-semibold text-ink">运行列表</div>
              <div className="mt-0.5 text-xs text-ink-3">{runs.length} 条近期运行</div>
            </div>
            <Button variant="default" disabled={busy} onClick={() => void loadRuns()} type="button">
              刷新
            </Button>
          </div>
          <div className="max-h-[720px] overflow-auto">
            {runs.length === 0 ? (
              <div className="px-4 py-8 text-sm text-ink-3">暂无运行记录</div>
            ) : (
              runs.map((run) => (
                <ListItem
                  key={run.id}
                  selected={selectedRunId === run.id}
                  title={
                    <span className="flex items-center gap-2">
                      <span
                        className={`inline-block h-2 w-2 rounded-full ${
                          statusTone(run.status) === "success"
                            ? "bg-success"
                            : statusTone(run.status) === "warning"
                              ? "bg-warning"
                              : statusTone(run.status) === "danger"
                                ? "bg-danger"
                                : statusTone(run.status) === "info"
                                  ? "bg-info"
                                  : "bg-ink-3"
                        }`}
                        aria-hidden
                      />
                      {shortId(run.id)}
                    </span>
                  }
                  subtitle={
                    <span className="flex items-center gap-2">
                      <span>{String(run.input.topic ?? "No topic")}</span>
                      <span>·</span>
                      <span>{run.steps.length} steps</span>
                    </span>
                  }
                  badge={
                    <span className={`text-xs font-medium ${statusTextClass(run.status)}`}>
                      {statusLabel(run.status)}
                    </span>
                  }
                  onClick={() => setSelectedRunId(run.id)}
                  className={statusBorderClass(run.status)}
                />
              ))
            )}
          </div>
        </Card>

        {/* Right: Detail area */}
        <div className="space-y-5">
          {/* Detail header */}
          <Card className="p-5">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div>
                <h2 className="text-base font-semibold text-ink">
                  {selectedRun ? shortId(selectedRun.id) : "请选择运行"}
                </h2>
                <p className="mt-1 text-sm text-ink-3">
                  {detail ? `${statusLabel(detail.status)} · ${detail.workflow_version_id}` : "未选择运行"}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                {canCancelSelectedRun ? (
                  <Button variant="danger" disabled={busy || !selectedRunId} onClick={handleCancel} type="button">
                    <XCircle size={14} /> 取消
                  </Button>
                ) : null}
                <Button variant="primary" disabled={busy || !selectedRunId} onClick={handleExecute} type="button">
                  <Play size={14} /> 执行
                </Button>
              </div>
            </div>
          </Card>

          {/* Pending approvals block (prominent, at top of detail) */}
          {selectedRunApprovals.length ? (
            <Card className="overflow-hidden border-warning/40 bg-warning/5 p-5">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="h-2 w-2 animate-pulse rounded-full bg-warning" aria-hidden />
                    <h3 className="text-sm font-semibold text-warning">待审批</h3>
                  </div>
                  <p className="mt-1.5 text-sm font-medium text-ink">{selectedRunApprovals[0].title}</p>
                  <p className="mt-1 text-xs text-ink-3">{selectedRunApprovals[0].instructions}</p>
                </div>
                <span className="shrink-0 rounded-lg border border-warning/40 bg-warning/10 px-3 py-1.5 text-xs font-semibold text-warning">
                  {statusLabel(selectedRunApprovals[0].risk_level)}
                </span>
              </div>
              <div className="mt-4">
                <textarea
                  className="field-input min-h-20 resize-y bg-surface-solid"
                  onChange={(event) => setApprovalComment(event.target.value)}
                  value={approvalComment}
                />
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <Button
                  variant="primary"
                  disabled={busy}
                  onClick={() => void decideApproval(selectedRunApprovals[0].id, "approve")}
                  type="button"
                >
                  通过
                </Button>
                <Button
                  variant="danger"
                  disabled={busy}
                  onClick={() => void decideApproval(selectedRunApprovals[0].id, "reject")}
                  type="button"
                >
                  驳回
                </Button>
              </div>
            </Card>
          ) : null}

          {/* Metrics row */}
          {detail ? (
            <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
              <MetricCard>
                <div className="text-xs text-ink-3">状态</div>
                <div className={`mt-1 text-lg font-semibold ${statusTextClass(detail.status)}`}>
                  {statusLabel(detail.status)}
                </div>
              </MetricCard>
              <MetricCard>
                <div className="text-xs text-ink-3">步骤</div>
                <div className="mt-1 text-lg font-semibold text-ink">{detail.steps.length}</div>
              </MetricCard>
              <MetricCard>
                <div className="text-xs text-ink-3">工具调用</div>
                <div className="mt-1 text-lg font-semibold text-ink">{detail.tool_calls.length}</div>
              </MetricCard>
              <MetricCard>
                <div className="text-xs text-ink-3">Token</div>
                <div className="mt-1 text-lg font-semibold text-ink">{runCost.totalTokens}</div>
              </MetricCard>
            </div>
          ) : null}

          {/* Runtime info (compact) */}
          {detail ? (
            <Card className="grid gap-px overflow-hidden bg-line sm:grid-cols-3">
              <div className="bg-surface-solid px-4 py-3">
                <div className="text-xs text-ink-3">执行节点</div>
                <div className="mt-0.5 text-sm font-medium text-ink-2">{runRuntime.worker}</div>
              </div>
              <div className="bg-surface-solid px-4 py-3">
                <div className="text-xs text-ink-3">检查点</div>
                <div className="mt-0.5 text-sm font-medium text-ink-2">{runRuntime.checkpoint}</div>
              </div>
              <div className="bg-surface-solid px-4 py-3">
                <div className="text-xs text-ink-3">租约过期</div>
                <div className="mt-0.5 text-sm font-medium text-ink-2">{runRuntime.leaseExpiresAt}</div>
              </div>
            </Card>
          ) : null}

          {/* Collapsible: Output */}
          <CollapsibleSection
            title="输出"
            expanded={outputExpanded}
            onToggle={() => setOutputExpanded((v) => !v)}
          >
            <pre className="max-h-72 overflow-auto rounded-xl border border-line bg-surface-solid p-3 text-sm text-ink-2">
              {detail ? JSON.stringify(detail.output ?? detail.error_message ?? detail.input, null, 2) : "请选择运行"}
            </pre>
          </CollapsibleSection>

          {/* Collapsible: Steps timeline */}
          <CollapsibleSection
            title="步骤时间线"
            count={detail?.steps.length}
            expanded={stepsExpanded}
            onToggle={() => setStepsExpanded((v) => !v)}
          >
            {detail?.steps.length ? (
              <div className="space-y-2">
                {detail.steps.map((step) => (
                  <div className="rounded-xl border border-line px-3 py-2.5 text-sm" key={step.id}>
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-medium text-ink-2">{step.node_name}</span>
                      <span className={`text-xs font-medium ${statusTextClass(step.status)}`}>{statusLabel(step.status)}</span>
                    </div>
                    <div className="mt-1 text-xs text-ink-3">
                      {statusLabel(step.node_type)} · 第 {step.attempt} 次尝试
                    </div>
                    {step.error_message ? <div className="mt-1 text-xs text-danger">{step.error_message}</div> : null}
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-sm text-ink-3">暂无步骤</div>
            )}
          </CollapsibleSection>

          {/* Collapsible: LLM calls */}
          <CollapsibleSection
            title="LLM 调用"
            count={detail?.llm_calls.length}
            expanded={llmExpanded}
            onToggle={() => setLlmExpanded((v) => !v)}
          >
            {detail ? (
              <div className="mb-2 rounded-xl border border-line bg-surface-solid px-3 py-2 text-sm">
                <div className="font-medium text-ink-2">Token 汇总</div>
                <div className="mt-1 text-xs text-ink-3">
                  输入 {runCost.promptTokens} · 输出 {runCost.completionTokens} · 耗时 {runCost.totalLatencyMs} ms
                </div>
              </div>
            ) : null}
            {detail?.llm_calls.length ? (
              <div className="space-y-2">
                {detail.llm_calls.map((call) => (
                  <div className="rounded-xl border border-line px-3 py-2.5 text-sm" key={call.id}>
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-medium text-ink-2">{call.model}</span>
                      <span className={`text-xs font-medium ${statusTextClass(call.status)}`}>{statusLabel(call.status)}</span>
                    </div>
                    <div className="mt-1 text-xs text-ink-3">
                      {call.total_tokens ?? 0} tokens · {call.latency_ms} ms
                    </div>
                    {call.error_message ? <div className="mt-1 text-xs text-danger">{call.error_message}</div> : null}
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-sm text-ink-3">暂无 LLM 调用</div>
            )}
          </CollapsibleSection>

          {/* Collapsible: Tool calls */}
          <CollapsibleSection
            title="工具调用"
            count={detail?.tool_calls.length}
            expanded={toolsExpanded}
            onToggle={() => setToolsExpanded((v) => !v)}
          >
            {detail?.tool_calls.length ? (
              <div className="space-y-2">
                {detail.tool_calls.map((call) => (
                  <div className="rounded-xl border border-line px-3 py-2.5 text-sm" key={call.id}>
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-medium text-ink-2">{call.tool_name}</span>
                      <span className={`text-xs font-medium ${statusTextClass(call.status)}`}>{statusLabel(call.status)}</span>
                    </div>
                    <div className="mt-1 text-xs text-ink-3">
                      {statusLabel(call.risk_level)} · {call.latency_ms} ms
                    </div>
                    {call.error_message ? <div className="mt-1 text-xs text-danger">{call.error_message}</div> : null}
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-sm text-ink-3">暂无工具调用</div>
            )}
          </CollapsibleSection>

          {/* Collapsible: Trace events */}
          <CollapsibleSection
            title="链路事件"
            count={detail?.trace_events.length}
            expanded={eventsExpanded}
            onToggle={() => setEventsExpanded((v) => !v)}
          >
            {detail?.trace_events.length ? (
              <div className="space-y-2">
                {detail.trace_events.map((event) => (
                  <div className="rounded-xl border border-line px-3 py-2.5 text-sm" key={event.id}>
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-medium text-ink-2">{event.event_type}</span>
                      <span className={event.severity === "error" ? "text-xs text-danger" : "text-xs text-ink-3"}>
                        {event.actor_type}
                      </span>
                    </div>
                    <div className="mt-1 text-xs text-ink-3">{event.message}</div>
                    <pre className="mt-2 max-h-28 overflow-auto rounded-lg bg-surface-solid p-2 text-[11px] text-ink-3">
                      {JSON.stringify(event.payload, null, 2)}
                    </pre>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-sm text-ink-3">暂无链路事件</div>
            )}
          </CollapsibleSection>
        </div>
      </section>
    </div>
  );
}

function CollapsibleSection({
  title,
  count,
  expanded,
  onToggle,
  children,
}: {
  title: string;
  count?: number;
  expanded: boolean;
  onToggle: () => void;
  children: ReactNode;
}) {
  return (
    <Card className="overflow-hidden">
      <button
        className="flex w-full items-center justify-between px-5 py-3.5 text-left transition-colors hover:bg-surface"
        onClick={onToggle}
        type="button"
      >
        <div className="flex items-center gap-2.5">
          {expanded ? (
            <ChevronDown size={15} className="text-ink-3" />
          ) : (
            <ChevronRight size={15} className="text-ink-3" />
          )}
          <span className="text-sm font-semibold text-ink">{title}</span>
          {count !== undefined ? (
            <span className="rounded-md bg-surface px-2 py-0.5 text-[11px] font-semibold text-ink-3">
              {count}
            </span>
          ) : null}
        </div>
      </button>
      {expanded ? (
        <div className="max-h-[480px] overflow-auto border-t border-line px-5 py-4">
          {children}
        </div>
      ) : null}
    </Card>
  );
}
