"""The AI tool loop, tested with a stub Anthropic client (no network, no API key needed)."""
import json
from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from app.config import settings
from app.schemas import ChatMessage
from app.services import chatbot


def block(**kw):
    return SimpleNamespace(**kw)


class StubMessages:
    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.script.pop(0)(kwargs)


class StubClient:
    instances = []

    def __init__(self, script, **_):
        self.beta = SimpleNamespace(messages=StubMessages(script))
        StubClient.instances.append(self)


@pytest.fixture
def ai_mode(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")
    StubClient.instances.clear()

    def install(script):
        monkeypatch.setattr(anthropic, "Anthropic", lambda **kw: StubClient(script, **kw))
    return install


def test_tool_loop_runs_tools_and_links_products(catalog, ai_mode):
    def first(_):
        return SimpleNamespace(stop_reason="tool_use", content=[
            block(type="thinking", thinking="", signature="sig"),
            block(type="tool_use", id="tu_1", name="recommend_build", input={"budget": 2000, "use_case": "gaming"}),
        ])

    def second(kwargs):
        # the tool result must come back in one user message, with the matching id
        last = kwargs["messages"][-1]
        assert last["role"] == "user" and last["content"][0]["tool_use_id"] == "tu_1"
        assert '"parts"' in last["content"][0]["content"]
        parts = json.loads(last["content"][0]["content"])["parts"]
        cpu_id = next(p["id"] for p in parts if p["category"] == "cpu")
        return SimpleNamespace(stop_reason="end_turn", content=[
            block(type="text", text=f"Here is your build. CPU: Ryzen [[product:{cpu_id}]]"),
        ])

    ai_mode([first, second])
    out = chatbot.chat(catalog, [ChatMessage(role="user", content="gaming pc 2000 jd")])
    assert out.mode == "ai"
    assert out.build is not None and out.build.compatible
    assert len(out.products) == 1 and out.products[0].category == "cpu"

    call = StubClient.instances[0].beta.messages.calls[0]
    assert call["model"] == settings.chat_model == "claude-opus-5-5"
    assert call["output_config"] == {"effort": settings.chat_effort}
    assert call["fallbacks"] == "default" and "server-side-fallback-2026-07-01" in call["betas"]
    assert all(t["strict"] for t in call["tools"])
    assert "thinking" not in call  # Opus 5.5: thinking is always on; effort is the control


def test_refusal_is_handled(catalog, ai_mode):
    ai_mode([lambda _: SimpleNamespace(stop_reason="refusal", content=[])])
    out = chatbot.chat(catalog, [ChatMessage(role="user", content="something off-topic")])
    assert out.mode == "ai" and "PC parts" in out.reply


def test_api_error_falls_back_to_offline(catalog, ai_mode):
    def boom(_):
        raise anthropic.APIConnectionError(request=httpx2.Request("POST", "https://api.anthropic.com"))
    ai_mode([boom])
    out = chatbot.chat(catalog, [ChatMessage(role="user", content="gaming pc for 2000 jd")])
    assert out.mode == "offline" and "temporarily unavailable" in out.reply


def test_echo_drops_blocks_before_fallback_marker():
    blocks = [block(type="thinking"), block(type="tool_use"), block(type="fallback"),
              block(type="thinking"), block(type="text")]
    kept = [b.type for b in chatbot._echoable(blocks)]
    assert kept == ["fallback", "thinking", "text"]
