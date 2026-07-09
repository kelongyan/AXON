import { apiFormRequest, apiRequest } from "./api-client";

export type KnowledgeBaseFormValues = {
  name: string;
  description: string;
  embeddingModel: string;
};

export type DocumentFormValues = {
  filename: string;
  contentType: string;
  content: string;
};

export type RetrievalFormValues = {
  query: string;
  topK: string;
};

export type KnowledgeBasePayload = {
  name: string;
  description: string;
  embedding_provider: "openai_compatible";
  embedding_model: string | null;
};

export type DocumentPayload = {
  filename: string;
  content_type: string;
  content: string;
  metadata: Record<string, unknown>;
};

export type RetrievalPayload = {
  query: string;
  top_k: number;
};

export type KnowledgeBase = {
  id: string;
  workspace_id: string;
  name: string;
  description: string;
  embedding_provider: string;
  embedding_model: string;
  status: string;
  settings: Record<string, unknown>;
  created_by: string;
  created_at: string;
  updated_at: string;
  document_count: number;
  chunk_count: number;
};

export type KnowledgeDocument = {
  id: string;
  workspace_id: string;
  knowledge_base_id: string;
  filename: string;
  content_type: string;
  source_type: string;
  object_key: string;
  status: string;
  parsing_error: string | null;
  text_char_count: number;
  chunk_count: number;
  metadata: Record<string, unknown>;
  created_at: string;
  processed_at: string | null;
};

export type SourceMetadata = {
  knowledge_base_id: string;
  document_id: string;
  chunk_id: string;
  filename: string;
  ordinal: number;
  metadata: Record<string, unknown>;
};

export type DocumentChunk = {
  id: string;
  workspace_id: string;
  knowledge_base_id: string;
  document_id: string;
  ordinal: number;
  content: string;
  token_count: number;
  char_count: number;
  metadata: Record<string, unknown>;
  source: SourceMetadata;
  created_at: string;
};

export type RetrievalResult = {
  chunk_id: string;
  document_id: string;
  knowledge_base_id: string;
  content: string;
  score: number;
  source: SourceMetadata;
};

export type RetrievalResponse = {
  query: string;
  results: RetrievalResult[];
};

export type KnowledgeBaseDetail = KnowledgeBase & {
  documents: KnowledgeDocument[];
  chunks: DocumentChunk[];
};

export function buildKnowledgeBasePayload(values: KnowledgeBaseFormValues): KnowledgeBasePayload {
  const embeddingModel = values.embeddingModel.trim();
  return {
    name: values.name.trim(),
    description: values.description.trim(),
    embedding_provider: "openai_compatible",
    embedding_model: embeddingModel || null,
  };
}

export function buildDocumentPayload(values: DocumentFormValues): DocumentPayload {
  const content = values.content.trim();
  if (!content) {
    throw new Error("Document content is required");
  }
  return {
    filename: values.filename.trim() || "document.txt",
    content_type: values.contentType.trim() || "text/plain",
    content,
    metadata: {},
  };
}

export function buildRetrievalPayload(values: RetrievalFormValues): RetrievalPayload {
  const parsedTopK = Number.parseInt(values.topK, 10);
  const topK = Number.isFinite(parsedTopK) ? Math.min(20, Math.max(1, parsedTopK)) : 5;
  return {
    query: values.query.trim(),
    top_k: topK,
  };
}

export async function fetchKnowledgeBases(): Promise<KnowledgeBase[]> {
  const response = await apiRequest<{ items: KnowledgeBase[] }>("/knowledge-bases");
  return response.items;
}

export async function fetchKnowledgeBase(knowledgeBaseId: string): Promise<KnowledgeBaseDetail> {
  return apiRequest<KnowledgeBaseDetail>(`/knowledge-bases/${knowledgeBaseId}`);
}

export async function createKnowledgeBase(values: KnowledgeBaseFormValues): Promise<KnowledgeBase> {
  return apiRequest<KnowledgeBase>("/knowledge-bases", {
    method: "POST",
    body: JSON.stringify(buildKnowledgeBasePayload(values)),
  });
}

export async function addDocument(knowledgeBaseId: string, values: DocumentFormValues): Promise<KnowledgeDocument> {
  return apiRequest<KnowledgeDocument>(`/knowledge-bases/${knowledgeBaseId}/documents`, {
    method: "POST",
    body: JSON.stringify(buildDocumentPayload(values)),
  });
}

export async function uploadDocument(knowledgeBaseId: string, file: File): Promise<KnowledgeDocument> {
  const data = new FormData();
  data.append("file", file);
  data.append("metadata", "{}");
  return formRequest<KnowledgeDocument>(`/knowledge-bases/${knowledgeBaseId}/documents/upload`, data);
}

export async function retrieve(
  knowledgeBaseId: string,
  values: RetrievalFormValues,
): Promise<RetrievalResponse> {
  return apiRequest<RetrievalResponse>(`/knowledge-bases/${knowledgeBaseId}/retrieve`, {
    method: "POST",
    body: JSON.stringify(buildRetrievalPayload(values)),
  });
}

async function formRequest<T>(path: string, data: FormData): Promise<T> {
  return apiFormRequest<T>(path, data);
}
