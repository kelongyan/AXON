"use client";

import { type ChangeEvent, type FormEvent, type ReactNode, useEffect, useMemo, useState } from "react";

import {
  type DocumentFormValues,
  type KnowledgeBase,
  type KnowledgeBaseDetail,
  type KnowledgeBaseFormValues,
  type RetrievalFormValues,
  type RetrievalResponse,
  addDocument,
  createKnowledgeBase,
  fetchKnowledgeBase,
  fetchKnowledgeBases,
  retrieve,
  uploadDocument,
} from "@/lib/knowledge-bases";
import { errorMessage } from "@/lib/error-message";
import { statusLabel } from "@/lib/status-label";
import { useRunAction } from "@/lib/use-run-action";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { GlassCard } from "@/components/ui/glass-card";
import { MessageBanner } from "@/components/ui/message-banner";
import { StatusPill } from "@/components/ui/status-pill";

const defaultKnowledgeBaseForm: KnowledgeBaseFormValues = {
  name: "AgentFlow 手册",
  description: "项目说明与运行约束。",
  embeddingModel: "",
};

const defaultDocumentForm: DocumentFormValues = {
  filename: "agentflow-handbook.md",
  contentType: "text/markdown",
  content:
    "# AgentFlow\n\nAgentFlow 使用远端的 OpenAI 兼容接口进行 LLM 与 Embedding 调用。当前阶段已禁用本地模型部署。",
};

const defaultRetrievalForm: RetrievalFormValues = {
  query: "AgentFlow 如何使用向量嵌入？",
  topK: "5",
};

