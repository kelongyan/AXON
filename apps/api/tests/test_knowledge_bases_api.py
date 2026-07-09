from uuid import UUID

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.models import Base
from app.main import create_app
from app.services.llm import LLMCompletion


class BagOfWordsEmbeddingClient:
    terms = ["agentflow", "embedding", "remote", "billing", "policy", "retrieval", "context", "untrusted"]

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def embed_texts(self, *, texts: list[str], model: str) -> list[list[float]]:
        self.calls.append({"texts": texts, "model": model})
        return [self._vector(text) for text in texts]

    def _vector(self, text: str) -> list[float]:
        lowered = text.lower()
        return [float(lowered.count(term)) for term in self.terms]


class MemoryObjectStore:
    def __init__(self) -> None:
        self.objects: dict[str, dict[str, object]] = {}

    def put_bytes(self, *, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = {"data": data, "content_type": content_type}


class RecordingLLMClient:
    def __init__(self, content: str = "The answer uses the retrieved source.") -> None:
        self.content = content
        self.calls: list[dict[str, object]] = []

    def complete(
        self,
        *,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        max_output_tokens: int,
    ) -> LLMCompletion:
        self.calls.append(
            {
                "messages": messages,
                "model": model,
                "temperature": temperature,
                "max_output_tokens": max_output_tokens,
            }
        )
        return LLMCompletion(
            content=self.content,
            model=model,
            prompt_tokens=11,
            completion_tokens=7,
            total_tokens=18,
        )


def create_test_client(
    *,
    fake_embedding: object | None = None,
    fake_store: object | None = None,
    fake_llm: object | None = None,
) -> TestClient:
    app = create_app(
        Settings(
            check_dependencies=False,
            database_url="sqlite+pysqlite:///:memory:",
            llm_api_key="sk-test",
            embedding_model="test-embedding",
        )
    )
    Base.metadata.create_all(app.state.engine)
    if fake_embedding is not None:
        app.state.embedding_client = fake_embedding
    if fake_store is not None:
        app.state.object_store = fake_store
    if fake_llm is not None:
        app.state.llm_client = fake_llm
    return TestClient(app)


def test_knowledge_base_document_processing_and_retrieval_returns_source_metadata():
    fake_embedding = BagOfWordsEmbeddingClient()
    fake_store = MemoryObjectStore()
    client = create_test_client(fake_embedding=fake_embedding, fake_store=fake_store)

    kb_response = client.post(
        "/knowledge-bases",
        json={
            "name": "AgentFlow Handbook",
            "description": "Internal RAG examples.",
            "embedding_model": "test-embedding",
        },
    )

    assert kb_response.status_code == 201
    knowledge_base = kb_response.json()
    kb_id = knowledge_base["id"]
    UUID(kb_id)
    assert knowledge_base["status"] == "active"
    assert knowledge_base["embedding_provider"] == "openai_compatible"

    document_response = client.post(
        f"/knowledge-bases/{kb_id}/documents",
        json={
            "filename": "agentflow.md",
            "content_type": "text/markdown",
            "content": (
                "# AgentFlow\n\n"
                "AgentFlow uses remote API-only embedding providers for RAG retrieval. "
                "The platform does not deploy local model weights.\n\n"
                "## Billing\n\nInvoices and billing policies live in a separate finance system."
            ),
            "metadata": {"source": "test-suite"},
        },
    )

    assert document_response.status_code == 201
    document = document_response.json()
    assert document["status"] == "processed"
    assert document["chunk_count"] >= 1
    assert document["object_key"] in fake_store.objects
    assert fake_embedding.calls[0]["model"] == "test-embedding"

    detail_response = client.get(f"/knowledge-bases/{kb_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["documents"][0]["filename"] == "agentflow.md"
    assert detail["chunks"][0]["source"]["filename"] == "agentflow.md"

    retrieval_response = client.post(
        f"/knowledge-bases/{kb_id}/retrieve",
        json={"query": "How does AgentFlow use remote embedding?", "top_k": 2},
    )

    assert retrieval_response.status_code == 200
    retrieval = retrieval_response.json()
    assert retrieval["query"] == "How does AgentFlow use remote embedding?"
    assert len(retrieval["results"]) >= 1
    top_result = retrieval["results"][0]
    assert "remote API-only embedding providers" in top_result["content"]
    assert top_result["source"]["filename"] == "agentflow.md"
    UUID(top_result["source"]["document_id"])
    UUID(top_result["source"]["chunk_id"])
    assert top_result["score"] > 0


def test_workflow_retrieval_node_injects_untrusted_context_and_returns_citations():
    fake_embedding = BagOfWordsEmbeddingClient()
    fake_store = MemoryObjectStore()
    fake_llm = RecordingLLMClient()
    client = create_test_client(fake_embedding=fake_embedding, fake_store=fake_store, fake_llm=fake_llm)

    kb_id = client.post(
        "/knowledge-bases",
        json={"name": "Runtime Sources", "embedding_model": "test-embedding"},
    ).json()["id"]
    client.post(
        f"/knowledge-bases/{kb_id}/documents",
        json={
            "filename": "runtime.txt",
            "content_type": "text/plain",
            "content": "AgentFlow retrieval context must be marked as untrusted before it reaches the model.",
        },
    )
    agent = create_agent(client)
    workflow = client.post("/workflows", json={"name": "RAG Runtime Flow"}).json()
    publish_response = client.post(
        f"/workflows/{workflow['id']}/versions",
        json={"graph": retrieval_graph(agent["current_version_id"], kb_id)},
    )
    assert publish_response.status_code == 201
    run = client.post(
        f"/workflows/{workflow['id']}/runs",
        json={"input": {"question": "What does retrieval context require?"}},
    ).json()

    execute_response = client.post(f"/runs/{run['id']}/execute")

    assert execute_response.status_code == 200
    executed = execute_response.json()
    assert executed["status"] == "succeeded"
    assert executed["output"]["answer"] == "The answer uses the retrieved source."
    assert executed["output"]["citations"][0]["filename"] == "runtime.txt"
    assert executed["steps"][1]["node_type"] == "retrieval"
    llm_user_message = fake_llm.calls[0]["messages"][1]["content"]
    assert "UNTRUSTED RETRIEVAL CONTEXT" in llm_user_message
    assert "marked as untrusted" in llm_user_message


def create_agent(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/agents",
        json={
            "name": "RAG Answerer",
            "description": "Answers with retrieved context.",
            "role_prompt": "You answer questions from supplied sources.",
            "system_prompt": "Use retrieved context when present.",
            "model_provider": "openai_compatible",
            "model_name": "step-3.7-flash",
            "temperature": 0.2,
            "max_output_tokens": 512,
        },
    )
    assert response.status_code == 201
    return response.json()


def retrieval_graph(agent_version_id: str, knowledge_base_id: str) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "nodes": [
            {
                "id": "node_start",
                "type": "start",
                "name": "Start",
                "config": {
                    "input_schema": {
                        "type": "object",
                        "required": ["question"],
                        "properties": {"question": {"type": "string"}},
                    }
                },
            },
            {
                "id": "node_retrieval",
                "type": "retrieval",
                "name": "Retrieve Sources",
                "config": {"knowledge_base_ids": [knowledge_base_id], "top_k": 3},
                "input_mapping": {"query": "$.run.input.question"},
            },
            {
                "id": "node_agent",
                "type": "agent",
                "name": "Answer",
                "config": {
                    "agent_version_id": agent_version_id,
                    "instruction": "Answer the question with citations.",
                },
                "input_mapping": {
                    "question": "$.run.input.question",
                    "retrieval_context": "$.steps.node_retrieval.output.context",
                    "citations": "$.steps.node_retrieval.output.citations",
                },
            },
            {
                "id": "node_end",
                "type": "end",
                "name": "End",
                "config": {
                    "output_mapping": {
                        "answer": "$.steps.node_agent.output.content",
                        "citations": "$.steps.node_retrieval.output.citations",
                    }
                },
            },
        ],
        "edges": [
            {"id": "edge_start_retrieval", "source": "node_start", "target": "node_retrieval", "type": "default"},
            {"id": "edge_retrieval_agent", "source": "node_retrieval", "target": "node_agent", "type": "default"},
            {"id": "edge_agent_end", "source": "node_agent", "target": "node_end", "type": "default"},
        ],
    }
