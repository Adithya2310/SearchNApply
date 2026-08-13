"""M7 — Local Dashboard.

    streamlit run dashboard.py

Runs only when you open it — never scheduled, unlike the GitHub Actions
side. Review + Tracker are live; Log Manual Application and Update Profile
are stubs until M3 is built (see BUILD_PLAN.md's reprioritized order).
"""

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from sheets.client import SheetsClient
from sheets.schema import SHEETS

load_dotenv()

st.set_page_config(page_title="Job Search Dashboard", layout="wide")

JOBS_STATUSES = ["New", "Reviewed", "Ignored", "Moved to Applications"]
APPLICATIONS_STATUSES = [
    "Interested",
    "Applied",
    "In Outreach",
    "Response Received",
    "Interview",
    "Rejected",
    "Offer",
    "No Response",
]


@st.cache_resource
def get_client():
    return SheetsClient()


def _today():
    return datetime.now(timezone.utc).date().isoformat()


def _safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


def _find_applications_row_for_job(client, job_id):
    for row in client.get_rows("Applications"):
        if row.get("linked_job_id") == job_id:
            return row
    return None


def mark_interested(client, job_row):
    """Creates (or re-flags) the linked Applications row and flips the Jobs
    row to Moved to Applications — see DESIGN.md's M7 note for why that
    status value exists.
    """
    job_id = job_row["job_id"]
    existing = _find_applications_row_for_job(client, job_id)
    if existing:
        client.update_row(
            "Applications", "app_id", existing["app_id"], {"status": "Interested", "last_update_date": _today()}
        )
    else:
        client.append_row(
            "Applications",
            {
                "app_id": uuid.uuid4().hex[:16],
                "source_type": "auto-discovered",
                "linked_job_id": job_id,
                "company": job_row.get("company", ""),
                "role": job_row.get("title", ""),
                "job_url": job_row.get("url", ""),
                "outreach_sent": "N",
                "status": "Interested",
                "last_update_date": _today(),
            },
        )
    client.update_row("Jobs", "job_id", job_id, {"status": "Moved to Applications"})


def mark_ignored(client, job_row):
    client.update_row("Jobs", "job_id", job_row["job_id"], {"status": "Ignored"})


def render_review_tab(client):
    st.subheader("Review new matches")
    rows = client.get_rows("Jobs")

    status_filter = st.multiselect(
        "Show statuses", JOBS_STATUSES, default=["New", "Reviewed"], key="review_status_filter"
    )
    visible = [r for r in rows if r.get("status") in status_filter]
    visible.sort(key=lambda r: -_safe_int(r.get("match_score")))

    st.caption(f"{len(visible)} job(s)")

    for row in visible:
        with st.container(border=True):
            cols = st.columns([6, 1, 1])
            with cols[0]:
                st.markdown(f"**{row.get('title', '')}** — {row.get('company', '')}")
                st.caption(
                    f"{row.get('location') or 'location n/a'} · "
                    f"score {row.get('match_score') or '?'} · status {row.get('status', '')}"
                )
                if row.get("url"):
                    st.markdown(f"[View posting]({row['url']})")
                if row.get("description_raw"):
                    with st.expander("Description"):
                        st.write(row["description_raw"][:3000])
            with cols[1]:
                if st.button("Interested", key=f"interested_{row['job_id']}"):
                    mark_interested(client, row)
                    st.rerun()
            with cols[2]:
                if st.button("Ignore", key=f"ignore_{row['job_id']}"):
                    mark_ignored(client, row)
                    st.rerun()


def render_tracker_tab(client):
    st.subheader("Applications tracker")
    rows = client.get_rows("Applications")
    if not rows:
        st.info("No applications logged yet — mark a job Interested in the Review tab to get started.")
        return

    columns = SHEETS["Applications"]
    df = pd.DataFrame(rows).reindex(columns=columns, fill_value="")

    edited = st.data_editor(
        df,
        key="tracker_editor",
        num_rows="fixed",
        disabled=["app_id", "source_type", "linked_job_id"],
        column_config={
            "status": st.column_config.SelectboxColumn("status", options=APPLICATIONS_STATUSES),
            "outreach_sent": st.column_config.SelectboxColumn("outreach_sent", options=["Y", "N"]),
            "notes": st.column_config.TextColumn("notes", width="large"),
        },
        width="stretch",
    )

    if st.button("Save changes"):
        original_by_id = {row["app_id"]: row for row in rows}
        updates = {}
        for _, edited_row in edited.iterrows():
            app_id = edited_row["app_id"]
            original = original_by_id.get(app_id, {})
            changed = {
                col: edited_row[col]
                for col in columns
                if col != "app_id" and str(edited_row[col]) != str(original.get(col, ""))
            }
            if changed:
                changed["last_update_date"] = _today()
                updates[app_id] = changed

        if updates:
            client.update_rows("Applications", "app_id", updates)
            st.success(f"Saved changes to {len(updates)} row(s).")
            st.rerun()
        else:
            st.info("No changes to save.")


def main():
    client = get_client()
    st.title("Job Search Dashboard")

    tab_review, tab_tracker, tab_log, tab_profile = st.tabs(
        ["Review", "Tracker", "Log Manual Application", "Update Profile"]
    )
    with tab_review:
        render_review_tab(client)
    with tab_tracker:
        render_tracker_tab(client)
    with tab_log:
        st.info("Coming soon — manual application logging isn't built yet.")
    with tab_profile:
        st.info("Coming soon — M3 Profile Updater isn't built yet.")


if __name__ == "__main__":
    main()
