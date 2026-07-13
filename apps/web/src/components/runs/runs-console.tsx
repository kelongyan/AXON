"use client";

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
import { GlassCard } from "@/components/ui/glass-card";
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
    <div className="space-y-6">
      <section className="border-b border-line pb-5">
        <p className="text-xs font-semibold uppercase tracking-wide text-accent">执行链路追踪</p>
        <div className="mt-2 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-ink">运行记录</h1>
            <p className="mt-1 text-sm text-ink-3">查看工作流执行过程、步骤、模型/工具调用与链路事件。</p>
          </div>
          <div className="flex flex-wrap gap-2 text-xs">
            <StatusPill label="运行记录" value={String(runs.length)} tone="neutral" />
            <StatusPill label="待审批" value={String(pendingApprovals.length)} tone={pendingApprovals.length ? "warning" : "success"} />
            <StatusPill label="链路" value="Phase 6" tone="success" />
          </div>
        </div>
      </section>

      {message ? <MessageBanner message={message} /> : null}

      <section className="grid gap-5 xl:grid-cols-[340px_minmax(0,1fr)]">
        <GlassCard className="overflow-hidden">
          <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
            <div>
              <div className="text-sm font-semibold text-ink">运行列表</div>
              <div className="mt-1 text-xs text-ink-3">{runs.length} 条近期运行</div>
            </div>
            <Button variant="default" disabled={busy} onClick={() => void loadRuns()} type="button">
              刷新
            </Button>
          </div>
          <div className="max-h-[720px] overflow-auto p-2">
            {runs.length === 0 ? (
              <div className="px-3 py-6 text-sm text-ink-3">暂无运行记录</div>
            ) : (
              runs.map((run) => (
                <button
                  className={`mb-2 w-full rounded-xl border px-3 py-3 text-left transition ${
                    selectedRunId === run.id
                      ? "border-accent bg-accent/10 text-accent"
                      : "border-line bg-surface-solid text-ink-2 hover:border-line-strong hover:bg-elevated"
                  }`}
                  key={run.id}
                  onClick={() => setSelectedRunId(run.id)}
                  type="button"
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-sm font-medium">{shortId(run.id)}</span>
                    <span className={`text-xs ${statusTextClass(run.status)}`}>{statusLabel(run.status)}</span>
                  </div>
                  <div className="mt-1 truncate text-xs text-ink-3">
                    {String(run.input.topic ?? "No topic")} · {run.steps.length} steps
                  </div>
                </button>
              ))
            )}
          </div>
        </GlassCard>

        <div className="space-y-5">
          <GlassCard className="p-5">
            <div className="flex flex-col gap-3 border-b border-line pb-4 md:flex-row md:items-center md:justify-between">
              <div>
                <h2 className="text-base font-semibold text-ink">{selectedRun ? shortId(selectedRun.id) : "请选择运行"}</h2>
                <p className="mt-1 text-sm text-ink-3">
                  {detail ? `${statusLabel(detail.status)} · ${detail.workflow_version_id}` : "未选择运行"}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                {canCancelSelectedRun ? (
                  <Button variant="default" disabled={busy || !selectedRunId} onClick={handleCancel} type="button">
                    取消
                  </Button>
                ) : null}
                <Button variant="primary" disabled={busy || !selectedRunId} onClick={handleExecute} type="button">
                  执行
                </Button>
              </div>
            </div>

            {detail ? (
              <>
                <div className="mt-5 grid gap-4 lg:grid-cols-4">
                  <Metric label="状态" value={statusLabel(detail.status)} />
                  <Metric label="步骤" value={String(detail.steps.length)} />
                  <Metric label="工具调用" value={String(detail.tool_calls.length)} />
                  <Metric label="Token" value={String(runCost.totalTokens)} />
                </div>
                <div className="mt-4 grid gap-3 lg:grid-cols-3">
                  <RuntimeMetric label="执行节点" value={runRuntime.worker} />
                  <RuntimeMetric label="检查点" value={runRuntime.checkpoint} />
                  <RuntimeMetric label="租约过期" value={runRuntime.leaseExpiresAt} />
                </div>
              </>
            ) : null}

            {selectedRunApprovals.length ? (
              <div className="mt-5 rounded-xl border border-warning/30 bg-warning/10 p-4">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <h3 className="text-sm font-semibold text-warning">待审批</h3>
                    <p className="mt-1 text-sm text-ink-2">{selectedRunApprovals[0].title}</p>
                    <p className="mt-1 text-xs text-ink-3">{selectedRunApprovals[0].instructions}</p>
                  </div>
                  <span className="rounded-md border border-warning/40 px-2.5 py-1 text-xs font-semibold text-warning">
                    {statusLabel(selectedRunApprovals[0].risk_level)}
                  </span>
                </div>
                <textarea
                  className="field-input mt-3 min-h-20 resize-y bg-surface-solid"
                  onChange={(event) => setApprovalComment(event.target.value)}
                  value={approvalComment}
                />
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
                    variant="default"
                    disabled={busy}
                    onClick={() => void decideApproval(selectedRunApprovals[0].id, "reject")}
                    type="button"
                  >
                    驳回
                  </Button>
                </div>
              </div>
            ) : null}

            <div className="mt-5">
              <h3 className="text-sm font-semibold text-ink">输出</h3>
              <pre className="mt-3 max-h-72 overflow-auto rounded-xl border border-line bg-surface-solid p-3 text-sm text-ink-2">
                {detail ? JSON.stringify(detail.output ?? detail.error_message ?? detail.input, null, 2) : "请选择运行"}
              </pre>
            </div>
          </GlassCard>

          <section className="grid gap-5 xl:grid-cols-2">
            <Panel title="步骤时间线">
              {detail?.steps.length ? (
                detail.steps.map((step) => (
                  <div className="rounded-xl border border-line px-3 py-2 text-sm" key={step.id}>
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-medium text-ink-2">{step.node_name}</span>
                      <span className={`text-xs ${statusTextClass(step.status)}`}>{statusLabel(step.status)}</span>
                    </div>
                    <div className="mt-1 text-xs text-ink-3">
                      {statusLabel(step.node_type)} · 第 {step.attempt} 次尝试
                    </div>
                    {step.error_message ? <div className="mt-1 text-xs text-danger">{step.error_message}</div> : null}
                  </div>
                ))
              ) : (
                <div className="text-sm text-ink-3">暂无步骤</div>
              )}
            </Panel>

            <Panel title="LLM 调用与成本">
              {detail ? (
                <div className="rounded-xl border border-line bg-surface-solid px-3 py-2 text-sm">
                  <div className="font-medium text-ink-2">Token 汇总</div>
                  <div className="mt-1 text-xs text-ink-3">
                    输入 {runCost.promptTokens} · 输出 {runCost.completionTokens} · 耗时 {runCost.totalLatencyMs} ms
                  </div>
                </div>
              ) : null}
              {detail?.llm_calls.length ? (
                detail.llm_calls.map((call) => (
                  <div className="rounded-xl border border-line px-3 py-2 text-sm" key={call.id}>
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-medium text-ink-2">{call.model}</span>
                      <span className={`text-xs ${statusTextClass(call.status)}`}>{statusLabel(call.status)}</span>
                    </div>
                    <div className="mt-1 text-xs text-ink-3">
                      {call.total_tokens ?? 0} tokens · {call.latency_ms} ms
                    </div>
                    {call.error_message ? <div className="mt-1 text-xs text-danger">{call.error_message}</div> : null}
                  </div>
                ))
              ) : (
                <div className="text-sm text-ink-3">暂无 LLM 调用</div>
              )}
            </Panel>

            <Panel title="工具调用">
              {detail?.tool_calls.length ? (
                detail.tool_calls.map((call) => (
                  <div className="rounded-xl border border-line px-3 py-2 text-sm" key={call.id}>
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-medium text-ink-2">{call.tool_name}</span>
                      <span className={`text-xs ${statusTextClass(call.status)}`}>{statusLabel(call.status)}</span>
                    </div>
                    <div className="mt-1 text-xs text-ink-3">
                      {statusLabel(call.risk_level)} · {call.latency_ms} ms
                    </div>
                    {call.error_message ? <div className="mt-1 text-xs text-danger">{call.error_message}</div> : null}
                  </div>
                ))
              ) : (
                <div className="text-sm text-ink-3">暂无工具调用</div>
              )}
            </Panel>
          </section>

          <Panel title="链路事件">
            {detail?.trace_events.length ? (
              detail.trace_events.map((event) => (
                <div className="rounded-xl border border-line px-3 py-2 text-sm" key={event.id}>
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
              ))
            ) : (
              <div className="text-sm text-ink-3">暂无链路事件</div>
            )}
          </Panel>
        </div>
      </section>
    </div>
  );
}

function Panel({ children, title }: { children: ReactNode; title: string }) {
  return (
    <GlassCard className="p-4">
      <h2 className="text-base font-semibold text-ink">{title}</h2>
      <div className="mt-4 max-h-[420px] space-y-2 overflow-auto">{children}</div>
    </GlassCard>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-line bg-surface-solid px-3 py-2">
      <div className="text-xs text-ink-3">{label}</div>
      <div className="mt-1 text-lg font-semibold text-ink">{value}</div>
    </div>
  );
}

function RuntimeMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-line bg-surface-solid px-3 py-2">
      <div className="text-xs text-ink-3">{label}</div>
      <div className="mt-1 break-all text-sm font-medium text-ink-2">{value}</div>
    </div>
  );
}
