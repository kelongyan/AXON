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

const defaultKnowledgeBaseForm: KnowledgeBaseFormValues = {
  name: "AgentFlow Handbook",
  description: "Project notes and operating constraints.",
  embeddingModel: "",
};

const defaultDocumentForm: DocumentFormValues = {
  filename: "agentflow-handbook.md",
  contentType: "text/markdown",
  content:
    "# AgentFlow\n\nAgentFlow uses remote OpenAI-compatible APIs for LLM and Embedding calls. Local model deployment is disabled in the current phase.",
};

const defaultRetrievalForm: RetrievalFormValues = {
  query: "How does AgentFlow use embeddings?",
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
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

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
    await runAction(async () => {
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
    await runAction(async () => {
      const created = await createKnowledgeBase(knowledgeBaseForm);
      setMessage(`Created ${created.name}`);
      await reloadKnowledgeBases(created.id);
    });
  }

  async function handleAddDocument() {
    if (!selectedKnowledgeBaseId) {
      return;
    }
    await runAction(async () => {
      const document = await addDocument(selectedKnowledgeBaseId, documentForm);
      setMessage(`Processed ${document.filename}`);
      await loadDetail(selectedKnowledgeBaseId);
      await reloadKnowledgeBases(selectedKnowledgeBaseId);
    });
  }

  async function handleUploadDocument() {
    if (!selectedKnowledgeBaseId || !selectedFile) {
      return;
    }
    await runAction(async () => {
      const document = await uploadDocument(selectedKnowledgeBaseId, selectedFile);
      setMessage(`Uploaded ${document.filename}`);
      setSelectedFile(null);
      await loadDetail(selectedKnowledgeBaseId);
      await reloadKnowledgeBases(selectedKnowledgeBaseId);
    });
  }

  async function handleRetrieve() {
    if (!selectedKnowledgeBaseId) {
      return;
    }
    await runAction(async () => {
      const result = await retrieve(selectedKnowledgeBaseId, retrievalForm);
      setRetrievalResult(result);
      setMessage(`Retrieved ${result.results.length} chunks`);
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

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    setSelectedFile(event.target.files?.[0] ?? null);
  }

  return (
    <div className="space-y-6">
      <section className="border-b border-zinc-200 pb-5">
        <p className="text-xs font-semibold uppercase tracking-normal text-teal-700">Retrieval</p>
        <div className="mt-2 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-zinc-950">Knowledge Bases</h1>
            <p className="mt-1 text-sm text-zinc-500">
              {selectedKnowledgeBase ? `${selectedKnowledgeBase.name} · ${selectedKnowledgeBase.chunk_count} chunks` : "No knowledge base selected"}
            </p>
          </div>
          <div className="flex flex-wrap gap-2 text-xs">
            <StatusPill label="Phase" value="4" tone="ready" />
            <StatusPill label="Embeddings" value="API" tone="ready" />
            <StatusPill label="Local inference" value="Off" tone="neutral" />
          </div>
        </div>
      </section>

      {message ? (
        <div className="rounded-md border border-zinc-200 bg-white px-4 py-3 text-sm text-zinc-700">{message}</div>
      ) : null}

      <section className="grid gap-5 xl:grid-cols-[300px_minmax(0,1fr)_380px]">
        <div className="rounded-lg border border-zinc-200 bg-white">
          <div className="flex items-center justify-between gap-3 border-b border-zinc-200 px-4 py-3">
            <div>
              <div className="text-sm font-semibold text-zinc-950">Knowledge Base List</div>
              <div className="mt-1 text-xs text-zinc-500">{knowledgeBases.length} configured</div>
            </div>
            <button className="control-button" disabled={busy} onClick={() => void loadInitialData()} type="button">
              Refresh
            </button>
          </div>
          <div className="max-h-[700px] overflow-auto p-2">
            {knowledgeBases.length === 0 ? (
              <div className="px-3 py-6 text-sm text-zinc-500">Create a knowledge base to start</div>
            ) : (
              knowledgeBases.map((knowledgeBase) => (
                <button
                  className={`mb-2 w-full rounded-md border px-3 py-3 text-left transition ${
                    selectedKnowledgeBaseId === knowledgeBase.id
                      ? "border-teal-500 bg-teal-50 text-teal-950"
                      : "border-zinc-200 bg-white text-zinc-700 hover:border-zinc-300 hover:bg-zinc-50"
                  }`}
                  key={knowledgeBase.id}
                  onClick={() => setSelectedKnowledgeBaseId(knowledgeBase.id)}
                  type="button"
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-sm font-medium">{knowledgeBase.name}</span>
                    <span className="text-xs capitalize">{knowledgeBase.status}</span>
                  </div>
                  <div className="mt-1 text-xs text-zinc-500">
                    {knowledgeBase.document_count} docs · {knowledgeBase.chunk_count} chunks
                  </div>
                </button>
              ))
            )}
          </div>
        </div>

        <div className="space-y-5">
          <form className="rounded-lg border border-zinc-200 bg-white p-5" onSubmit={handleCreate}>
            <div className="flex flex-col gap-3 border-b border-zinc-200 pb-4 md:flex-row md:items-center md:justify-between">
              <div>
                <h2 className="text-base font-semibold text-zinc-950">Configuration</h2>
                <p className="mt-1 text-sm text-zinc-500">{detail?.embedding_model ?? "Server default embedding model"}</p>
              </div>
              <button className="control-button primary" disabled={busy} type="submit">
                Create
              </button>
            </div>

            <div className="mt-5 grid gap-4 md:grid-cols-2">
              <Field label="Name">
                <input
                  className="field-input"
                  onChange={(event) => setKnowledgeBaseForm({ ...knowledgeBaseForm, name: event.target.value })}
                  value={knowledgeBaseForm.name}
                />
              </Field>
              <Field label="Embedding Model">
                <input
                  className="field-input"
                  onChange={(event) =>
                    setKnowledgeBaseForm({ ...knowledgeBaseForm, embeddingModel: event.target.value })
                  }
                  value={knowledgeBaseForm.embeddingModel}
                />
              </Field>
              <Field className="md:col-span-2" label="Description">
                <input
                  className="field-input"
                  onChange={(event) =>
                    setKnowledgeBaseForm({ ...knowledgeBaseForm, description: event.target.value })
                  }
                  value={knowledgeBaseForm.description}
                />
              </Field>
            </div>
          </form>

          <section className="rounded-lg border border-zinc-200 bg-white p-5">
            <div className="flex flex-col gap-3 border-b border-zinc-200 pb-4 md:flex-row md:items-center md:justify-between">
              <div>
                <h2 className="text-base font-semibold text-zinc-950">Documents</h2>
                <p className="mt-1 text-sm text-zinc-500">{detail?.documents.length ?? 0} processed or queued</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <button className="control-button primary" disabled={busy || !selectedKnowledgeBaseId} onClick={handleAddDocument} type="button">
                  Add Text
                </button>
                <button
                  className="control-button"
                  disabled={busy || !selectedKnowledgeBaseId || !selectedFile}
                  onClick={handleUploadDocument}
                  type="button"
                >
                  Upload
                </button>
              </div>
            </div>

            <div className="mt-5 grid gap-4 md:grid-cols-2">
              <Field label="Filename">
                <input
                  className="field-input"
                  onChange={(event) => setDocumentForm({ ...documentForm, filename: event.target.value })}
                  value={documentForm.filename}
                />
              </Field>
              <Field label="Content Type">
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
              <Field className="md:col-span-2" label="Content">
                <textarea
                  className="field-input min-h-44 resize-y font-mono"
                  onChange={(event) => setDocumentForm({ ...documentForm, content: event.target.value })}
                  value={documentForm.content}
                />
              </Field>
              <Field className="md:col-span-2" label="File">
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
                <div className="rounded-md border border-zinc-200 px-3 py-2 text-sm" key={document.id}>
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-medium text-zinc-800">{document.filename}</span>
                    <span className="text-xs capitalize text-emerald-700">{document.status}</span>
                  </div>
                  <div className="mt-1 text-xs text-zinc-500">
                    {document.chunk_count} chunks · {document.content_type}
                  </div>
                  {document.parsing_error ? <div className="mt-1 text-xs text-rose-700">{document.parsing_error}</div> : null}
                </div>
              )) ?? <div className="text-sm text-zinc-500">No documents yet</div>}
            </div>
          </section>

          <section className="rounded-lg border border-zinc-200 bg-white p-5">
            <div className="border-b border-zinc-200 pb-4">
              <h2 className="text-base font-semibold text-zinc-950">Chunk Preview</h2>
              <p className="mt-1 text-sm text-zinc-500">{detail?.chunks.length ?? 0} visible chunks</p>
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              {detail?.chunks.slice(0, 6).map((chunk) => (
                <div className="rounded-md border border-zinc-200 p-3" key={chunk.id}>
                  <div className="flex items-center justify-between gap-3 text-xs text-zinc-500">
                    <span>{chunk.source.filename}</span>
                    <span>#{chunk.ordinal}</span>
                  </div>
                  <p className="mt-2 line-clamp-4 text-sm text-zinc-700">{chunk.content}</p>
                </div>
              )) ?? <div className="text-sm text-zinc-500">No chunks yet</div>}
            </div>
          </section>
        </div>

        <section className="rounded-lg border border-zinc-200 bg-white p-4">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-base font-semibold text-zinc-950">Retrieval Test</h2>
            <button className="control-button primary" disabled={busy || !selectedKnowledgeBaseId} onClick={handleRetrieve} type="button">
              Search
            </button>
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
                <div className="rounded-md border border-emerald-200 bg-emerald-50 p-3" key={result.chunk_id}>
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-xs font-semibold uppercase tracking-normal text-emerald-700">
                      Result {index + 1}
                    </div>
                    <span className="text-xs text-emerald-700">{result.score.toFixed(3)}</span>
                  </div>
                  <p className="mt-2 whitespace-pre-wrap text-sm text-emerald-950">{result.content}</p>
                  <div className="mt-3 text-xs text-emerald-700">
                    {result.source.filename} · chunk {result.source.ordinal}
                  </div>
                </div>
              ))
            ) : (
              <div className="text-sm text-zinc-500">No retrieval result yet</div>
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
