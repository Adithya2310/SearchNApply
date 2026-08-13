import json

from ai_provider.provider import generate

EMAIL_SYSTEM_PROMPT = """You draft a short, professional cold outreach email \
about a specific job the candidate wants to apply for or has just applied \
to. Rules:

- Plain text, no Markdown.
- Body: 3-5 short paragraphs max, professional but not stiff. Briefly \
introduce the candidate, reference the specific role/company, connect 1-2 \
real pieces of experience from the profile to what the job description \
asks for, and close with a clear, low-pressure ask (e.g. "I'd appreciate \
the chance to connect briefly").
- Ground every claim strictly in the provided profile JSON - never invent \
skills, employers, projects, or achievements that aren't in it.
- Sign off with the candidate's real name from the profile.
- If a contact name is given, address them by name ("Hi {name},"); if not, \
use a generic-but-warm greeting ("Hi there," or "Hello,") - never invent a \
fake name.
- Respond with ONLY a JSON object {"subject": "...", "body": "..."} - no \
prose, no markdown fences.
"""

LINKEDIN_SYSTEM_PROMPT = """You draft a LinkedIn connection request note \
about a specific job. LinkedIn enforces a hard 300-character limit on \
connection notes - your response MUST be 300 characters or fewer, \
including spaces. Rules:

- Plain text, one short paragraph, no line breaks, no Markdown.
- Reference the specific role/company and one real, relevant piece of \
experience from the profile - ground it strictly in the given profile \
JSON, never invent anything.
- Warm but brief - this is a connection request note, not an email.
- If a contact name is given, you may address them by first name; \
otherwise skip a greeting and start with the substance.
- Respond with ONLY the note text - no quotes, no prose, no markdown \
fences.
"""

LINKEDIN_MAX_CHARS = 300


def _build_prompt(resume_profile, job_description, company, role, contact_name):
    return (
        f"CANDIDATE PROFILE (JSON):\n{json.dumps(resume_profile, indent=2)}\n\n"
        f"COMPANY: {company}\nROLE: {role}\nCONTACT NAME: {contact_name or '(unknown)'}\n\n"
        f"JOB DESCRIPTION:\n{job_description}\n"
    )


def generate_email_draft(resume_profile, job_description, company, role, contact_name, config):
    prompt = _build_prompt(resume_profile, job_description, company, role, contact_name)
    raw = generate(prompt, system=EMAIL_SYSTEM_PROMPT, config=config)
    try:
        draft = json.loads(raw)
    except json.JSONDecodeError:
        raise ValueError(f"AI did not return valid JSON for the email draft: {raw!r}")
    if not isinstance(draft, dict) or "subject" not in draft or "body" not in draft:
        raise ValueError(f"AI response is missing subject/body: {raw!r}")
    return draft


def _enforce_linkedin_length(note):
    """Belt-and-suspenders: LinkedIn's 300-char cap is a hard platform
    constraint, not a style preference, and models don't reliably count
    characters exactly — truncate at a word boundary in code rather than
    trusting the prompt alone.
    """
    note = note.strip()
    if len(note) <= LINKEDIN_MAX_CHARS:
        return note
    truncated = note[: LINKEDIN_MAX_CHARS - 1].rsplit(" ", 1)[0]
    return truncated + "…"


def generate_linkedin_note(resume_profile, job_description, company, role, contact_name, config):
    prompt = _build_prompt(resume_profile, job_description, company, role, contact_name)
    raw = generate(prompt, system=LINKEDIN_SYSTEM_PROMPT, config=config)
    return _enforce_linkedin_length(raw)
