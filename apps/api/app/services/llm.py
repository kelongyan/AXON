from dataclasses import dataclass
import re
from typing import Any

import httpx

from app.core.config import Settings


@dataclass(frozen=True)
class LLMCompletion:
    content: str
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class LLMProviderError(RuntimeError):
    pass


class OpenAICompatibleLLMClient:
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
    def from_settings(cls, settings: Settings) -> "OpenAICompatibleLLMClient":
        return cls(
            base_url=settings.llm_api_base_url,
            api_key=settings.llm_api_key.get_secret_value(),
            timeout_seconds=settings.model_request_timeout_seconds,
        )

    def complete(
        self,
        *,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        max_output_tokens: int,
    ) -> LLMCompletion:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_output_tokens,
        }

        try:
            with httpx.Client(timeout=self.timeout_seconds, transport=self.transport) as client:
                response = client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
        except httpx.HTTPError as exc:
            raise LLMProviderError(sanitize_provider_error(f"provider request failed: {exc}")) from exc

        if response.status_code >= 400:
            raise LLMProviderError(
                sanitize_provider_error(
                    f"provider returned {response.status_code}: {_provider_error_message(response)}"
                )
            )

        body = response.json()
        try:
            message = body["choices"][0]["message"]
            content = message.get("content", "")
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError("provider returned an invalid chat completion payload") from exc

        usage = body.get("usage") if isinstance(body, dict) else {}
        if not isinstance(usage, dict):
            usage = {}

        return LLMCompletion(
            content=content,
            model=model,
            prompt_tokens=_optional_int(usage.get("prompt_tokens")),
            completion_tokens=_optional_int(usage.get("completion_tokens")),
            total_tokens=_optional_int(usage.get("total_tokens")),
        )


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


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def sanitize_provider_error(message: str) -> str:
    sanitized = re.sub(r"sk-[A-Za-z0-9_\-]+", "[REDACTED]", message)
    sanitized = re.sub(r"authorization", "auth", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"bearer\s+[A-Za-z0-9._\-]+", "Bearer [REDACTED]", sanitized, flags=re.IGNORECASE)
    return sanitized

