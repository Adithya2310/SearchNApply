def find_work_experience(resume_profile, company_name):
    for exp in resume_profile.get("work_experience", []) or []:
        if (exp.get("company") or "").strip().lower() == (company_name or "").strip().lower():
            return exp
    return None


def find_project(resume_profile, project_name):
    for proj in resume_profile.get("projects", []) or []:
        if (proj.get("name") or "").strip().lower() == (project_name or "").strip().lower():
            return proj
    return None


def add_bullet_to_work_experience(resume_profile, company_name, bullet):
    exp = find_work_experience(resume_profile, company_name)
    if exp is None:
        raise ValueError(f"No work_experience entry for company '{company_name}'")
    exp.setdefault("bullets", []).append(bullet)
    return resume_profile


def add_bullet_to_project(resume_profile, project_name, bullet):
    """Projects are stored as a single description string, not a bullets
    list (unlike work_experience) — append as a new sentence rather than
    introducing a second shape for the same kind of data.
    """
    proj = find_project(resume_profile, project_name)
    if proj is None:
        raise ValueError(f"No project entry named '{project_name}'")
    existing = (proj.get("description") or "").strip()
    proj["description"] = f"{existing} {bullet}".strip() if existing else bullet
    return resume_profile


def add_new_project(resume_profile, project_name, bullet):
    resume_profile.setdefault("projects", []).append({"name": project_name, "description": bullet, "links": {}})
    return resume_profile
