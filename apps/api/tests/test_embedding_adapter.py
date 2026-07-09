import json

import httpx
import pytest

from app.services.embeddings import OpenAICompatibleEmbeddingClient
from app.services.llm import LLMProviderError


def test_openai_compatible_embedding_client_posts_embeddings_and_orders_vectors():
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("authorization")
        captured["payload"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [0.0, 1.0, 0.5]},
                    {"index": 0, "embedding": [1.0, 0.0, 0.25]},
                ]
            },
        )

    client = OpenAICompatibleEmbeddingClient(
        base_url="https://provider.test/v1",
        api_key="sk-provider",
        timeout_seconds=5,
        transport=httpx.MockTransport(handler),
    )

    vectors = client.embed_texts(texts=["alpha", "beta"], model="text-embedding-compatible")

    assert captured["url"] == "https://provider.test/v1/embeddings"
    assert captured["authorization"] == "Bearer sk-provider"
    assert captured["payload"] == {"model": "text-embedding-compatible", "input": ["alpha", "beta"]}
    assert vectors == [[1.0, 0.0, 0.25], [0.0, 1.0, 0.5]]


def test_openai_compatible_embedding_client_sanitizes_provider_errors():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "bad key sk-provider in Authorization header"}})

    client = OpenAICompatibleEmbeddingClient(
        base_url="https://provider.test/v1/",
        api_key="sk-provider",
        timeout_seconds=5,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(LLMProviderError) as exc_info:
        client.embed_texts(texts=["alpha"], model="text-embedding-compatible")

    message = str(exc_info.value)
    assert "embedding provider returned 401" in message
    assert "sk-provider" not in message
    assert "Authorization" not in message
