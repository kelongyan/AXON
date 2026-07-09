from typing import Any

import httpx

from app.core.config import Settings
from app.services.llm import LLMProviderError, sanitize_provider_error


class OpenAICompatibleEmbeddingClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout_seconds: int,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    @classmethod
    def from_settings(cls, settings: Settings) -> "OpenAICompatibleEmbeddingClient":
        return cls(
            base_url=settings.resolved_embedding_api_base_url,
            api_key=settings.resolved_embedding_api_key.get_secret_value(),
            timeout_seconds=settings.model_request_timeout_seconds,
        )

    def embed_texts(self, *, texts: list[str], model: str) -> list[list[float]]:
        if not texts:
            return []

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {"model": model, "input": texts}
        try:
            with httpx.Client(timeout=self.timeout_seconds, transport=self.transport) as client:
                response = client.post(f"{self.base_url}/embeddings", headers=headers, json=payload)
        except httpx.HTTPError as exc:
            raise LLMProviderError(sanitize_provider_error(f"embedding provider request failed: {exc}")) from exc

        if response.status_code >= 400:
            raise LLMProviderError(
                sanitize_provider_error(
                    f"embedding provider returned {response.status_code}: {_provider_error_message(response)}"
                )
            )

        body = response.json()
        data = body.get("data") if isinstance(body, dict) else None
        if not isinstance(data, list):
            raise LLMProviderError("embedding provider returned an invalid payload")

        ordered = sorted(
            (item for item in data if isinstance(item, dict)),
            key=lambda item: int(item.get("index", 0)),
        )
        vectors: list[list[float]] = []
        for item in ordered:
            embedding = item.get("embedding")
            if not isinstance(embedding, list) or not all(isinstance(value, int | float) for value in embedding):
                raise LLMProviderError("embedding provider returned an invalid vector")
            vectors.append([float(value) for value in embedding])

        if len(vectors) != len(texts):
            raise LLMProviderError("embedding provider returned the wrong number of vectors")
        return vectors


def _provider_error_message(response: httpx.Response) -> str:
    try:
        body: Any = response.json()
    except ValueError:
        return response.text[:500]

    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict) and isinstance(error.get("message"), str):
            return error["message"][:500]
        if isinstance(body.get("message"), str):
            return body["message"][:500]
    return str(body)[:500]
