"use client";

import { useEffect, useMemo, useState } from "react";

import {
  type Approval,
  type WorkflowRun,
  approveApproval,
  executeRun,
  fetchApprovals,
  fetchRun,
  fetchRuns,
  formatRunCostSummary,
  rejectApproval,
  shouldPollRunStatus,
} from "@/lib/workflows";

export function RunsConsole() {
  const [runs, setRuns] = useState<WorkflowRun[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [detail, setDetail] = useState<WorkflowRun | null>(null);
  const [pendingApprovals, setPendingApprovals] = useState<Approval[]>([]);
  const [approvalComment, setApprovalComment] = useState("Reviewed for Phase 6 smoke.");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const selectedRun = useMemo(
    () => runs.find((run) => run.id === selectedRunId) ?? null,
    [runs, selectedRunId],
  );
  const runCost = useMemo(
    () => (detail ? formatRunCostSummary(detail) : { totalTokens: 0, promptTokens: 0, completionTokens: 0, totalLatencyMs: 0 }),
    [detail],
  );
  const selectedRunApprovals = detail?.approvals.filter((approval) => approval.status === "pending") ?? [];
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
    await runAction(async () => {
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
    await runAction(async () => {
      const run = await executeRun(selectedRunId);
      setDetail(run);
      setMessage(`Run ${run.status}`);
      const [nextRuns, approvals] = await Promise.all([fetchRuns(), fetchApprovals("pending")]);
      setRuns(nextRuns);
      setPendingApprovals(approvals);
    });
  }

  async function decideApproval(approvalId: string, decision: "approve" | "reject") {
    await runAction(async () => {
      const run =
        decision === "approve"
          ? await approveApproval(approvalId, approvalComment)
          : await rejectApproval(approvalId, approvalComment);
      setDetail(run);
      setSelectedRunId(run.id);
      setMessage(`Approval ${decision}d; run ${run.status}`);
      const [nextRuns, approvals] = await Promise.all([fetchRuns(), fetchApprovals("pending")]);
      setRuns(nextRuns);
      setPendingApprovals(approvals);
    });
  }

  async function runAction(action: () => Promise<void>) {
    try {
      setBusy(true);
      setMessage(null);
      await action();
    } catch (error) {
      setMessage(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <section className="border-b border-zinc-200 pb-5">
        <p className="text-xs font-semibold uppercase tracking-normal text-teal-700">Execution Trace</p>
        <div className="mt-2 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-zinc-950">Runs</h1>
            <p className="mt-1 text-sm text-zinc-500">Inspect workflow execution, steps, model/tool calls, and trace events.</p>
          </div>
          <div className="flex flex-wrap gap-2 text-xs">
            <StatusPill label="Runs" value={String(runs.length)} tone="neutral" />
            <StatusPill label="Approvals" value={String(pendingApprovals.length)} tone={pendingApprovals.length ? "warn" : "ready"} />
            <StatusPill label="Trace" value="Phase 6" tone="ready" />
          </div>
        </div>
      </section>

      {message ? (
        <div className="rounded-md border border-zinc-200 bg-white px-4 py-3 text-sm text-zinc-700">{message}</div>
      ) : null}

      <section className="grid gap-5 xl:grid-cols-[340px_minmax(0,1fr)]">
        <div className="rounded-lg border border-zinc-200 bg-white">
          <div className="flex items-center justify-between gap-3 border-b border-zinc-200 px-4 py-3">
            <div>
              <div className="text-sm font-semibold text-zinc-950">Run List</div>
              <div className="mt-1 text-xs text-zinc-500">{runs.length} recent runs</div>
            </div>
            <button className="control-button" disabled={busy} onClick={() => void loadRuns()} type="button">
              Refresh
            </button>
          </div>
          <div className="max-h-[720px] overflow-auto p-2">
            {runs.length === 0 ? (
              <div className="px-3 py-6 text-sm text-zinc-500">No runs yet</div>
            ) : (
              runs.map((run) => (
                <button
                  className={`mb-2 w-full rounded-md border px-3 py-3 text-left transition ${
                    selectedRunId === run.id
                      ? "border-teal-500 bg-teal-50 text-teal-950"
                      : "border-zinc-200 bg-white text-zinc-700 hover:border-zinc-300 hover:bg-zinc-50"
                  }`}
                  key={run.id}
                  onClick={() => setSelectedRunId(run.id)}
                  type="button"
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-sm font-medium">{shortId(run.id)}</span>
                    <span className={`text-xs ${statusClass(run.status)}`}>{run.status}</span>
                  </div>
                  <div className="mt-1 truncate text-xs text-zinc-500">
                    {String(run.input.topic ?? "No topic")} · {run.steps.length} steps
                  </div>
                </button>
              ))
            )}
          </div>
        </div>

        <div className="space-y-5">
          <section className="rounded-lg border border-zinc-200 bg-white p-5">
            <div className="flex flex-col gap-3 border-b border-zinc-200 pb-4 md:flex-row md:items-center md:justify-between">
              <div>
                <h2 className="text-base font-semibold text-zinc-950">{selectedRun ? shortId(selectedRun.id) : "Select a run"}</h2>
                <p className="mt-1 text-sm text-zinc-500">
                  {detail ? `${detail.status} · ${detail.workflow_version_id}` : "No run selected"}
                </p>
              </div>
              <button className="control-button primary" disabled={busy || !selectedRunId} onClick={handleExecute} type="button">
                Execute
              </button>
            </div>

            {detail ? (
              <div className="mt-5 grid gap-4 lg:grid-cols-4">
                <Metric label="Status" value={detail.status} />
                <Metric label="Steps" value={String(detail.steps.length)} />
                <Metric label="Tool Calls" value={String(detail.tool_calls.length)} />
                <Metric label="Tokens" value={String(runCost.totalTokens)} />
              </div>
            ) : null}

            {selectedRunApprovals.length ? (
              <div className="mt-5 rounded-md border border-amber-200 bg-amber-50 p-4">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <h3 className="text-sm font-semibold text-amber-950">Pending Approval</h3>
                    <p className="mt-1 text-sm text-amber-800">{selectedRunApprovals[0].title}</p>
                    <p className="mt-1 text-xs text-amber-700">{selectedRunApprovals[0].instructions}</p>
                  </div>
                  <span className="rounded-md border border-amber-300 px-2.5 py-1 text-xs font-semibold text-amber-800">
                    {selectedRunApprovals[0].risk_level}
                  </span>
                </div>
                <textarea
                  className="field-input mt-3 min-h-20 resize-y bg-white"
                  onChange={(event) => setApprovalComment(event.target.value)}
                  value={approvalComment}
                />
                <div className="mt-3 flex flex-wrap gap-2">
                  <button className="control-button primary" disabled={busy} onClick={() => void decideApproval(selectedRunApprovals[0].id, "approve")} type="button">
                    Approve
                  </button>
                  <button className="control-button" disabled={busy} onClick={() => void decideApproval(selectedRunApprovals[0].id, "reject")} type="button">
                    Reject
                  </button>
                </div>
              </div>
            ) : null}

            <div className="mt-5">
              <h3 className="text-sm font-semibold text-zinc-950">Output</h3>
              <pre className="mt-3 max-h-72 overflow-auto rounded-md border border-zinc-200 bg-zinc-50 p-3 text-sm text-zinc-700">
                {detail ? JSON.stringify(detail.output ?? detail.error_message ?? detail.input, null, 2) : "Select a run"}
              </pre>
            </div>
          </section>

          <section className="grid gap-5 xl:grid-cols-2">
            <Panel title="Step Timeline">
              {detail?.steps.length ? (
                detail.steps.map((step) => (
                  <div className="rounded-md border border-zinc-200 px-3 py-2 text-sm" key={step.id}>
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-medium text-zinc-800">{step.node_name}</span>
                      <span className={`text-xs ${statusClass(step.status)}`}>{step.status}</span>
                    </div>
                    <div className="mt-1 text-xs text-zinc-500">
                      {step.node_type} · attempt {step.attempt}
                    </div>
                    {step.error_message ? <div className="mt-1 text-xs text-rose-700">{step.error_message}</div> : null}
                  </div>
                ))
              ) : (
                <div className="text-sm text-zinc-500">No steps yet</div>
              )}
            </Panel>

            <Panel title="LLM Calls & Cost">
              {detail ? (
                <div className="rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2 text-sm">
                  <div className="font-medium text-zinc-800">Token Summary</div>
                  <div className="mt-1 text-xs text-zinc-500">
                    prompt {runCost.promptTokens} · completion {runCost.completionTokens} · latency {runCost.totalLatencyMs} ms
                  </div>
                </div>
              ) : null}
              {detail?.llm_calls.length ? (
                detail.llm_calls.map((call) => (
                  <div className="rounded-md border border-zinc-200 px-3 py-2 text-sm" key={call.id}>
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-medium text-zinc-800">{call.model}</span>
                      <span className={`text-xs ${statusClass(call.status)}`}>{call.status}</span>
                    </div>
                    <div className="mt-1 text-xs text-zinc-500">
                      {call.total_tokens ?? 0} tokens · {call.latency_ms} ms
                    </div>
                    {call.error_message ? <div className="mt-1 text-xs text-rose-700">{call.error_message}</div> : null}
                  </div>
                ))
              ) : (
                <div className="text-sm text-zinc-500">No LLM calls yet</div>
              )}
            </Panel>

            <Panel title="Tool Calls">
              {detail?.tool_calls.length ? (
                detail.tool_calls.map((call) => (
                  <div className="rounded-md border border-zinc-200 px-3 py-2 text-sm" key={call.id}>
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-medium text-zinc-800">{call.tool_name}</span>
                      <span className={`text-xs ${statusClass(call.status)}`}>{call.status}</span>
                    </div>
                    <div className="mt-1 text-xs text-zinc-500">
                      {call.risk_level} · {call.latency_ms} ms
                    </div>
                    {call.error_message ? <div className="mt-1 text-xs text-rose-700">{call.error_message}</div> : null}
                  </div>
                ))
              ) : (
                <div className="text-sm text-zinc-500">No tool calls yet</div>
              )}
            </Panel>
          </section>

          <Panel title="Trace Events">
            {detail?.trace_events.length ? (
              detail.trace_events.map((event) => (
                <div className="rounded-md border border-zinc-200 px-3 py-2 text-sm" key={event.id}>
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-medium text-zinc-800">{event.event_type}</span>
                    <span className={event.severity === "error" ? "text-xs text-rose-700" : "text-xs text-zinc-500"}>
                      {event.actor_type}
                    </span>
                  </div>
                  <div className="mt-1 text-xs text-zinc-500">{event.message}</div>
                  <pre className="mt-2 max-h-28 overflow-auto rounded bg-zinc-50 p-2 text-[11px] text-zinc-600">
                    {JSON.stringify(event.payload, null, 2)}
                  </pre>
                </div>
              ))
            ) : (
              <div className="text-sm text-zinc-500">No trace events yet</div>
            )}
          </Panel>
        </div>
      </section>
    </div>
  );
}

function Panel({ children, title }: { children: React.ReactNode; title: string }) {
  return (
    <section className="rounded-lg border border-zinc-200 bg-white p-4">
      <h2 className="text-base font-semibold text-zinc-950">{title}</h2>
      <div className="mt-4 max-h-[420px] space-y-2 overflow-auto">{children}</div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2">
      <div className="text-xs text-zinc-500">{label}</div>
      <div className="mt-1 text-lg font-semibold text-zinc-950">{value}</div>
    </div>
  );
}

function StatusPill({
  label,
  tone,
  value,
}: {
  label: string;
  tone: "neutral" | "ready" | "warn";
  value: string;
}) {
  const toneClassName =
    tone === "ready"
      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
      : tone === "warn"
        ? "border-amber-200 bg-amber-50 text-amber-700"
        : "border-zinc-200 bg-white text-zinc-600";
  return (
    <span className={`rounded-md border px-2.5 py-1 font-medium ${toneClassName}`}>
      {label}: {value}
    </span>
  );
}

function shortId(value: string): string {
  return value.slice(0, 8);
}

function statusClass(status: string): string {
  if (status === "succeeded") {
    return "text-emerald-700";
  }
  if (status === "failed" || status === "blocked") {
    return "text-rose-700";
  }
  if (status === "waiting_approval") {
    return "text-amber-700";
  }
  return "text-amber-700";
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Request failed";
}
