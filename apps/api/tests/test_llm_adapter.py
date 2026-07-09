import json

import httpx
import pytest

from app.services.llm import OpenAICompatibleLLMClient, LLMProviderError


def test_openai_compatible_client_posts_chat_completion_and_parses_usage():
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("authorization")
        captured["payload"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "hello"}}],
                "usage": {
                    "prompt_tokens": 5,
                    "completion_tokens": 3,
                    "total_tokens": 8,
                },
            },
        )

    client = OpenAICompatibleLLMClient(
        base_url="https://provider.test/v1",
        api_key="sk-provider",
        timeout_seconds=5,
        transport=httpx.MockTransport(handler),
    )

    completion = client.complete(
        messages=[{"role": "user", "content": "ping"}],
        model="remote-model",
        temperature=0.2,
        max_output_tokens=128,
    )

    assert captured["url"] == "https://provider.test/v1/chat/completions"
    assert captured["authorization"] == "Bearer sk-provider"
    assert captured["payload"] == {
        "model": "remote-model",
        "messages": [{"role": "user", "content": "ping"}],
        "temperature": 0.2,
        "max_tokens": 128,
    }
    assert completion.content == "hello"
    assert completion.model == "remote-model"
    assert completion.prompt_tokens == 5
    assert completion.completion_tokens == 3
    assert completion.total_tokens == 8


def test_openai_compatible_client_sanitizes_provider_errors():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={"error": {"message": "bad key sk-provider in Authorization header"}},
        )

    client = OpenAICompatibleLLMClient(
        base_url="https://provider.test/v1/",
        api_key="sk-provider",
        timeout_seconds=5,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(LLMProviderError) as exc_info:
        client.complete(
            messages=[{"role": "user", "content": "ping"}],
            model="remote-model",
            temperature=0.2,
            max_output_tokens=128,
        )

    message = str(exc_info.value)
    assert "provider returned 401" in message
    assert "sk-provider" not in message
    assert "Authorization" not in message

