"use client";

import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { type Agent, fetchAgents } from "@/lib/agents";
import {
  type Tool,
  type ToolCall,
  type ToolInvokeResult,
  buildGrantLabel,
  fetchToolCalls,
  fetchTools,
  grantTool,
  invokeTool,
  parseToolInput,
  revokeTool,
  seedBuiltInTools,
} from "@/lib/tools";

const defaultInput = JSON.stringify(
  {
    data: { title: "Phase 2", status: "ready", secret: "hidden" },
    select_keys: ["title", "status"],
  },
  null,
  2,
);

export function ToolsConsole() {
  const [tools, setTools] = useState<Tool[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [calls, setCalls] = useState<ToolCall[]>([]);
  const [selectedToolId, setSelectedToolId] = useState<string | null>(null);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [inputText, setInputText] = useState(defaultInput);
  const [invokeResult, setInvokeResult] = useState<ToolInvokeResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const selectedTool = useMemo(
    () => tools.find((tool) => tool.id === selectedToolId) ?? null,
    [selectedToolId, tools],
  );
  const selectedAgent = useMemo(
    () => agents.find((agent) => agent.id === selectedAgentId) ?? null,
    [agents, selectedAgentId],
  );

  useEffect(() => {
    void loadInitialData();
  }, []);

  useEffect(() => {
    if (selectedTool?.name === "markdown_report_generate") {
      setInputText(
        JSON.stringify(
          {
            title: "Phase 2",
            sections: [{ heading: "Summary", content: "Tool Registry works." }],
          },
          null,
          2,
        ),
      );
    } else if (selectedTool?.name === "code_runner") {
      setInputText(JSON.stringify({ language: "python", code: "print('blocked')" }, null, 2));
    } else if (selectedTool?.name === "json_transform") {
      setInputText(defaultInput);
    }
  }, [selectedTool?.name]);

  async function loadInitialData() {
    await runAction(async () => {
      const [nextTools, nextAgents, nextCalls] = await Promise.all([fetchTools(), fetchAgents(), fetchToolCalls()]);
      setTools(nextTools);
      setAgents(nextAgents);
      setCalls(nextCalls);
      setSelectedToolId((current) => current ?? nextTools[0]?.id ?? null);
      setSelectedAgentId((current) => current ?? nextAgents[0]?.id ?? null);
    });
  }

  async function handleSeed() {
    await runAction(async () => {
      const result = await seedBuiltInTools();
      setTools(result.items);
      setSelectedToolId(result.items[0]?.id ?? null);
      setMessage(`Seeded built-ins: ${result.created} created, ${result.updated} updated`);
    });
  }

  async function handleGrant() {
    if (!selectedAgent || !selectedTool) {
      return;
    }
    await runAction(async () => {
      await grantTool(selectedAgent.id, selectedTool.id);
      setMessage(`Granted ${buildGrantLabel(selectedAgent.name, selectedTool.display_name)}`);
    });
  }

  async function handleRevoke() {
    if (!selectedAgent || !selectedTool) {
      return;
    }
    await runAction(async () => {
      await revokeTool(selectedAgent.id, selectedTool.id);
      setMessage(`Revoked ${buildGrantLabel(selectedAgent.name, selectedTool.display_name)}`);
    });
  }

  async function handleInvoke() {
    if (!selectedAgent || !selectedTool) {
      return;
    }
    await runAction(async () => {
      const input = parseToolInput(inputText);
      const result = await invokeTool(selectedTool.id, selectedAgent.id, input);
      setInvokeResult(result);
      setCalls(await fetchToolCalls());
      setMessage(`Tool call ${result.status}`);
    });
  }

  async function runAction(action: () => Promise<void>) {
    try {
      setBusy(true);
      setMessage(null);
      await action();
    } catch (error) {
      setMessage(errorMessage(error));
      setCalls(await fetchToolCalls().catch(() => calls));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <section className="border-b border-zinc-200 pb-5">
        <p className="text-xs font-semibold uppercase tracking-normal text-teal-700">Tool Registry</p>
        <div className="mt-2 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-zinc-950">Tools</h1>
            <p className="mt-1 text-sm text-zinc-500">
              Register, authorize, test, and audit guarded tool calls.
            </p>
          </div>
          <div className="flex flex-wrap gap-2 text-xs">
            <StatusPill label="Phase" value="2" tone="ready" />
            <StatusPill label="Approval" value="Blocked" tone="pending" />
            <StatusPill label="Audit" value="On" tone="ready" />
          </div>
        </div>
      </section>

      {message ? (
        <div className="rounded-md border border-zinc-200 bg-white px-4 py-3 text-sm text-zinc-700">{message}</div>
      ) : null}

      <section className="grid gap-5 xl:grid-cols-[300px_minmax(0,1fr)] 2xl:grid-cols-[300px_minmax(0,1fr)_380px]">
        <div className="rounded-lg border border-zinc-200 bg-white">
          <div className="flex items-center justify-between gap-3 border-b border-zinc-200 px-4 py-3">
            <div>
              <div className="text-sm font-semibold text-zinc-950">Registry</div>
              <div className="mt-1 text-xs text-zinc-500">{tools.length} tools</div>
            </div>
            <button className="control-button primary" disabled={busy} onClick={handleSeed} type="button">
              Seed
            </button>
          </div>
          <div className="max-h-[680px] overflow-auto p-2">
            {tools.length === 0 ? (
              <div className="px-3 py-6 text-sm text-zinc-500">Seed built-ins to start</div>
            ) : (
              tools.map((tool) => (
                <button
                  className={`mb-2 w-full rounded-md border px-3 py-3 text-left transition ${
                    selectedToolId === tool.id
                      ? "border-teal-500 bg-teal-50 text-teal-950"
                      : "border-zinc-200 bg-white text-zinc-700 hover:border-zinc-300 hover:bg-zinc-50"
                  }`}
                  key={tool.id}
                  onClick={() => setSelectedToolId(tool.id)}
                  type="button"
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-sm font-medium">{tool.display_name}</span>
                    <span className="text-xs">{tool.status}</span>
                  </div>
                  <div className="mt-1 text-xs text-zinc-500">
                    {tool.name} · {tool.risk_level}
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
                <h2 className="text-base font-semibold text-zinc-950">
                  {selectedTool?.display_name ?? "Select a tool"}
                </h2>
                <p className="mt-1 text-sm text-zinc-500">{selectedTool?.description ?? "No tool selected"}</p>
              </div>
              {selectedTool ? (
                <div className="flex flex-wrap gap-2 text-xs">
                  <StatusPill label="Risk" value={selectedTool.risk_level} tone={selectedTool.requires_approval ? "pending" : "ready"} />
                  <StatusPill label="Timeout" value={`${selectedTool.timeout_seconds}s`} tone="neutral" />
                </div>
              ) : null}
            </div>

            <div className="mt-5 grid gap-4 md:grid-cols-2">
              <Field label="Agent">
                <select
                  className="field-input"
                  onChange={(event) => setSelectedAgentId(event.target.value || null)}
                  value={selectedAgentId ?? ""}
                >
                  <option value="">Select Agent</option>
                  {agents.map((agent) => (
                    <option key={agent.id} value={agent.id}>
                      {agent.name}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Authorization">
                <div className="flex gap-2">
                  <button className="control-button primary" disabled={busy || !selectedAgent || !selectedTool} onClick={handleGrant} type="button">
                    Grant
                  </button>
                  <button className="control-button" disabled={busy || !selectedAgent || !selectedTool} onClick={handleRevoke} type="button">
                    Revoke
                  </button>
                </div>
              </Field>
              <Field className="md:col-span-2" label="Input JSON">
                <textarea
                  className="field-input min-h-52 resize-y font-mono"
                  onChange={(event) => setInputText(event.target.value)}
                  value={inputText}
                />
              </Field>
            </div>

            <div className="mt-4 flex items-center justify-between gap-3">
              <div className="text-xs text-zinc-500">
                High-risk or approval-required tools are blocked and audited in this phase.
              </div>
              <button className="control-button primary" disabled={busy || !selectedAgent || !selectedTool} onClick={handleInvoke} type="button">
                Invoke
              </button>
            </div>

            {invokeResult ? (
              <div className="mt-4 rounded-md border border-emerald-200 bg-emerald-50 p-3">
                <div className="text-xs font-semibold uppercase tracking-normal text-emerald-700">Output</div>
                <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap text-sm text-emerald-950">
                  {JSON.stringify(invokeResult.output, null, 2)}
                </pre>
              </div>
            ) : null}
          </section>

          <section className="rounded-lg border border-zinc-200 bg-white p-5">
            <h2 className="text-base font-semibold text-zinc-950">Input Schema</h2>
            <pre className="mt-3 max-h-80 overflow-auto rounded-md border border-zinc-200 bg-zinc-50 p-3 text-xs text-zinc-700">
              {selectedTool ? JSON.stringify(selectedTool.input_schema, null, 2) : "{}"}
            </pre>
          </section>
        </div>

        <section className="rounded-lg border border-zinc-200 bg-white p-4 xl:col-span-2 2xl:col-span-1">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-base font-semibold text-zinc-950">Tool Calls</h2>
            <button className="control-button" disabled={busy} onClick={() => void loadInitialData()} type="button">
              Refresh
            </button>
          </div>
          <div className="mt-4 max-h-[720px] space-y-2 overflow-auto">
            {calls.length ? (
              calls.map((call) => (
                <div className="rounded-md border border-zinc-200 px-3 py-2 text-sm" key={call.id}>
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-medium text-zinc-800">{call.tool_name}</span>
                    <span className={`text-xs ${call.status === "succeeded" ? "text-emerald-700" : "text-rose-700"}`}>
                      {call.status}
                    </span>
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
          </div>
        </section>
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

function StatusPill({
  label,
  tone,
  value,
}: {
  label: string;
  tone: "neutral" | "pending" | "ready";
  value: string;
}) {
  const toneClassName = {
    neutral: "border-zinc-200 bg-white text-zinc-600",
    pending: "border-amber-200 bg-amber-50 text-amber-700",
    ready: "border-emerald-200 bg-emerald-50 text-emerald-700",
  }[tone];
  return (
    <span className={`rounded-md border px-2.5 py-1 font-medium ${toneClassName}`}>
      {label}: {value}
    </span>
  );
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Request failed";
}
