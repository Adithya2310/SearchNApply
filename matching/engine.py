from .config import load_config
from .scorer import score_job
from .skills import build_vocabulary


def run_matching(client, resume_profile):
    """M4 — scores every unscored Jobs row and writes match_score back,
    auto-demoting weak matches to status=Ignored.

    Only processes rows where match_score is currently empty: idempotent
    across runs, and never clobbers a status the user (or M1's dedup) has
    already set. All writes go through one batched update_rows() call —
    see the M1 aggregator's read-quota lesson for why that matters once
    the Jobs sheet has any real volume.
    """
    config = load_config(client)
    vocabulary = build_vocabulary(resume_profile, config)
    threshold = config["match_threshold"]

    rows = client.get_rows("Jobs")
    to_score = [r for r in rows if not str(r.get("match_score", "")).strip()]

    updates_by_id = {}
    ignored = 0
    for row in to_score:
        result = score_job(row, vocabulary, config)
        updates = {"match_score": result["match_score"]}
        if result["match_score"] < threshold:
            updates["status"] = "Ignored"
            ignored += 1
        updates_by_id[row["job_id"]] = updates

    client.update_rows("Jobs", "job_id", updates_by_id)

    return {"scored": len(updates_by_id), "ignored": ignored}
