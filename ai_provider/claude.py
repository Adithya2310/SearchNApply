import os

import anthropic

# Not live-tested — no ANTHROPIC_API_KEY provisioned for this project yet
# (it's a paid key, separate from Claude Code credits, per
# API_KEYS_NEEDED.md). Written to the same generate() interface as
# gemini.py so switching Config.ai_provider to "claude" later needs no
# code change elsewhere, but treat this path as unverified until a real
# key exists and it's been run against a real request.
DEFAULT_MODEL = "claude-sonnet-4-5"
DEFAULT_MAX_TOKENS = 4096


def _get_client(api_key):
    return anthropic.Anthropic(api_key=api_key)


def generate(prompt, system=None, model=None, api_key=None):
    api_key = api_key or os.environ["ANTHROPIC_API_KEY"]
    client = _get_client(api_key)
    kwargs = {"system": system} if system else {}
    message = client.messages.create(
        model=model or DEFAULT_MODEL,
        max_tokens=DEFAULT_MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
        **kwargs,
    )
    return "".join(block.text for block in message.content if block.type == "text")
