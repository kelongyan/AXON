"use client";

import { type FormEvent, useEffect, useMemo, useState } from "react";

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
} from "@/features/agents";
import { cn } from "@/lib/cn";
import { errorMessage } from "@/lib/error-message";
import { statusLabel } from "@/lib/status-label";
import { useRunAction } from "@/lib/use-run-action";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Card } from "@/components/ui/glass-card";
import { ListItem } from "@/components/ui/list-item";
import { MessageBanner } from "@/components/ui/message-banner";
import { Modal } from "@/components/ui/modal";
import { StatusPill } from "@/components/ui/status-pill";

const defaultFormValues: AgentFormValues = {
  name: "",
  description: "",
  rolePrompt: "你是一个专注的助手。",
  systemPrompt: "用简洁、结构化的 Markdown 回答。",
  modelName: "gpt-4.1-mini",
  temperature: "0.2",
  maxOutputTokens: "1000",
};

type Tab = "config" | "test" | "versions" | "calls";

const tabs: { key: Tab; label: string }[] = [
  { key: "config", label: "配置" },
  { key: "test", label: "测试" },
  { key: "versions", label: "版本" },
  { key: "calls", label: "调用" },
];

export function AgentsConsole() {
  const [context, setContext] = useState<MeContext | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [detail, setDetail] = useState<AgentDetail | null>(null);
  const [formValues, setFormValues] = useState<AgentFormValues>(defaultFormValues);
  const [testInput, setTestInput] = useState("总结该智能体应当完成的任务。");
  const [testRun, setTestRun] = useState<AgentTestRun | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("config");
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [createFormValues, setCreateFormValues] = useState<AgentFormValues>(defaultFormValues);
  const { busy, message, run, setMessage } = useRunAction();

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
      const [nextContext, nextAgents] = await Promise.all([fetchMe(), fetchAgents()]);
      setContext(nextContext);
      setAgents(nextAgents);
      if (!selectedAgentId && nextAgents[0]) {
        setSelectedAgentId(nextAgents[0].id);
      }
    } catch (error) {
      setMessage(errorMessage(error));
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
    await run(async () => {
      const created = await createAgent(createFormValues);
      setMessage(`已创建 ${created.name}`);
      setTestRun(null);
      setCreateFormValues(defaultFormValues);
      setCreateModalOpen(false);
      await reloadAgents(created.id);
    });
  }

  async function handlePublishVersion() {
    if (!selectedAgentId) {
      return;
    }
    await run(async () => {
      await publishAgentVersion(selectedAgentId, formValues);
      setMessage("已发布新的智能体版本");
      await loadAgentDetail(selectedAgentId);
      await reloadAgents(selectedAgentId);
    });
  }

  async function handleClone() {
    if (!selectedAgentId) {
      return;
    }
    await run(async () => {
      const cloned = await cloneAgent(selectedAgentId);
      setMessage(`已克隆 ${cloned.name}`);
      await reloadAgents(cloned.id);
    });
  }

  async function handleDisable() {
    if (!selectedAgentId) {
      return;
    }
    await run(async () => {
      await disableAgent(selectedAgentId);
      setMessage("智能体已停用");
      await loadAgentDetail(selectedAgentId);
      await reloadAgents(selectedAgentId);
    });
  }

  async function handleTestRun() {
    if (!selectedAgentId) {
      return;
    }
    await run(async () => {
      const result = await runAgentTest(selectedAgentId, testInput);
      setTestRun(result);
      setMessage("测试运行完成");
      await loadAgentDetail(selectedAgentId);
    });
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <section className="border-b border-line pb-5">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-page-title">智能体</h1>
            <p className="mt-1 text-sm text-ink-3">
              {context ? `${context.workspace.name} · ${context.user.display_name}` : "正在加载工作区"}
            </p>
          </div>
          <div className="flex flex-wrap gap-2 text-xs">
            <StatusPill label="阶段" value="1" tone="success" />
            <StatusPill label="提供商" value="OpenAI API" tone="success" />
            <StatusPill label="本地推理" value="关闭" tone="neutral" />
          </div>
        </div>
      </section>

      {message ? <MessageBanner message={message} /> : null}

      <section className="grid gap-5 xl:grid-cols-[260px_minmax(0,1fr)]">
        {/* Left column: actions only */}
        <div className="space-y-5">
          <Card className="space-y-4 p-4">
            <h2 className="text-sm font-semibold text-ink">操作</h2>
            <Button
              variant="primary"
              disabled={busy}
              onClick={() => setCreateModalOpen(true)}
              type="button"
              className="w-full"
            >
              创建智能体
            </Button>
            <div className="grid grid-cols-2 gap-2 text-center">
              <div className="rounded-xl bg-surface-solid px-3 py-2">
                <div className="text-xs text-ink-3">已配置</div>
                <div className="mt-0.5 text-lg font-semibold text-ink">{agents.length}</div>
              </div>
              <div className="rounded-xl bg-surface-solid px-3 py-2">
                <div className="text-xs text-ink-3">当前版本</div>
                <div className="mt-0.5 text-lg font-semibold text-ink">
                  {selectedAgent?.current_version?.version_number ?? "-"}
                </div>
              </div>
            </div>
          </Card>
        </div>

        {/* Right column: detail tabs + agent list */}
        <div className="min-w-0 space-y-5">
          {/* Current agent header */}
          <Card className="p-5">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div>
                <h2 className="text-base font-semibold text-ink">{selectedAgent?.name ?? "请选择智能体"}</h2>
                <p className="mt-1 text-sm text-ink-3">
                  {selectedAgent
                    ? `${statusLabel(selectedAgent.status)} · ${selectedAgent.current_version?.model_name ?? "未配置模型"}`
                    : "未选择智能体"}
                </p>
              </div>
              <div className="flex flex-wrap gap-2 text-xs">
                <StatusPill label="版本" value={`v${selectedAgent?.current_version?.version_number ?? "-"}`} tone="neutral" />
                <StatusPill status={selectedAgent?.status} tone={statusLabel(selectedAgent?.status) as never} size="sm" />
              </div>
            </div>
          </Card>

          {/* Tab bar */}
          <div className="flex gap-1 border-b border-line">
            {tabs.map((tab) => (
              <button
                key={tab.key}
                type="button"
                className={cn(
                  "px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px",
                  activeTab === tab.key
                    ? "border-accent text-accent"
                    : "border-transparent text-ink-3 hover:text-ink-2",
                )}
                onClick={() => setActiveTab(tab.key)}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Tab panels */}
          <div>
            {/* 配置 tab */}
            {activeTab === "config" && (
              <Card className="p-5">
                <div className="flex flex-col gap-3 border-b border-line pb-4 md:flex-row md:items-center md:justify-between">
                  <div>
                    <h2 className="text-base font-semibold text-ink">配置</h2>
                    <p className="mt-1 text-sm text-ink-3">
                      {selectedAgent?.name ?? "选择智能体"}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      variant="default"
                      disabled={busy || !selectedAgentId}
                      onClick={handleClone}
                      type="button"
                    >
                      克隆
                    </Button>
                    <Button
                      variant="danger"
                      disabled={busy || !selectedAgentId}
                      onClick={handleDisable}
                      type="button"
                    >
                      停用
                    </Button>
                    <Button
                      variant="primary"
                      disabled={busy || !selectedAgentId}
                      onClick={handlePublishVersion}
                      type="button"
                    >
                      发布版本
                    </Button>
                  </div>
                </div>

                <div className="mt-5 grid gap-4 md:grid-cols-2">
                  <Field label="名称">
                    <input
                      className="field-input"
                      onChange={(event) => setFormValues({ ...formValues, name: event.target.value })}
                      value={formValues.name}
                    />
                  </Field>
                  <Field label="模型">
                    <input
                      className="field-input"
                      onChange={(event) => setFormValues({ ...formValues, modelName: event.target.value })}
                      value={formValues.modelName}
                    />
                  </Field>
                  <Field label="温度">
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
                  <Field label="最大输出 Token">
                    <input
                      className="field-input"
                      min="1"
                      onChange={(event) => setFormValues({ ...formValues, maxOutputTokens: event.target.value })}
                      type="number"
                      value={formValues.maxOutputTokens}
                    />
                  </Field>
                  <Field className="md:col-span-2" label="描述">
                    <input
                      className="field-input"
                      onChange={(event) => setFormValues({ ...formValues, description: event.target.value })}
                      value={formValues.description}
                    />
                  </Field>
                  <Field className="md:col-span-2" label="角色提示词">
                    <textarea
                      className="field-input min-h-28 resize-y"
                      onChange={(event) => setFormValues({ ...formValues, rolePrompt: event.target.value })}
                      value={formValues.rolePrompt}
                    />
                  </Field>
                  <Field className="md:col-span-2" label="系统提示词">
                    <textarea
                      className="field-input min-h-32 resize-y"
                      onChange={(event) => setFormValues({ ...formValues, systemPrompt: event.target.value })}
                      value={formValues.systemPrompt}
                    />
                  </Field>
                </div>
              </Card>
            )}

            {/* 测试 tab */}
            {activeTab === "test" && (
              <Card className="p-5">
                <div className="flex items-center justify-between gap-3">
                  <h2 className="text-base font-semibold text-ink">测试运行</h2>
                  <Button
                    variant="primary"
                    disabled={busy || !selectedAgentId}
                    onClick={handleTestRun}
                    type="button"
                  >
                    运行
                  </Button>
                </div>
                <textarea
                  className="field-input mt-4 min-h-28 resize-y"
                  onChange={(event) => setTestInput(event.target.value)}
                  value={testInput}
                />
                {testRun ? (
                  <div className="mt-4 rounded-xl border border-success/30 bg-success/10 p-3">
                    <div className="text-xs font-semibold uppercase tracking-wide text-success">输出</div>
                    <pre className="mt-2 whitespace-pre-wrap text-sm text-ink">{testRun.output}</pre>
                    <div className="mt-3 text-xs text-success">
                      {testRun.llm_call.model} · {testRun.llm_call.total_tokens ?? 0} tokens ·{" "}
                      {testRun.llm_call.latency_ms} ms
                    </div>
                  </div>
                ) : null}
              </Card>
            )}

            {/* 版本 tab */}
            {activeTab === "versions" && (
              <Card className="p-5">
                <h2 className="text-base font-semibold text-ink">版本历史</h2>
                <div className="mt-4 space-y-2">
                  {detail?.versions.map((version) => (
                    <div className="rounded-xl border border-line px-3 py-2" key={version.id}>
                      <div className="flex items-center justify-between gap-3 text-sm">
                        <span className="font-medium text-ink-2">版本 {version.version_number}</span>
                        <span className="text-xs text-ink-3">{statusLabel(version.status)}</span>
                      </div>
                      <div className="mt-1 text-xs text-ink-3">
                        {version.model_name} · temp {version.temperature} · {version.max_output_tokens} tokens
                      </div>
                    </div>
                  )) ?? <div className="text-sm text-ink-3">暂无版本</div>}
                </div>
              </Card>
            )}

            {/* 调用 tab */}
            {activeTab === "calls" && (
              <Card className="p-5">
                <h2 className="text-base font-semibold text-ink">LLM 调用</h2>
                <div className="mt-4 space-y-2">
                  {detail?.recent_llm_calls.length ? (
                    detail.recent_llm_calls.map((call) => (
                      <div className="rounded-xl border border-line px-3 py-2 text-sm" key={call.id}>
                        <div className="flex items-center justify-between gap-3">
                          <span className="font-medium text-ink-2">{statusLabel(call.status)}</span>
                          <span className="text-xs text-ink-3">{call.latency_ms} ms</span>
                        </div>
                        <div className="mt-1 text-xs text-ink-3">
                          {call.model} · {call.total_tokens ?? 0} tokens
                        </div>
                        {call.error_message ? (
                          <div className="mt-1 text-xs text-danger">{call.error_message}</div>
                        ) : null}
                      </div>
                    ))
                  ) : (
                    <div className="text-sm text-ink-3">暂无调用</div>
                  )}
                </div>
              </Card>
            )}
          </div>

          {/* Agent list moved below tabs */}
          <Card className="overflow-hidden">
            <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
              <div>
                <div className="text-sm font-semibold text-ink">智能体列表</div>
                <div className="mt-1 text-xs text-ink-3">{agents.length} 个已配置</div>
              </div>
              <Button
                variant="secondary"
                disabled={busy}
                onClick={() => setCreateModalOpen(true)}
                type="button"
              >
                创建
              </Button>
            </div>
            <div className="max-h-[360px] overflow-auto p-2">
              {agents.length === 0 ? (
                <div className="px-3 py-6 text-sm text-ink-3">暂无智能体</div>
              ) : (
                agents.map((agent) => (
                  <ListItem
                    key={agent.id}
                    selected={selectedAgentId === agent.id}
                    title={agent.name}
                    subtitle={
                      <>
                        v{agent.current_version?.version_number ?? "-"} ·{" "}
                        {agent.current_version?.model_name ?? "未配置模型"}
                      </>
                    }
                    badge={<span className="text-xs">{statusLabel(agent.status)}</span>}
                    onClick={() => setSelectedAgentId(agent.id)}
                  />
                ))
              )}
            </div>
          </Card>
        </div>
      </section>

      {/* Create agent modal */}
      <Modal
        open={createModalOpen}
        onClose={() => setCreateModalOpen(false)}
        title="创建智能体"
      >
        <form className="space-y-4" onSubmit={handleCreate}>
          <Field label="名称">
            <input
              className="field-input"
              onChange={(event) =>
                setCreateFormValues({ ...createFormValues, name: event.target.value })
              }
              value={createFormValues.name}
              required
            />
          </Field>
          <Field label="描述">
            <input
              className="field-input"
              onChange={(event) =>
                setCreateFormValues({ ...createFormValues, description: event.target.value })
              }
              value={createFormValues.description}
            />
          </Field>
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="模型">
              <input
                className="field-input"
                onChange={(event) =>
                  setCreateFormValues({ ...createFormValues, modelName: event.target.value })
                }
                value={createFormValues.modelName}
              />
            </Field>
            <Field label="温度">
              <input
                className="field-input"
                max="2"
                min="0"
                onChange={(event) =>
                  setCreateFormValues({ ...createFormValues, temperature: event.target.value })
                }
                step="0.1"
                type="number"
                value={createFormValues.temperature}
              />
            </Field>
          </div>
          <Field label="最大输出 Token">
            <input
              className="field-input"
              min="1"
              onChange={(event) =>
                setCreateFormValues({ ...createFormValues, maxOutputTokens: event.target.value })
              }
              type="number"
              value={createFormValues.maxOutputTokens}
            />
          </Field>
          <Field label="角色提示词">
            <textarea
              className="field-input min-h-20 resize-y"
              onChange={(event) =>
                setCreateFormValues({ ...createFormValues, rolePrompt: event.target.value })
              }
              value={createFormValues.rolePrompt}
            />
          </Field>
          <Field label="系统提示词">
            <textarea
              className="field-input min-h-20 resize-y"
              onChange={(event) =>
                setCreateFormValues({ ...createFormValues, systemPrompt: event.target.value })
              }
              value={createFormValues.systemPrompt}
            />
          </Field>
          <div className="flex justify-end gap-2 pt-2">
            <Button
              variant="default"
              disabled={busy}
              onClick={() => setCreateModalOpen(false)}
              type="button"
            >
              取消
            </Button>
            <Button variant="primary" disabled={busy} type="submit">
              创建
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
