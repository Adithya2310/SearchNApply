import json

from ai_provider.provider import generate
from matching.aliases import canonicalize

# Extracting "what skills does this JD ask for" is genuinely open-ended NLP
# — unlike matching/skills.py's scoring (which only ever scans for skills
# already in the *candidate's own* vocabulary against a fixed alias table),
# there's no fixed universe of every skill a JD might mention. So this one
# step uses the AI provider; the actual gap diff below is plain
# canonicalize()-based set comparison, same as the rest of the matching
# code, no AI needed for that part.
EXTRACT_SKILLS_SYSTEM_PROMPT = (
    "You extract the specific technical skills, tools, languages, and "
    "technologies explicitly required or strongly preferred by a job "
    'description. Respond with ONLY a JSON array of short skill name '
    'strings (e.g. ["Python", "Kubernetes", "AWS"]) - no prose, no markdown '
    "fences, nothing else. If none are mentioned, respond with []."
)


def extract_required_skills(job_description, config):
    """AI call: returns the JD's required skills in their original casing,
    for display — canonicalization happens separately when diffing.
    """
    raw = generate(job_description, system=EXTRACT_SKILLS_SYSTEM_PROMPT, config=config)
    try:
        skills = json.loads(raw)
    except json.JSONDecodeError:
        raise ValueError(f"AI did not return valid JSON for skill extraction: {raw!r}")
    if not isinstance(skills, list):
        raise ValueError(f"AI returned JSON that isn't a list: {raw!r}")
    return [s for s in (str(s).strip() for s in skills) if s]


def candidate_skill_set(resume_profile):
    """Every skill the profile already claims — languages, tools, and every
    role's tech_stack — canonicalized so lexical variants (React/ReactJS)
    don't produce a false gap.
    """
    skills_block = resume_profile.get("skills", {}) or {}
    names = list(skills_block.get("languages", []) or [])
    names += skills_block.get("technologies_tools", []) or []
    for exp in resume_profile.get("work_experience", []) or []:
        names += exp.get("tech_stack", []) or []
    return {canonicalize(n) for n in names if n and n.strip()}


def find_skill_gaps(job_description, resume_profile, config):
    """Required JD skills (original casing) the candidate's profile doesn't
    already cover.
    """
    required = extract_required_skills(job_description, config)
    known = candidate_skill_set(resume_profile)
    return [skill for skill in required if canonicalize(skill) not in known]
