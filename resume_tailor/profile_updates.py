from matching.aliases import canonicalize


def add_confirmed_skills(resume_profile, confirmed_skills):
    """Merges skills the user confirmed they actually have into the
    profile's technologies_tools list, deduped by canonical name. Mutates
    and returns resume_profile — the caller decides whether/when to persist
    to disk.

    This is the one part of gap resolution that writes to the profile at
    all, and only for skills the user explicitly confirmed in the moment —
    same "no unapproved write" principle as M3's diff-approval flow, just
    via a different trigger (M9's gap-resolution prompt instead of M3's
    chat box).
    """
    skills_block = resume_profile.setdefault("skills", {})
    tools = skills_block.setdefault("technologies_tools", [])
    existing_canonical = {canonicalize(t) for t in tools}
    for skill in confirmed_skills:
        if canonicalize(skill) not in existing_canonical:
            tools.append(skill)
            existing_canonical.add(canonicalize(skill))
    return resume_profile