export function KnowledgeBasesConsole() {
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [selectedKnowledgeBaseId, setSelectedKnowledgeBaseId] = useState<string | null>(null);
  const [detail, setDetail] = useState<KnowledgeBaseDetail | null>(null);
  const [knowledgeBaseForm, setKnowledgeBaseForm] = useState<KnowledgeBaseFormValues>(defaultKnowledgeBaseForm);
  const [documentForm, setDocumentForm] = useState<DocumentFormValues>(defaultDocumentForm);
  const [retrievalForm, setRetrievalForm] = useState<RetrievalFormValues>(defaultRetrievalForm);
  const [retrievalResult, setRetrievalResult] = useState<RetrievalResponse | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const { busy, message, run, setMessage } = useRunAction();

  const selectedKnowledgeBase = useMemo(
    () => knowledgeBases.find((knowledgeBase) => knowledgeBase.id === selectedKnowledgeBaseId) ?? null,
    [knowledgeBases, selectedKnowledgeBaseId],
  );

  useEffect(() => {
    void loadInitialData();
  }, []);

  useEffect(() => {
    if (selectedKnowledgeBaseId) {
      void loadDetail(selectedKnowledgeBaseId);
    } else {
      setDetail(null);
    }
  }, [selectedKnowledgeBaseId]);

  async function loadInitialData() {
    await run(async () => {
      const items = await fetchKnowledgeBases();
      setKnowledgeBases(items);
      setSelectedKnowledgeBaseId((current) => current ?? items[0]?.id ?? null);
    });
  }

  async function reloadKnowledgeBases(selectId?: string) {
    const items = await fetchKnowledgeBases();
    setKnowledgeBases(items);
    if (selectId) {
      setSelectedKnowledgeBaseId(selectId);
      return;
    }
    if (selectedKnowledgeBaseId && items.some((item) => item.id === selectedKnowledgeBaseId)) {
      return;
    }
    setSelectedKnowledgeBaseId(items[0]?.id ?? null);
  }

  async function loadDetail(knowledgeBaseId: string) {
    try {
      const nextDetail = await fetchKnowledgeBase(knowledgeBaseId);
      setDetail(nextDetail);
      setKnowledgeBaseForm({
        name: nextDetail.name,
        description: nextDetail.description,
        embeddingModel: nextDetail.embedding_model,
      });
    } catch (error) {
      setMessage(errorMessage(error));
    }
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await run(async () => {
      const created = await createKnowledgeBase(knowledgeBaseForm);
      setMessage(`已创建 ${created.name}`);
      await reloadKnowledgeBases(created.id);
    });
  }

  async function handleAddDocument() {
    if (!selectedKnowledgeBaseId) {
      return;
    }
    await run(async () => {
      const document = await addDocument(selectedKnowledgeBaseId, documentForm);
      setMessage(`已处理 ${document.filename}`);
      await loadDetail(selectedKnowledgeBaseId);
      await reloadKnowledgeBases(selectedKnowledgeBaseId);
    });
  }

  async function handleUploadDocument() {
    if (!selectedKnowledgeBaseId || !selectedFile) {
      return;
    }
    await run(async () => {
      const document = await uploadDocument(selectedKnowledgeBaseId, selectedFile);
      setMessage(`已上传 ${document.filename}`);
      setSelectedFile(null);
      await loadDetail(selectedKnowledgeBaseId);
      await reloadKnowledgeBases(selectedKnowledgeBaseId);
    });
  }

  async function handleRetrieve() {
    if (!selectedKnowledgeBaseId) {
      return;
    }
    await run(async () => {
      const result = await retrieve(selectedKnowledgeBaseId, retrievalForm);
      setRetrievalResult(result);
      setMessage(`已检索 ${result.results.length} 个分块`);
    });
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    setSelectedFile(event.target.files?.[0] ?? null);
  }

  return (
    <div className="space-y-6">
      <section className="border-b border-line pb-5">
        <p className="text-xs font-semibold uppercase tracking-wide text-accent">检索</p>
        <div className="mt-2 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-ink">知识库</h1>
            <p className="mt-1 text-sm text-ink-3">
              {selectedKnowledgeBase ? `${selectedKnowledgeBase.name} · ${selectedKnowledgeBase.chunk_count} 个分块` : "未选择知识库"}
            </p>
          </div>
          <div className="flex flex-wrap gap-2 text-xs">
            <StatusPill label="阶段" value="4" tone="success" />
            <StatusPill label="嵌入" value="API" tone="success" />
            <StatusPill label="本地推理" value="关闭" tone="neutral" />
          </div>
        </div>
      </section>

      {message ? <MessageBanner message={message} /> : null}

      <section className="grid gap-5 xl:grid-cols-[300px_minmax(0,1fr)_380px]">
        <GlassCard className="overflow-hidden">
          <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
            <div>
              <div className="text-sm font-semibold text-ink">知识库列表</div>
              <div className="mt-1 text-xs text-ink-3">{knowledgeBases.length} 个已配置</div>
            </div>
            <Button variant="default" disabled={busy} onClick={() => void loadInitialData()} type="button">
              刷新
            </Button>
          </div>
          <div className="max-h-[700px] overflow-auto p-2">
            {knowledgeBases.length === 0 ? (
              <div className="px-3 py-6 text-sm text-ink-3">Create a knowledge base to start</div>
            ) : (
              knowledgeBases.map((knowledgeBase) => (
                <button
                  className={`mb-2 w-full rounded-xl border px-3 py-3 text-left transition ${
                    selectedKnowledgeBaseId === knowledgeBase.id
                      ? "border-accent bg-accent/10 text-accent"
                      : "border-line bg-surface-solid text-ink-2 hover:border-line-strong hover:bg-elevated"
                  }`}
                  key={knowledgeBase.id}
                  onClick={() => setSelectedKnowledgeBaseId(knowledgeBase.id)}
                  type="button"
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-sm font-medium">{knowledgeBase.name}</span>
                    <span className="text-xs">{statusLabel(knowledgeBase.status)}</span>
                  </div>
                  <div className="mt-1 text-xs text-ink-3">
                    {knowledgeBase.document_count} 篇文档 · {knowledgeBase.chunk_count} 个分块
                  </div>
                </button>
              ))
            )}
          </div>
        </GlassCard>

        <div className="space-y-5">
          <GlassCard as="form" className="space-y-5 p-5" onSubmit={handleCreate}>
            <div className="flex flex-col gap-3 border-b border-line pb-4 md:flex-row md:items-center md:justify-between">
              <div>
                <h2 className="text-base font-semibold text-ink">配置</h2>
                <p className="mt-1 text-sm text-ink-3">{detail?.embedding_model ?? "服务端默认嵌入模型"}</p>
              </div>
              <Button variant="primary" disabled={busy} type="submit">
                创建
              </Button>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <Field label="名称">
                <input
                  className="field-input"
                  onChange={(event) => setKnowledgeBaseForm({ ...knowledgeBaseForm, name: event.target.value })}
                  value={knowledgeBaseForm.name}
                />
              </Field>
              <Field label="嵌入模型">
                <input
                  className="field-input"
                  onChange={(event) =>
                    setKnowledgeBaseForm({ ...knowledgeBaseForm, embeddingModel: event.target.value })
                  }
                  value={knowledgeBaseForm.embeddingModel}
                />
              </Field>
              <Field className="md:col-span-2" label="描述">
                <input
                  className="field-input"
                  onChange={(event) =>
                    setKnowledgeBaseForm({ ...knowledgeBaseForm, description: event.target.value })
                  }
                  value={knowledgeBaseForm.description}
                />
              </Field>
            </div>
          </GlassCard>

          <GlassCard className="p-5">
            <div className="flex flex-col gap-3 border-b border-line pb-4 md:flex-row md:items-center md:justify-between">
              <div>
                <h2 className="text-base font-semibold text-ink">文档</h2>
                <p className="mt-1 text-sm text-ink-3">{detail?.documents.length ?? 0} 个已处理或排队</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="primary"
                  disabled={busy || !selectedKnowledgeBaseId}
                  onClick={handleAddDocument}
                  type="button"
                >
                  添加文本
                </Button>
                <Button
                  variant="default"
                  disabled={busy || !selectedKnowledgeBaseId || !selectedFile}
                  onClick={handleUploadDocument}
                  type="button"
                >
                  上传
                </Button>
              </div>
            </div>

            <div className="mt-5 grid gap-4 md:grid-cols-2">
              <Field label="文件名">
                <input
                  className="field-input"
                  onChange={(event) => setDocumentForm({ ...documentForm, filename: event.target.value })}
                  value={documentForm.filename}
                />
              </Field>
              <Field label="内容类型">
                <select
                  className="field-input"
                  onChange={(event) => setDocumentForm({ ...documentForm, contentType: event.target.value })}
                  value={documentForm.contentType}
                >
                  <option value="text/markdown">text/markdown</option>
                  <option value="text/plain">text/plain</option>
                  <option value="application/pdf">application/pdf</option>
                </select>
              </Field>
              <Field className="md:col-span-2" label="内容">
                <textarea
                  className="field-input min-h-44 resize-y font-mono"
                  onChange={(event) => setDocumentForm({ ...documentForm, content: event.target.value })}
                  value={documentForm.content}
                />
              </Field>
              <Field className="md:col-span-2" label="文件">
                <input
                  accept=".txt,.md,.markdown,.pdf,text/plain,text/markdown,application/pdf"
                  className="field-input"
                  onChange={handleFileChange}
                  type="file"
                />
              </Field>
            </div>

            <div className="mt-5 grid gap-3 md:grid-cols-2">
              {detail?.documents.map((document) => (
                <div className="rounded-xl border border-line px-3 py-2 text-sm" key={document.id}>
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-medium text-ink-2">{document.filename}</span>
                    <span className="text-xs text-success">{statusLabel(document.status)}</span>
                  </div>
                  <div className="mt-1 text-xs text-ink-3">
                    {document.chunk_count} chunks · {document.content_type}
                  </div>
                  {document.parsing_error ? <div className="mt-1 text-xs text-danger">{document.parsing_error}</div> : null}
                </div>
              )) ?? <div className="text-sm text-ink-3">No documents yet</div>}
            </div>
          </GlassCard>

          <GlassCard className="p-5">
            <div className="border-b border-line pb-4">
              <h2 className="text-base font-semibold text-ink">分块预览</h2>
              <p className="mt-1 text-sm text-ink-3">{detail?.chunks.length ?? 0} 个可见分块</p>
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              {detail?.chunks.slice(0, 6).map((chunk) => (
                <div className="rounded-xl border border-line p-3" key={chunk.id}>
                  <div className="flex items-center justify-between gap-3 text-xs text-ink-3">
                    <span>{chunk.source.filename}</span>
                    <span>#{chunk.ordinal}</span>
                  </div>
                  <p className="mt-2 line-clamp-4 text-sm text-ink-2">{chunk.content}</p>
                </div>
              )) ?? <div className="text-sm text-ink-3">No chunks yet</div>}
            </div>
          </GlassCard>
        </div>

        <GlassCard className="p-4">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-base font-semibold text-ink">检索测试</h2>
            <Button
              variant="primary"
              disabled={busy || !selectedKnowledgeBaseId}
              onClick={handleRetrieve}
              type="button"
            >
              检索
            </Button>
          </div>
          <Field className="mt-4" label="Query">
            <textarea
              className="field-input min-h-28 resize-y"
              onChange={(event) => setRetrievalForm({ ...retrievalForm, query: event.target.value })}
              value={retrievalForm.query}
            />
          </Field>
          <Field className="mt-4" label="Top K">
            <input
              className="field-input"
              max="20"
              min="1"
              onChange={(event) => setRetrievalForm({ ...retrievalForm, topK: event.target.value })}
              type="number"
              value={retrievalForm.topK}
            />
          </Field>

          <div className="mt-5 space-y-3">
            {retrievalResult?.results.length ? (
              retrievalResult.results.map((result, index) => (
                <div className="rounded-xl border border-success/30 bg-success/10 p-3" key={result.chunk_id}>
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-xs font-semibold uppercase tracking-wide text-success">结果 {index + 1}</div>
                    <span className="text-xs text-success">{result.score.toFixed(3)}</span>
                  </div>
                  <p className="mt-2 whitespace-pre-wrap text-sm text-ink">{result.content}</p>
                  <div className="mt-3 text-xs text-success">
                    {result.source.filename} · chunk {result.source.ordinal}
                  </div>
                </div>
              ))
            ) : (
              <div className="text-sm text-ink-3">暂无检索结果</div>
            )}
          </div>
        </GlassCard>
      </section>
    </div>
  );
}
