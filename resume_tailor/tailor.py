import copy
import json

from ai_provider.provider import generate

TAILOR_SYSTEM_PROMPT = """You are a resume tailoring assistant. You will be \
given a candidate's profile as JSON and a job description. Rewrite and \
reorder the candidate's resume content to best fit this specific role, \
following these rules strictly:

- ATS-friendly formatting ONLY: plain text, no tables, no columns, no \
graphics/icons/text boxes, no special characters beyond standard \
punctuation and bullet dashes ("-"). This explicitly means NO Markdown \
syntax anywhere in the output - no "**bold**", no "##headers", no "*" \
bullets, no backticks. Section headers are plain ALL CAPS text on their \
own line, nothing else.
- Standard section headers, in this order: SUMMARY, SKILLS, EXPERIENCE, \
PROJECTS, EDUCATION, ACHIEVEMENTS. Omit a section entirely if the profile \
has nothing for it.
- Reverse-chronological order within EXPERIENCE and EDUCATION.
- Every work_experience and education entry already has a precomputed \
"date_range" field. Use that string VERBATIM for its dates - do not \
reformat it, do not reason about "today's date", and never substitute \
"Present" unless date_range itself literally says "Present". This field \
exists specifically so you never have to infer whether a role is ongoing.
- Do NOT add any field, attribute, or detail that is not explicitly \
present in the profile JSON - this includes company/institution \
locations, addresses, or any other detail. If a company or institution \
in the profile has no location field, do not invent or guess one for it \
in the output.
- Every bullet starts with a strong action verb, preserves the profile's \
real quantified metrics, and does not invent experience, employers, \
dates, or metrics that aren't in the profile.
- Prioritize and lead with the skills/experience/projects most relevant to \
this job description; do not drop unrelated real experience, just \
reorder/de-emphasize it.
- Naturally weave in these keywords from the job description wherever \
truthfully supported by the profile: {keywords}
- Output ONLY the final resume text - no commentary before or after it.
"""


def _format_date_range(start_date, end_date):
    """Computed in code, not left to the model — an LLM asked to render
    dates will happily "helpfully" infer an ongoing role as "Present" even
    when the profile has a real end_date already in the past (confirmed
    live: it did this for a job that had genuinely already ended).
    """
    return f"{start_date or '?'} - {end_date}" if end_date else f"{start_date or '?'} - Present"


def _with_precomputed_date_ranges(resume_profile):
    profile = copy.deepcopy(resume_profile)
    for exp in profile.get("work_experience", []) or []:
        exp["date_range"] = _format_date_range(exp.get("start_date"), exp.get("end_date"))
    for edu in profile.get("education", []) or []:
        edu["date_range"] = _format_date_range(edu.get("start_date"), edu.get("end_date"))
    return profile


def tailor_resume(resume_profile, job_description, keywords, config):
    """AI call: the actual rewrite/reorder step. Skill-gap resolution
    (resume_tailor/gaps.py) must happen before this, so `keywords` can
    include whatever the user just confirmed they know — this call never
    decides on its own whether the candidate has a skill.
    """
    profile_for_prompt = _with_precomputed_date_ranges(resume_profile)
    prompt = (
        f"CANDIDATE PROFILE (JSON):\n{json.dumps(profile_for_prompt, indent=2)}\n\n"
        f"JOB DESCRIPTION:\n{job_description}\n"
    )
    system = TAILOR_SYSTEM_PROMPT.format(keywords=", ".join(keywords) if keywords else "(none)")
    return generate(prompt, system=system, config=config)
