"use client";

import { type FormEvent, type ReactNode, useEffect, useMemo, useState } from "react";

import {
  type Agent,
  type AgentDetail,
  type AgentFormValues,
  type AgentTestRun,
  type MeContext,
  cloneAgent,
  createAgent,
  disableAgent,
  fetchAgent,
  fetchAgents,
  fetchMe,
  publishAgentVersion,
  runAgentTest,
} from "@/lib/agents";

const defaultFormValues: AgentFormValues = {
  name: "",
  description: "",
  rolePrompt: "You are a focused assistant.",
  systemPrompt: "Answer with concise, structured Markdown.",
  modelName: "gpt-4.1-mini",
  temperature: "0.2",
  maxOutputTokens: "1000",
};

export function AgentsConsole() {
  const [context, setContext] = useState<MeContext | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [detail, setDetail] = useState<AgentDetail | null>(null);
  const [formValues, setFormValues] = useState<AgentFormValues>(defaultFormValues);
  const [testInput, setTestInput] = useState("Summarize what this Agent should do.");
  const [testRun, setTestRun] = useState<AgentTestRun | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const selectedAgent = useMemo(
    () => agents.find((agent) => agent.id === selectedAgentId) ?? null,
    [agents, selectedAgentId],
  );

  useEffect(() => {
    void loadInitialData();
  }, []);

  useEffect(() => {
    if (selectedAgentId) {
      void loadAgentDetail(selectedAgentId);
    } else {
      setDetail(null);
    }
  }, [selectedAgentId]);

  async function loadInitialData() {
    try {
      setBusy(true);
      const [nextContext, nextAgents] = await Promise.all([fetchMe(), fetchAgents()]);
      setContext(nextContext);
      setAgents(nextAgents);
      if (!selectedAgentId && nextAgents[0]) {
        setSelectedAgentId(nextAgents[0].id);
      }
    } catch (error) {
      setMessage(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  async function reloadAgents(selectAgentId?: string) {
    const nextAgents = await fetchAgents();
    setAgents(nextAgents);
    if (selectAgentId) {
      setSelectedAgentId(selectAgentId);
      return;
    }
    if (selectedAgentId && nextAgents.some((agent) => agent.id === selectedAgentId)) {
      return;
    }
    setSelectedAgentId(nextAgents[0]?.id ?? null);
  }

  async function loadAgentDetail(agentId: string) {
    try {
      const nextDetail = await fetchAgent(agentId);
      setDetail(nextDetail);
      populateForm(nextDetail);
    } catch (error) {
      setMessage(errorMessage(error));
    }
  }

  function populateForm(agent: AgentDetail) {
    const current = agent.current_version;
    setFormValues({
      name: agent.name,
      description: agent.description,
      rolePrompt: current?.role_prompt ?? defaultFormValues.rolePrompt,
      systemPrompt: current?.system_prompt ?? defaultFormValues.systemPrompt,
      modelName: current?.model_name ?? defaultFormValues.modelName,
      temperature: String(current?.temperature ?? defaultFormValues.temperature),
      maxOutputTokens: String(current?.max_output_tokens ?? defaultFormValues.maxOutputTokens),
    });
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await runAction(async () => {
      const created = await createAgent(formValues);
      setMessage(`Created ${created.name}`);
      setTestRun(null);
      await reloadAgents(created.id);
    });
  }

  async function handlePublishVersion() {
    if (!selectedAgentId) {
      return;
    }
    await runAction(async () => {
      await publishAgentVersion(selectedAgentId, formValues);
      setMessage("Published new Agent version");
      await loadAgentDetail(selectedAgentId);
      await reloadAgents(selectedAgentId);
    });
  }

  async function handleClone() {
    if (!selectedAgentId) {
      return;
    }
    await runAction(async () => {
      const cloned = await cloneAgent(selectedAgentId);
      setMessage(`Cloned ${cloned.name}`);
      await reloadAgents(cloned.id);
    });
  }

  async function handleDisable() {
    if (!selectedAgentId) {
      return;
    }
    await runAction(async () => {
      await disableAgent(selectedAgentId);
      setMessage("Agent disabled");
      await loadAgentDetail(selectedAgentId);
      await reloadAgents(selectedAgentId);
    });
  }

  async function handleTestRun() {
    if (!selectedAgentId) {
      return;
    }
    await runAction(async () => {
      const result = await runAgentTest(selectedAgentId, testInput);
      setTestRun(result);
      setMessage("Test run finished");
      await loadAgentDetail(selectedAgentId);
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
        <p className="text-xs font-semibold uppercase tracking-normal text-teal-700">Agent Registry</p>
        <div className="mt-2 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-zinc-950">Agents</h1>
            <p className="mt-1 text-sm text-zinc-500">
              {context ? `${context.workspace.name} · ${context.user.display_name}` : "Loading workspace"}
            </p>
          </div>
          <div className="flex flex-wrap gap-2 text-xs">
            <StatusPill label="Phase" value="1" tone="ready" />
            <StatusPill label="Provider" value="OpenAI API" tone="ready" />
            <StatusPill label="Local inference" value="Off" tone="neutral" />
          </div>
        </div>
      </section>

      {message ? (
        <div className="rounded-md border border-zinc-200 bg-white px-4 py-3 text-sm text-zinc-700">{message}</div>
      ) : null}

      <section className="grid gap-5 xl:grid-cols-[280px_minmax(0,1fr)_360px]">
        <div className="rounded-lg border border-zinc-200 bg-white">
          <div className="border-b border-zinc-200 px-4 py-3">
            <div className="text-sm font-semibold text-zinc-950">Agent List</div>
            <div className="mt-1 text-xs text-zinc-500">{agents.length} configured</div>
          </div>
          <div className="max-h-[620px] overflow-auto p-2">
            {agents.length === 0 ? (
              <div className="px-3 py-6 text-sm text-zinc-500">No agents yet</div>
            ) : (
              agents.map((agent) => (
                <button
                  className={`mb-2 w-full rounded-md border px-3 py-3 text-left transition ${
                    selectedAgentId === agent.id
                      ? "border-teal-500 bg-teal-50 text-teal-950"
                      : "border-zinc-200 bg-white text-zinc-700 hover:border-zinc-300 hover:bg-zinc-50"
                  }`}
                  key={agent.id}
                  onClick={() => setSelectedAgentId(agent.id)}
                  type="button"
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-sm font-medium">{agent.name}</span>
                    <span className="text-xs capitalize">{agent.status}</span>
                  </div>
                  <div className="mt-1 text-xs text-zinc-500">
                    v{agent.current_version?.version_number ?? "-"} · {agent.current_version?.model_name ?? "No model"}
                  </div>
                </button>
              ))
            )}
          </div>
        </div>

        <form className="rounded-lg border border-zinc-200 bg-white p-5" onSubmit={handleCreate}>
          <div className="flex flex-col gap-3 border-b border-zinc-200 pb-4 md:flex-row md:items-center md:justify-between">
            <div>
              <h2 className="text-base font-semibold text-zinc-950">Configuration</h2>
              <p className="mt-1 text-sm text-zinc-500">{selectedAgent?.name ?? "New Agent"}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button className="control-button primary" disabled={busy} type="submit">
                Create
              </button>
              <button className="control-button" disabled={busy || !selectedAgentId} onClick={handlePublishVersion} type="button">
                Publish Version
              </button>
            </div>
          </div>

          <div className="mt-5 grid gap-4 md:grid-cols-2">
            <Field label="Name">
              <input
                className="field-input"
                onChange={(event) => setFormValues({ ...formValues, name: event.target.value })}
                value={formValues.name}
              />
            </Field>
            <Field label="Model">
              <input
                className="field-input"
                onChange={(event) => setFormValues({ ...formValues, modelName: event.target.value })}
                value={formValues.modelName}
              />
            </Field>
            <Field label="Temperature">
              <input
                className="field-input"
                max="2"
                min="0"
                onChange={(event) => setFormValues({ ...formValues, temperature: event.target.value })}
                step="0.1"
                type="number"
                value={formValues.temperature}
              />
            </Field>
            <Field label="Max Output Tokens">
              <input
                className="field-input"
                min="1"
                onChange={(event) => setFormValues({ ...formValues, maxOutputTokens: event.target.value })}
                type="number"
                value={formValues.maxOutputTokens}
              />
            </Field>
            <Field className="md:col-span-2" label="Description">
              <input
                className="field-input"
                onChange={(event) => setFormValues({ ...formValues, description: event.target.value })}
                value={formValues.description}
              />
            </Field>
            <Field className="md:col-span-2" label="Role Prompt">
              <textarea
                className="field-input min-h-28 resize-y"
                onChange={(event) => setFormValues({ ...formValues, rolePrompt: event.target.value })}
                value={formValues.rolePrompt}
              />
            </Field>
            <Field className="md:col-span-2" label="System Prompt">
              <textarea
                className="field-input min-h-32 resize-y"
                onChange={(event) => setFormValues({ ...formValues, systemPrompt: event.target.value })}
                value={formValues.systemPrompt}
              />
            </Field>
          </div>
        </form>

        <div className="space-y-5">
          <section className="rounded-lg border border-zinc-200 bg-white p-4">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-base font-semibold text-zinc-950">Test Run</h2>
              <button className="control-button primary" disabled={busy || !selectedAgentId} onClick={handleTestRun} type="button">
                Run
              </button>
            </div>
            <textarea
              className="field-input mt-4 min-h-28 resize-y"
              onChange={(event) => setTestInput(event.target.value)}
              value={testInput}
            />
            {testRun ? (
              <div className="mt-4 rounded-md border border-emerald-200 bg-emerald-50 p-3">
                <div className="text-xs font-semibold uppercase tracking-normal text-emerald-700">Output</div>
                <pre className="mt-2 whitespace-pre-wrap text-sm text-emerald-950">{testRun.output}</pre>
                <div className="mt-3 text-xs text-emerald-700">
                  {testRun.llm_call.model} · {testRun.llm_call.total_tokens ?? 0} tokens · {testRun.llm_call.latency_ms} ms
                </div>
              </div>
            ) : null}
          </section>

          <section className="rounded-lg border border-zinc-200 bg-white p-4">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-base font-semibold text-zinc-950">Lifecycle</h2>
              <div className="flex gap-2">
                <button className="control-button" disabled={busy || !selectedAgentId} onClick={handleClone} type="button">
                  Clone
                </button>
                <button className="control-button danger" disabled={busy || !selectedAgentId} onClick={handleDisable} type="button">
                  Disable
                </button>
              </div>
            </div>
            <div className="mt-4 space-y-2">
              {detail?.versions.map((version) => (
                <div className="rounded-md border border-zinc-200 px-3 py-2" key={version.id}>
                  <div className="flex items-center justify-between gap-3 text-sm">
                    <span className="font-medium text-zinc-800">Version {version.version_number}</span>
                    <span className="text-xs text-zinc-500">{version.status}</span>
                  </div>
                  <div className="mt-1 text-xs text-zinc-500">
                    {version.model_name} · temp {version.temperature} · {version.max_output_tokens} tokens
                  </div>
                </div>
              )) ?? <div className="text-sm text-zinc-500">No version selected</div>}
            </div>
          </section>

          <section className="rounded-lg border border-zinc-200 bg-white p-4">
            <h2 className="text-base font-semibold text-zinc-950">LLM Calls</h2>
            <div className="mt-4 space-y-2">
              {detail?.recent_llm_calls.length ? (
                detail.recent_llm_calls.map((call) => (
                  <div className="rounded-md border border-zinc-200 px-3 py-2 text-sm" key={call.id}>
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-medium capitalize text-zinc-800">{call.status}</span>
                      <span className="text-xs text-zinc-500">{call.latency_ms} ms</span>
                    </div>
                    <div className="mt-1 text-xs text-zinc-500">
                      {call.model} · {call.total_tokens ?? 0} tokens
                    </div>
                    {call.error_message ? <div className="mt-1 text-xs text-rose-700">{call.error_message}</div> : null}
                  </div>
                ))
              ) : (
                <div className="text-sm text-zinc-500">No calls yet</div>
              )}
            </div>
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
  children: ReactNode;
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

function StatusPill({ label, value, tone }: { label: string; value: string; tone: "neutral" | "ready" }) {
  const toneClassName =
    tone === "ready" ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-zinc-200 bg-white text-zinc-600";
  return (
    <span className={`rounded-md border px-2.5 py-1 font-medium ${toneClassName}`}>
      {label}: {value}
    </span>
  );
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Request failed";
}
