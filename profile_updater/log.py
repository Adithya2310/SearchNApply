import json
from datetime import datetime, timezone

DEFAULT_LOG_PATH = "profile_updates_log.jsonl"


def append_log_entry(raw_input, proposed, decision, applied=None, log_path=None):
    """One line per decision — approved/edited/rejected, plus the original
    raw input and what the AI actually proposed. This is the audit trail
    DESIGN.md's M3 spec calls for: how the profile evolved, and an easy
    undo path if something slips through wrong.
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "raw_input": raw_input,
        "proposed": proposed,
        "decision": decision,
        "applied": applied,
    }
    with open(log_path or DEFAULT_LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry
