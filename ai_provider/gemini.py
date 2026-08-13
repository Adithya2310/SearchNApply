import os

from google import genai

DEFAULT_MODEL = "gemini-2.5-flash"


def _get_client(api_key):
    return genai.Client(api_key=api_key)


def generate(prompt, system=None, model=None, api_key=None):
    api_key = api_key or os.environ["GEMINI_API_KEY"]
    client = _get_client(api_key)
    config = {"system_instruction": system} if system else None
    response = client.models.generate_content(
        model=model or DEFAULT_MODEL,
        contents=prompt,
        config=config,
    )
    return response.text
