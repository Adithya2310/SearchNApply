import json

from ai_provider.provider import generate

EXTRACT_SYSTEM_PROMPT = """You help update a candidate's resume profile from \
a short piece of free text they just wrote about something they did. Given \
their current profile (JSON) and the free text, extract:

- skills: a list of distinct skill/technology names the text demonstrates \
that are NOT already in the profile's skills (languages or \
technologies_tools). Empty list if none.
- bullet: a single achievement-style resume bullet capturing what the text \
describes, in the same voice as the profile's existing bullets (action-verb \
start, quantified if the text has numbers/impact). Null if the text \
doesn't describe a concrete achievement worth a bullet.
- suggested_target_type: one of "work_experience", "project", or \
"new_project" - your best guess at where this bullet belongs, from the \
text's own clues (e.g. "at work" -> most recent work_experience; "side \
project" -> project or new_project if no existing project matches).
- suggested_target_name: the company name (if work_experience) or project \
name (if project/new_project) your best guess refers to.

Respond with ONLY a JSON object with exactly these four keys: skills, \
bullet, suggested_target_type, suggested_target_name. No prose, no \
markdown fences.
"""

REQUIRED_KEYS = {"skills", "bullet", "suggested_target_type", "suggested_target_name"}


def extract_update(raw_text, resume_profile, config):
    """AI call: turns a short piece of free text into a structured proposal
    (skills demonstrated + a candidate bullet + a best-guess home for it).
    Never writes anything itself — the caller shows this as a diff for the
    user to approve/edit/reject before anything touches resume_profile.json.
    """
    prompt = (
        f"CURRENT PROFILE (JSON):\n{json.dumps(resume_profile, indent=2)}\n\n"
        f"FREE TEXT:\n{raw_text}\n"
    )
    raw = generate(prompt, system=EXTRACT_SYSTEM_PROMPT, config=config)
    try:
        proposal = json.loads(raw)
    except json.JSONDecodeError:
        raise ValueError(f"AI did not return valid JSON for profile update extraction: {raw!r}")
    if not isinstance(proposal, dict) or not REQUIRED_KEYS.issubset(proposal):
        raise ValueError(f"AI response is missing required keys {REQUIRED_KEYS}: {raw!r}")
    return proposal
