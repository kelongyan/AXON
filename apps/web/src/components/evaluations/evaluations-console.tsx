"use client";

import { type FormEvent, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import {
  type Evaluation,
  type EvaluationFormValues,
  createEvaluation,
  fetchEvaluations,
  runEvaluation,
  summarizeEvaluationResults,
} from "@/lib/evaluations";
import { type Workflow, fetchWorkflows } from "@/lib/workflows";
import { errorMessage } from "@/lib/error-message";
import { statusLabel } from "@/lib/status-label";
import { useRunAction } from "@/lib/use-run-action";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { GlassCard } from "@/components/ui/glass-card";
import { MessageBanner } from "@/components/ui/message-banner";
import { StatusPill } from "@/components/ui/status-pill";

const defaultCases = JSON.stringify(
  [
    { name: "AgentFlow 概览", input: { topic: "AgentFlow 阶段 6" }, expected: {} },
    { name: "审批行为", input: { topic: "审批工作流" }, expected: {} },
  ],
  null,
  2,
);

const defaultFormValues: EvaluationFormValues = {
  name: "阶段 6 冒烟评估",
  description: "针对固定输入批量运行已发布的工作流。",
  workflowId: "",
  tokenPricePer1k: "0.001",
  casesText: defaultCases,
};

function shortId(value: string): string {
  return value.slice(0, 8);
}

export function EvaluationsConsole() {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [evaluations, setEvaluations] = useState<Evaluation[]>([]);
  const [selectedEvaluationId, setSelectedEvaluationId] = useState<string | null>(null);
  const [formValues, setFormValues] = useState<EvaluationFormValues>(defaultFormValues);
  const { busy, message, run, setMessage } = useRunAction();

  const selectedEvaluation = useMemo(
    () => evaluations.find((evaluation) => evaluation.id === selectedEvaluationId) ?? evaluations[0] ?? null,
    [evaluations, selectedEvaluationId],
  );
  const resultSummary = selectedEvaluation
    ? summarizeEvaluationResults(selectedEvaluation.results)
    : { successCount: 0, failureCount: 0, totalTokens: 0, averageLatencyMs: 0 };

  useEffect(() => {
    void loadData();
  }, []);

  async function loadData() {
    await run(async () => {
      const [nextWorkflows, nextEvaluations] = await Promise.all([fetchWorkflows(), fetchEvaluations()]);
      setWorkflows(nextWorkflows);
      setEvaluations(nextEvaluations);
      setFormValues((current) => ({
        ...current,
        workflowId: current.workflowId || nextWorkflows.find((workflow) => workflow.current_version_id)?.id || "",
      }));
      setSelectedEvaluationId((current) => current ?? nextEvaluations[0]?.id ?? null);
    });
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await run(async () => {
      const evaluation = await createEvaluation(formValues);
      setMessage(`已创建 ${evaluation.name}`);
      const nextEvaluations = await fetchEvaluations();
      setEvaluations(nextEvaluations);
      setSelectedEvaluationId(evaluation.id);
    });
  }

  async function handleRun() {
    if (!selectedEvaluation) {
      return;
    }
    await run(async () => {
      const evaluation = await runEvaluation(selectedEvaluation.id);
      setMessage(`评估 ${statusLabel(evaluation.status)}`);
      const nextEvaluations = await fetchEvaluations();
      setEvaluations(nextEvaluations);
      setSelectedEvaluationId(evaluation.id);
    });
  }

  return (
    <div className="space-y-6">
      <section className="border-b border-line pb-5">
        <p className="text-xs font-semibold uppercase tracking-wide text-accent">评估</p>
        <div className="mt-2 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-ink">评估</h1>
            <p className="mt-1 text-sm text-ink-3">创建固定用例集，批量运行工作流并检视结果。</p>
          </div>
          <div className="flex flex-wrap gap-2 text-xs">
            <StatusPill label="用例集" value={String(evaluations.length)} tone="neutral" />
            <StatusPill label="批量" value="Phase 6" tone="success" />
            <StatusPill label="Token" value={String(resultSummary.totalTokens)} tone="success" />
          </div>
        </div>
      </section>

      {message ? <MessageBanner message={message} /> : null}

      <section className="grid gap-5 xl:grid-cols-[380px_minmax(0,1fr)]">
        <div className="space-y-5">
          <GlassCard as="form" className="space-y-4 p-4" onSubmit={handleCreate}>
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-base font-semibold text-ink">新建评估</h2>
              <Button variant="primary" disabled={busy || !formValues.workflowId} type="submit">
                创建
              </Button>
            </div>
            <Field label="Workflow">
              <select
                className="field-input"
                onChange={(event) => setFormValues({ ...formValues, workflowId: event.target.value })}
                value={formValues.workflowId}
              >
                <option value="">请选择已发布的工作流</option>
                {workflows.map((workflow) => (
                  <option disabled={!workflow.current_version_id} key={workflow.id} value={workflow.id}>
                    {workflow.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Name">
              <input
                className="field-input"
                onChange={(event) => setFormValues({ ...formValues, name: event.target.value })}
                value={formValues.name}
              />
            </Field>
            <Field label="Description">
              <textarea
                className="field-input min-h-20 resize-y"
                onChange={(event) => setFormValues({ ...formValues, description: event.target.value })}
                value={formValues.description}
              />
            </Field>
            <Field label="Token Price / 1K">
              <input
                className="field-input"
                onChange={(event) => setFormValues({ ...formValues, tokenPricePer1k: event.target.value })}
                value={formValues.tokenPricePer1k}
              />
            </Field>
            <Field label="Cases JSON">
              <textarea
                className="field-input min-h-64 resize-y font-mono"
                onChange={(event) => setFormValues({ ...formValues, casesText: event.target.value })}
                value={formValues.casesText}
              />
            </Field>
          </GlassCard>

          <GlassCard className="overflow-hidden">
            <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
              <div>
                <div className="text-sm font-semibold text-ink">评估列表</div>
                <div className="mt-1 text-xs text-ink-3">{evaluations.length} 个已配置</div>
              </div>
              <Button variant="default" disabled={busy} onClick={() => void loadData()} type="button">
                刷新
              </Button>
            </div>
            <div className="max-h-[360px] overflow-auto p-2">
              {evaluations.length === 0 ? (
                <div className="px-3 py-6 text-sm text-ink-3">暂无评估</div>
              ) : (
                evaluations.map((evaluation) => (
                  <button
                    className={`mb-2 w-full rounded-xl border px-3 py-3 text-left transition ${
                      selectedEvaluation?.id === evaluation.id
                        ? "border-accent bg-accent/10 text-accent"
                        : "border-line bg-surface-solid text-ink-2 hover:border-line-strong hover:bg-elevated"
                    }`}
                    key={evaluation.id}
                    onClick={() => setSelectedEvaluationId(evaluation.id)}
                    type="button"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-sm font-medium">{evaluation.name}</span>
                      <span className="text-xs">{statusLabel(evaluation.status)}</span>
                    </div>
                    <div className="mt-1 text-xs text-ink-3">
                      {String(evaluation.summary.case_count ?? evaluation.cases.length)} 个用例 · {String(evaluation.summary.success_count ?? 0)} 个通过
                    </div>
                  </button>
                ))
              )}
            </div>
          </GlassCard>
        </div>

        <div className="space-y-5">
          <GlassCard className="p-5">
            <div className="flex flex-col gap-3 border-b border-line pb-4 md:flex-row md:items-center md:justify-between">
              <div>
                <h2 className="text-base font-semibold text-ink">{selectedEvaluation?.name ?? "请选择评估"}</h2>
                <p className="mt-1 text-sm text-ink-3">
                  {selectedEvaluation ? `${statusLabel(selectedEvaluation.status)} · ${selectedEvaluation.workflow_id}` : "未选择评估"}
                </p>
              </div>
              <Button variant="primary" disabled={busy || !selectedEvaluation} onClick={handleRun} type="button">
                运行批次
              </Button>
            </div>
            <div className="mt-5 grid gap-4 md:grid-cols-4">
              <Metric label="用例" value={String(selectedEvaluation?.summary.case_count ?? selectedEvaluation?.cases.length ?? 0)} />
              <Metric label="成功" value={String(resultSummary.successCount || selectedEvaluation?.summary.success_count || 0)} />
              <Metric label="失败" value={String(resultSummary.failureCount || selectedEvaluation?.summary.failure_count || 0)} />
              <Metric label="平均延迟" value={`${resultSummary.averageLatencyMs} ms`} />
            </div>
          </GlassCard>

          <section className="grid gap-5 xl:grid-cols-2">
            <Panel title="用例">
              {selectedEvaluation?.cases.length ? (
                selectedEvaluation.cases.map((item) => (
                  <div className="rounded-xl border border-line px-3 py-2 text-sm" key={item.id}>
                    <div className="font-medium text-ink-2">{item.ordinal}. {item.name}</div>
                    <pre className="mt-2 max-h-28 overflow-auto rounded-lg bg-surface-solid p-2 text-[11px] text-ink-3">
                      {JSON.stringify(item.input, null, 2)}
                    </pre>
                  </div>
                ))
              ) : (
                <div className="text-sm text-ink-3">暂无用例</div>
              )}
            </Panel>

            <Panel title="结果">
              {selectedEvaluation?.results.length ? (
                selectedEvaluation.results.map((result) => (
                  <div className="rounded-xl border border-line px-3 py-2 text-sm" key={result.id}>
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-medium text-ink-2">{result.run_id ? shortId(result.run_id) : "No run"}</span>
                      <span className={result.status === "succeeded" ? "text-xs text-success" : "text-xs text-danger"}>
                        {statusLabel(result.status)}
                      </span>
                    </div>
                    <div className="mt-1 text-xs text-ink-3">
                      {result.total_tokens} tokens · {result.latency_ms} ms
                    </div>
                    <pre className="mt-2 max-h-32 overflow-auto rounded-lg bg-surface-solid p-2 text-[11px] text-ink-3">
                      {JSON.stringify(result.output ?? result.error_message, null, 2)}
                    </pre>
                  </div>
                ))
              ) : (
                <div className="text-sm text-ink-3">暂无结果</div>
              )}
            </Panel>
          </section>
        </div>
      </section>
    </div>
  );
}

function Panel({ children, title }: { children: ReactNode; title: string }) {
  return (
    <GlassCard className="p-4">
      <h2 className="text-base font-semibold text-ink">{title}</h2>
      <div className="mt-4 max-h-[520px] space-y-2 overflow-auto">{children}</div>
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
