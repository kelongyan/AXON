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
import { errorMessage } from "@/lib/error-message";
import { statusLabel } from "@/lib/status-label";
import { useRunAction } from "@/lib/use-run-action";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { GlassCard } from "@/components/ui/glass-card";
import { MessageBanner } from "@/components/ui/message-banner";
import { StatusPill } from "@/components/ui/status-pill";

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
  const { busy, message, run, setBusy, setMessage } = useRunAction();

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
            sections: [{ heading: "Summary", content: "工具注册表可用。" }],
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
    await run(async () => {
      const [nextTools, nextAgents, nextCalls] = await Promise.all([fetchTools(), fetchAgents(), fetchToolCalls()]);
      setTools(nextTools);
      setAgents(nextAgents);
      setCalls(nextCalls);
      setSelectedToolId((current) => current ?? nextTools[0]?.id ?? null);
      setSelectedAgentId((current) => current ?? nextAgents[0]?.id ?? null);
    });
  }

  async function handleSeed() {
    await run(async () => {
      const result = await seedBuiltInTools();
      setTools(result.items);
      setSelectedToolId(result.items[0]?.id ?? null);
      setMessage(`已初始化内置工具：${result.created} 个已创建，${result.updated} 个已更新`);
    });
  }

  async function handleGrant() {
    if (!selectedAgent || !selectedTool) {
      return;
    }
    await run(async () => {
      await grantTool(selectedAgent.id, selectedTool.id);
      setMessage(`已授权 ${buildGrantLabel(selectedAgent.name, selectedTool.display_name)}`);
    });
  }

  async function handleRevoke() {
    if (!selectedAgent || !selectedTool) {
      return;
    }
    await run(async () => {
      await revokeTool(selectedAgent.id, selectedTool.id);
      setMessage(`已撤销 ${buildGrantLabel(selectedAgent.name, selectedTool.display_name)}`);
    });
  }

  async function handleInvoke() {
    if (!selectedAgent || !selectedTool) {
      return;
    }
    setBusy(true);
    setMessage(null);
    try {
      const input = parseToolInput(inputText);
      const result = await invokeTool(selectedTool.id, selectedAgent.id, input);
      setInvokeResult(result);
      setCalls(await fetchToolCalls());
      setMessage(`工具调用 ${statusLabel(result.status)}`);
    } catch (error) {
      setMessage(errorMessage(error));
      setCalls(await fetchToolCalls().catch(() => calls));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <section className="border-b border-line pb-5">
        <p className="text-xs font-semibold uppercase tracking-wide text-accent">工具注册表</p>
        <div className="mt-2 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-ink">工具</h1>
            <p className="mt-1 text-sm text-ink-3">注册、授权、测试并审计受管控的工具调用。</p>
          </div>
          <div className="flex flex-wrap gap-2 text-xs">
            <StatusPill label="阶段" value="2" tone="success" />
            <StatusPill label="审批" value="已拦截" tone="warning" />
            <StatusPill label="审计" value="开启" tone="success" />
          </div>
        </div>
      </section>

      {message ? <MessageBanner message={message} /> : null}

      <section className="grid gap-5 xl:grid-cols-[300px_minmax(0,1fr)] 2xl:grid-cols-[300px_minmax(0,1fr)_380px]">
        <GlassCard className="overflow-hidden">
          <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
            <div>
              <div className="text-sm font-semibold text-ink">注册表</div>
              <div className="mt-1 text-xs text-ink-3">{tools.length} 个工具</div>
            </div>
            <Button variant="primary" disabled={busy} onClick={handleSeed} type="button">
              初始化
            </Button>
          </div>
          <div className="max-h-[680px] overflow-auto p-2">
            {tools.length === 0 ? (
              <div className="px-3 py-6 text-sm text-ink-3">请先初始化内置工具</div>
            ) : (
              tools.map((tool) => (
                <button
                  className={`mb-2 w-full rounded-xl border px-3 py-3 text-left transition ${
                    selectedToolId === tool.id
                      ? "border-accent bg-accent/10 text-accent"
                      : "border-line bg-surface-solid text-ink-2 hover:border-line-strong hover:bg-elevated"
                  }`}
                  key={tool.id}
                  onClick={() => setSelectedToolId(tool.id)}
                  type="button"
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-sm font-medium">{tool.display_name}</span>
                    <span className="text-xs">{statusLabel(tool.status)}</span>
                  </div>
                  <div className="mt-1 text-xs text-ink-3">
                    {tool.name} · {statusLabel(tool.risk_level)}
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
                <h2 className="text-base font-semibold text-ink">
                  {selectedTool?.display_name ?? "请选择工具"}
                </h2>
                <p className="mt-1 text-sm text-ink-3">{selectedTool?.description ?? "未选择工具"}</p>
              </div>
              {selectedTool ? (
                <div className="flex flex-wrap gap-2 text-xs">
                  <StatusPill
                    label="风险"
                    value={statusLabel(selectedTool.risk_level)}
                    tone={selectedTool.requires_approval ? "warning" : "success"}
                  />
                  <StatusPill label="超时" value={`${selectedTool.timeout_seconds}s`} tone="neutral" />
                </div>
              ) : null}
            </div>

            <div className="mt-5 grid gap-4 md:grid-cols-2">
              <Field label="智能体">
                <select
                  className="field-input"
                  onChange={(event) => setSelectedAgentId(event.target.value || null)}
                  value={selectedAgentId ?? ""}
                >
                  <option value="">请选择智能体</option>
                  {agents.map((agent) => (
                    <option key={agent.id} value={agent.id}>
                      {agent.name}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="授权">
                <div className="flex gap-2">
                  <Button
                    variant="primary"
                    disabled={busy || !selectedAgent || !selectedTool}
                    onClick={handleGrant}
                    type="button"
                  >
                    授权
                  </Button>
                  <Button
                    variant="default"
                    disabled={busy || !selectedAgent || !selectedTool}
                    onClick={handleRevoke}
                    type="button"
                  >
                    撤销
                  </Button>
                </div>
              </Field>
              <Field className="md:col-span-2" label="输入 JSON">
                <textarea
                  className="field-input min-h-52 resize-y font-mono"
                  onChange={(event) => setInputText(event.target.value)}
                  value={inputText}
                />
              </Field>
            </div>

            <div className="mt-4 flex items-center justify-between gap-3">
              <div className="text-xs text-ink-3">本阶段中，高风险或需审批的工具将被拦截并记录审计。</div>
              <Button
                variant="primary"
                disabled={busy || !selectedAgent || !selectedTool}
                onClick={handleInvoke}
                type="button"
              >
                调用
              </Button>
            </div>

            {invokeResult ? (
              <div className="mt-4 rounded-xl border border-success/30 bg-success/10 p-3">
                <div className="text-xs font-semibold uppercase tracking-wide text-success">输出</div>
                <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap text-sm text-ink">
                  {JSON.stringify(invokeResult.output, null, 2)}
                </pre>
              </div>
            ) : null}
          </GlassCard>

          <GlassCard className="p-5">
            <h2 className="text-base font-semibold text-ink">输入结构</h2>
            <pre className="mt-3 max-h-80 overflow-auto rounded-xl border border-line bg-surface-solid p-3 text-xs text-ink-2">
              {selectedTool ? JSON.stringify(selectedTool.input_schema, null, 2) : "{}"}
            </pre>
          </GlassCard>
        </div>

        <GlassCard className="p-4 xl:col-span-2 2xl:col-span-1">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-base font-semibold text-ink">工具调用</h2>
            <Button variant="default" disabled={busy} onClick={() => void loadInitialData()} type="button">
              刷新
            </Button>
          </div>
          <div className="mt-4 max-h-[720px] space-y-2 overflow-auto">
            {calls.length ? (
              calls.map((call) => (
                <div className="rounded-xl border border-line px-3 py-2 text-sm" key={call.id}>
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-medium text-ink-2">{call.tool_name}</span>
                    <span className={call.status === "succeeded" ? "text-xs text-success" : "text-xs text-danger"}>
                      {statusLabel(call.status)}
                    </span>
                  </div>
                  <div className="mt-1 text-xs text-ink-3">
                    {statusLabel(call.risk_level)} · {call.latency_ms} ms
                  </div>
                  {call.error_message ? <div className="mt-1 text-xs text-danger">{call.error_message}</div> : null}
                </div>
              ))
            ) : (
              <div className="text-sm text-ink-3">暂无工具调用记录</div>
            )}
          </div>
        </GlassCard>
      </section>
    </div>
  );
}
