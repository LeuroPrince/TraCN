import pytest

from app.llm import LlmResponseError, LlmRuntimeConfig, chat_completion


class DummyResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


class DummyClient:
    def __init__(self, response: DummyResponse, **_: object):
        self.response = response

    async def __aenter__(self) -> "DummyClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def post(self, *_: object, **__: object) -> DummyResponse:
        return self.response


@pytest.mark.asyncio
async def test_chat_completion_rejects_reasoning_only_response(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "choices": [
            {
                "message": {"content": "", "reasoning_content": "Thinking..."},
                "finish_reason": "length",
            }
        ]
    }

    monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: DummyClient(DummyResponse(payload), **kwargs))

    with pytest.raises(LlmResponseError, match="max_tokens was exhausted"):
        await chat_completion(
            LlmRuntimeConfig(provider="test", model="reasoning", base_url="https://example.test", api_key="key"),
            [{"role": "user", "content": "hello"}],
            max_tokens=20,
        )


@pytest.mark.asyncio
async def test_chat_completion_returns_final_content(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {"choices": [{"message": {"content": "TraCN connection OK"}, "finish_reason": "stop"}]}

    monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: DummyClient(DummyResponse(payload), **kwargs))

    message = await chat_completion(
        LlmRuntimeConfig(provider="test", model="chat", base_url="https://example.test", api_key="key"),
        [{"role": "user", "content": "hello"}],
    )

    assert message == "TraCN connection OK"
