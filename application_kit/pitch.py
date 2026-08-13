import json

from ai_provider.provider import generate

PITCH_SYSTEM_PROMPT = """You write a short "why I'm interested in this role" \
blurb for a job application form, given a candidate's profile as JSON and \
a job description. Rules:

- 2-4 sentences, plain text, no Markdown, no bullet points.
- Ground every claim strictly in the profile JSON - do not invent skills, \
employers, projects, or achievements that aren't in it.
- Connect specific real experience from the profile to what the job \
description is actually asking for; do not write generic filler that \
could apply to any job.
- Output ONLY the blurb text - no preamble, no quotes around it.
"""


def generate_pitch(resume_profile, job_description, config):
    prompt = (
        f"CANDIDATE PROFILE (JSON):\n{json.dumps(resume_profile, indent=2)}\n\n"
        f"JOB DESCRIPTION:\n{job_description}\n"
    )
    return generate(prompt, system=PITCH_SYSTEM_PROMPT, config=config)
