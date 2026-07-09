import { describe, expect, it } from "vitest";

import {
  buildDocumentPayload,
  buildKnowledgeBasePayload,
  buildRetrievalPayload,
} from "./knowledge-bases";

describe("knowledge base helpers", () => {
  it("builds a trimmed knowledge base payload", () => {
    expect(
      buildKnowledgeBasePayload({
        name: "  AgentFlow Handbook  ",
        description: "  Internal docs  ",
        embeddingModel: "  text-embedding-3-small  ",
      }),
    ).toEqual({
      name: "AgentFlow Handbook",
      description: "Internal docs",
      embedding_provider: "openai_compatible",
      embedding_model: "text-embedding-3-small",
    });
  });

  it("builds a trimmed document payload and rejects empty content", () => {
    expect(
      buildDocumentPayload({
        filename: "  handbook.md  ",
        contentType: " text/markdown ",
        content: "  # Handbook  ",
      }),
    ).toEqual({
      filename: "handbook.md",
      content_type: "text/markdown",
      content: "# Handbook",
      metadata: {},
    });

    expect(() =>
      buildDocumentPayload({ filename: "empty.txt", contentType: "text/plain", content: "   " }),
    ).toThrow("Document content is required");
  });

  it("builds a bounded retrieval payload", () => {
    expect(buildRetrievalPayload({ query: " AgentFlow embedding ", topK: "99" })).toEqual({
      query: "AgentFlow embedding",
      top_k: 20,
    });
    expect(buildRetrievalPayload({ query: " AgentFlow embedding ", topK: "-1" })).toEqual({
      query: "AgentFlow embedding",
      top_k: 1,
    });
  });
});
