import hashlib


def compute_job_id(company, title, url):
    """job_id = hash of company+title+url, per DESIGN.md Section 2."""
    key = f"{(company or '').strip().lower()}|{(title or '').strip().lower()}|{(url or '').strip().lower()}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
