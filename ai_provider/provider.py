from . import claude, gemini

# M14 — the one place every AI-calling module (M3, M4, M9, M10) should
# route through. Config.ai_provider picks the backend and Config.ai_model
# optionally overrides that backend's default model — both read from the
# Sheet, so swapping providers/models is a Config edit, not a code change,
# and will be directly wireable to a dropdown once M7's UI exists.
PROVIDERS = {"gemini": gemini, "claude": claude}


def generate(prompt, system=None, config=None):
    config = config or {}
    provider_name = (config.get("ai_provider") or "none").strip().lower()
    provider = PROVIDERS.get(provider_name)
    if provider is None:
        raise ValueError(
            f"Config.ai_provider is '{provider_name}', which has no generative "
            f"backend — this task needs a real model. Set it to one of: "
            f"{', '.join(sorted(PROVIDERS))}."
        )
    return provider.generate(prompt, system=system, model=config.get("ai_model") or None)
