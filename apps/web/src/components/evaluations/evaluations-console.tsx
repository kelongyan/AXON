"use client";

import { type FormEvent, useEffect, useMemo, useState } from "react";

import {
  type Evaluation,
  type EvaluationFormValues,
  createEvaluation,
  fetchEvaluations,
  runEvaluation,
  summarizeEvaluationResults,
} from "@/lib/evaluations";
import { type Workflow, fetchWorkflows } from "@/lib/workflows";

const defaultCases = JSON.stringify(
  [
    { name: "AgentFlow overview", input: { topic: "AgentFlow Phase 6" }, expected: {} },
    { name: "Approval behavior", input: { topic: "Approval workflow" }, expected: {} },
  ],
  null,
  2,
);

const defaultFormValues: EvaluationFormValues = {
  name: "Phase 6 Smoke Evaluation",
  description: "Batch run a published workflow against fixed inputs.",
  workflowId: "",
  tokenPricePer1k: "0.001",
  casesText: defaultCases,
};

export function EvaluationsConsole() {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [evaluations, setEvaluations] = useState<Evaluation[]>([]);
  const [selectedEvaluationId, setSelectedEvaluationId] = useState<string | null>(null);
  const [formValues, setFormValues] = useState<EvaluationFormValues>(defaultFormValues);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

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
    await runAction(async () => {
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
    await runAction(async () => {
      const evaluation = await createEvaluation(formValues);
      setMessage(`Created ${evaluation.name}`);
      const nextEvaluations = await fetchEvaluations();
      setEvaluations(nextEvaluations);
      setSelectedEvaluationId(evaluation.id);
    });
  }

  async function handleRun() {
    if (!selectedEvaluation) {
      return;
    }
    await runAction(async () => {
      const evaluation = await runEvaluation(selectedEvaluation.id);
      setMessage(`Evaluation ${evaluation.status}`);
      const nextEvaluations = await fetchEvaluations();
      setEvaluations(nextEvaluations);
      setSelectedEvaluationId(evaluation.id);
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
        <p className="text-xs font-semibold uppercase tracking-normal text-teal-700">Evaluation</p>
        <div className="mt-2 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-zinc-950">Evaluations</h1>
            <p className="mt-1 text-sm text-zinc-500">Create fixed case sets, batch run workflows, and inspect results.</p>
          </div>
          <div className="flex flex-wrap gap-2 text-xs">
            <StatusPill label="Sets" value={String(evaluations.length)} tone="neutral" />
            <StatusPill label="Batch" value="Phase 6" tone="ready" />
            <StatusPill label="Tokens" value={String(resultSummary.totalTokens)} tone="ready" />
          </div>
        </div>
      </section>

      {message ? (
        <div className="rounded-md border border-zinc-200 bg-white px-4 py-3 text-sm text-zinc-700">{message}</div>
      ) : null}

      <section className="grid gap-5 xl:grid-cols-[380px_minmax(0,1fr)]">
        <div className="space-y-5">
          <form className="rounded-lg border border-zinc-200 bg-white p-4" onSubmit={handleCreate}>
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-base font-semibold text-zinc-950">New Evaluation</h2>
              <button className="control-button primary" disabled={busy || !formValues.workflowId} type="submit">
                Create
              </button>
            </div>
            <Field className="mt-4" label="Workflow">
              <select
                className="field-input"
                onChange={(event) => setFormValues({ ...formValues, workflowId: event.target.value })}
                value={formValues.workflowId}
              >
                <option value="">Select published workflow</option>
                {workflows.map((workflow) => (
                  <option disabled={!workflow.current_version_id} key={workflow.id} value={workflow.id}>
                    {workflow.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field className="mt-4" label="Name">
              <input
                className="field-input"
                onChange={(event) => setFormValues({ ...formValues, name: event.target.value })}
                value={formValues.name}
              />
            </Field>
            <Field className="mt-4" label="Description">
              <textarea
                className="field-input min-h-20 resize-y"
                onChange={(event) => setFormValues({ ...formValues, description: event.target.value })}
                value={formValues.description}
              />
            </Field>
            <Field className="mt-4" label="Token Price / 1K">
              <input
                className="field-input"
                onChange={(event) => setFormValues({ ...formValues, tokenPricePer1k: event.target.value })}
                value={formValues.tokenPricePer1k}
              />
            </Field>
            <Field className="mt-4" label="Cases JSON">
              <textarea
                className="field-input min-h-64 resize-y font-mono"
                onChange={(event) => setFormValues({ ...formValues, casesText: event.target.value })}
                value={formValues.casesText}
              />
            </Field>
          </form>

          <div className="rounded-lg border border-zinc-200 bg-white">
            <div className="flex items-center justify-between gap-3 border-b border-zinc-200 px-4 py-3">
              <div>
                <div className="text-sm font-semibold text-zinc-950">Evaluation List</div>
                <div className="mt-1 text-xs text-zinc-500">{evaluations.length} configured</div>
              </div>
              <button className="control-button" disabled={busy} onClick={() => void loadData()} type="button">
                Refresh
              </button>
            </div>
            <div className="max-h-[360px] overflow-auto p-2">
              {evaluations.length === 0 ? (
                <div className="px-3 py-6 text-sm text-zinc-500">No evaluations yet</div>
              ) : (
                evaluations.map((evaluation) => (
                  <button
                    className={`mb-2 w-full rounded-md border px-3 py-3 text-left transition ${
                      selectedEvaluation?.id === evaluation.id
                        ? "border-teal-500 bg-teal-50 text-teal-950"
                        : "border-zinc-200 bg-white text-zinc-700 hover:border-zinc-300 hover:bg-zinc-50"
                    }`}
                    key={evaluation.id}
                    onClick={() => setSelectedEvaluationId(evaluation.id)}
                    type="button"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-sm font-medium">{evaluation.name}</span>
                      <span className="text-xs capitalize">{evaluation.status}</span>
                    </div>
                    <div className="mt-1 text-xs text-zinc-500">
                      {String(evaluation.summary.case_count ?? evaluation.cases.length)} cases · {String(evaluation.summary.success_count ?? 0)} passed
                    </div>
                  </button>
                ))
              )}
            </div>
          </div>
        </div>

        <div className="space-y-5">
          <section className="rounded-lg border border-zinc-200 bg-white p-5">
            <div className="flex flex-col gap-3 border-b border-zinc-200 pb-4 md:flex-row md:items-center md:justify-between">
              <div>
                <h2 className="text-base font-semibold text-zinc-950">{selectedEvaluation?.name ?? "Select an evaluation"}</h2>
                <p className="mt-1 text-sm text-zinc-500">
                  {selectedEvaluation ? `${selectedEvaluation.status} · ${selectedEvaluation.workflow_id}` : "No evaluation selected"}
                </p>
              </div>
              <button className="control-button primary" disabled={busy || !selectedEvaluation} onClick={handleRun} type="button">
                Run Batch
              </button>
            </div>
            <div className="mt-5 grid gap-4 md:grid-cols-4">
              <Metric label="Cases" value={String(selectedEvaluation?.summary.case_count ?? selectedEvaluation?.cases.length ?? 0)} />
              <Metric label="Succeeded" value={String(resultSummary.successCount || selectedEvaluation?.summary.success_count || 0)} />
              <Metric label="Failed" value={String(resultSummary.failureCount || selectedEvaluation?.summary.failure_count || 0)} />
              <Metric label="Avg Latency" value={`${resultSummary.averageLatencyMs} ms`} />
            </div>
          </section>

          <section className="grid gap-5 xl:grid-cols-2">
            <Panel title="Cases">
              {selectedEvaluation?.cases.length ? (
                selectedEvaluation.cases.map((item) => (
                  <div className="rounded-md border border-zinc-200 px-3 py-2 text-sm" key={item.id}>
                    <div className="font-medium text-zinc-800">{item.ordinal}. {item.name}</div>
                    <pre className="mt-2 max-h-28 overflow-auto rounded bg-zinc-50 p-2 text-[11px] text-zinc-600">
                      {JSON.stringify(item.input, null, 2)}
                    </pre>
                  </div>
                ))
              ) : (
                <div className="text-sm text-zinc-500">No cases</div>
              )}
            </Panel>

            <Panel title="Results">
              {selectedEvaluation?.results.length ? (
                selectedEvaluation.results.map((result) => (
                  <div className="rounded-md border border-zinc-200 px-3 py-2 text-sm" key={result.id}>
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-medium text-zinc-800">{result.run_id ? shortId(result.run_id) : "No run"}</span>
                      <span className={result.status === "succeeded" ? "text-xs text-emerald-700" : "text-xs text-rose-700"}>
                        {result.status}
                      </span>
                    </div>
                    <div className="mt-1 text-xs text-zinc-500">
                      {result.total_tokens} tokens · {result.latency_ms} ms
                    </div>
                    <pre className="mt-2 max-h-32 overflow-auto rounded bg-zinc-50 p-2 text-[11px] text-zinc-600">
                      {JSON.stringify(result.output ?? result.error_message, null, 2)}
                    </pre>
                  </div>
                ))
              ) : (
                <div className="text-sm text-zinc-500">No results yet</div>
              )}
            </Panel>
          </section>
        </div>
      </section>
    </div>
  );
}

function Field({
  children,
  className = "",
  label,
}: {
  children: React.ReactNode;
  className?: string;
  label: string;
}) {
  return (
    <label className={`block ${className}`}>
      <span className="text-xs font-semibold uppercase tracking-normal text-zinc-500">{label}</span>
      <div className="mt-1">{children}</div>
    </label>
  );
}

function Panel({ children, title }: { children: React.ReactNode; title: string }) {
  return (
    <section className="rounded-lg border border-zinc-200 bg-white p-4">
      <h2 className="text-base font-semibold text-zinc-950">{title}</h2>
      <div className="mt-4 max-h-[520px] space-y-2 overflow-auto">{children}</div>
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
  tone: "neutral" | "ready";
  value: string;
}) {
  const toneClassName =
    tone === "ready" ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-zinc-200 bg-white text-zinc-600";
  return (
    <span className={`rounded-md border px-2.5 py-1 font-medium ${toneClassName}`}>
      {label}: {value}
    </span>
  );
}

function shortId(value: string): string {
  return value.slice(0, 8);
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Request failed";
}
