import types

import pytest

from ai_provider import claude, gemini, provider


class FakeGeminiClient:
    def __init__(self):
        self.calls = []
        self.models = types.SimpleNamespace(generate_content=self._generate_content)

    def _generate_content(self, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        return types.SimpleNamespace(text="tailored gemini output")


def test_gemini_generate_passes_system_instruction_and_model(monkeypatch):
    fake_client = FakeGeminiClient()
    monkeypatch.setattr(gemini, "_get_client", lambda api_key: fake_client)
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

    result = gemini.generate("tailor this", system="be ATS-friendly", model="gemini-2.5-pro")

    assert result == "tailored gemini output"
    assert fake_client.calls[0]["model"] == "gemini-2.5-pro"
    assert fake_client.calls[0]["contents"] == "tailor this"
    assert fake_client.calls[0]["config"] == {"system_instruction": "be ATS-friendly"}


def test_gemini_generate_defaults_model_when_none_given(monkeypatch):
    fake_client = FakeGeminiClient()
    monkeypatch.setattr(gemini, "_get_client", lambda api_key: fake_client)
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

    gemini.generate("prompt")

    assert fake_client.calls[0]["model"] == gemini.DEFAULT_MODEL
    assert fake_client.calls[0]["config"] is None


class FakeClaudeClient:
    def __init__(self):
        self.calls = []

    def messages_create(self, **kwargs):
        self.calls.append(kwargs)
        block = types.SimpleNamespace(type="text", text="tailored claude output")
        return types.SimpleNamespace(content=[block])


def test_claude_generate_passes_system_and_model(monkeypatch):
    fake_client = FakeClaudeClient()
    fake_client.messages = types.SimpleNamespace(create=fake_client.messages_create)
    monkeypatch.setattr(claude, "_get_client", lambda api_key: fake_client)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")

    result = claude.generate("tailor this", system="be ATS-friendly", model="claude-opus-4-8")

    assert result == "tailored claude output"
    call = fake_client.calls[0]
    assert call["model"] == "claude-opus-4-8"
    assert call["system"] == "be ATS-friendly"
    assert call["messages"] == [{"role": "user", "content": "tailor this"}]


def test_provider_dispatches_to_gemini_by_config(monkeypatch):
    captured = {}
    monkeypatch.setattr(gemini, "generate", lambda prompt, system=None, model=None: captured.update(
        prompt=prompt, system=system, model=model
    ) or "gemini result")

    result = provider.generate("hello", system="sys", config={"ai_provider": "gemini", "ai_model": "gemini-2.5-pro"})

    assert result == "gemini result"
    assert captured == {"prompt": "hello", "system": "sys", "model": "gemini-2.5-pro"}


def test_provider_dispatches_to_claude_by_config(monkeypatch):
    monkeypatch.setattr(claude, "generate", lambda prompt, system=None, model=None: "claude result")

    result = provider.generate("hello", config={"ai_provider": "claude"})

    assert result == "claude result"


def test_provider_raises_clear_error_when_ai_provider_is_none():
    with pytest.raises(ValueError, match="ai_provider is 'none'"):
        provider.generate("hello", config={"ai_provider": "none"})


def test_provider_raises_clear_error_for_unsupported_provider():
    with pytest.raises(ValueError, match="ai_provider is 'ollama'"):
        provider.generate("hello", config={"ai_provider": "ollama"})
