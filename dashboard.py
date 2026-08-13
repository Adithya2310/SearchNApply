"""M7 — Local Dashboard.

    streamlit run dashboard.py

Runs only when you open it — never scheduled, unlike the GitHub Actions
side. Review, Tracker, Apply Kit, and Update Profile are live; Log Manual
Application is still a stub.
"""

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from application_kit.fields import build_fields
from application_kit.pitch import generate_pitch
from matching.config import load_config
from profile_updater.apply import add_bullet_to_project, add_bullet_to_work_experience, add_new_project
from profile_updater.extract import extract_update
from profile_updater.log import append_log_entry
from resume_tailor.profile_updates import add_confirmed_skills
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


def _resume_profile_path(client):
    # load_config() only exposes M4's scoring keys, not resume_profile_path
    # — same reason scripts/run_matching.py, scripts/tailor_resume.py, etc.
    # read it from a raw Config dict instead.
    config_rows = {r["key"]: r["value"] for r in client.get_rows("Config") if r.get("key")}
    return config_rows.get("resume_profile_path") or "resume_profile.json"


def _load_resume_profile(client):
    with open(_resume_profile_path(client)) as f:
        return json.load(f)


def _save_resume_profile(client, resume_profile):
    with open(_resume_profile_path(client), "w") as f:
        json.dump(resume_profile, f, indent=2)
        f.write("\n")


def render_apply_kit_tab(client):
    st.subheader("Apply Kit")
    st.caption(
        "Copy-paste-ready values for a real application form — generated from your profile, "
        "not submitted anywhere. You still log in and paste these yourself."
    )
    app_rows = client.get_rows("Applications")
    if not app_rows:
        st.info("No applications yet — mark a job Interested in the Review tab first.")
        return

    labels = [f"{r.get('company', '')} — {r.get('role', '')} ({r.get('status', '')})" for r in app_rows]
    choice = st.selectbox("Application", options=range(len(app_rows)), format_func=lambda i: labels[i])
    app_row = app_rows[choice]

    resume_profile = _load_resume_profile(client)
    config = load_config(client)

    job_info = {"company": app_row.get("company", ""), "title": app_row.get("role", ""), "url": app_row.get("job_url", "")}
    fields = build_fields(
        resume_profile, job_info, config=config, resume_filename=app_row.get("resume_version_used") or None
    )

    for label, value in fields:
        st.caption(label)
        st.code(value or "(blank)", language=None)

    st.divider()
    st.markdown("**Why I'm interested (AI-generated, review before pasting)**")

    linked_job = None
    if app_row.get("linked_job_id"):
        linked_job = next((r for r in client.get_rows("Jobs") if r["job_id"] == app_row["linked_job_id"]), None)

    pitch_key = f"pitch_{app_row['app_id']}"
    if linked_job and linked_job.get("description_raw"):
        if st.button("Generate pitch", key=f"generate_{app_row['app_id']}"):
            job_description = f"{linked_job.get('title', '')}\n\n{linked_job['description_raw']}"
            st.session_state[pitch_key] = generate_pitch(resume_profile, job_description, config)
        if pitch_key in st.session_state:
            st.code(st.session_state[pitch_key], language=None)
    else:
        st.info("No job description linked to this application — can't generate a pitch for it yet.")


def _target_options(resume_profile):
    options = [("work_experience", exp.get("company", "")) for exp in resume_profile.get("work_experience", []) or []]
    options += [("project", proj.get("name", "")) for proj in resume_profile.get("projects", []) or []]
    options.append(("new_project", None))
    return options


def _target_label(option):
    target_type, name = option
    if target_type == "new_project":
        return "New project"
    prefix = "Work experience" if target_type == "work_experience" else "Project"
    return f"{prefix}: {name}"


def _default_target_index(options, proposal):
    suggested_type = proposal.get("suggested_target_type")
    suggested_name = (proposal.get("suggested_target_name") or "").strip().lower()
    for i, (target_type, name) in enumerate(options):
        if target_type == suggested_type and (name or "").strip().lower() == suggested_name:
            return i
    return len(options) - 1  # "New project" is always last


def render_update_profile_tab(client):
    st.subheader("Update Profile")
    st.caption(
        "Tell it about something you did — a work task, a side project — and it proposes a resume "
        "update for you to review. Nothing is saved to resume_profile.json until you approve it."
    )

    raw_text = st.text_area("What did you do?", key="profile_update_text", height=100)
    if st.button("Analyze", key="analyze_profile_update"):
        if not raw_text.strip():
            st.warning("Type something first.")
        else:
            resume_profile = _load_resume_profile(client)
            config = load_config(client)
            with st.spinner("Analyzing..."):
                proposal = extract_update(raw_text, resume_profile, config)
            st.session_state["profile_update_proposal"] = proposal
            st.session_state["profile_update_raw_text"] = raw_text

    proposal = st.session_state.get("profile_update_proposal")
    if not proposal:
        return

    st.divider()
    st.markdown("**Review before saving**")

    resume_profile = _load_resume_profile(client)
    selected_skills = st.multiselect(
        "Skills to add", options=proposal.get("skills") or [], default=proposal.get("skills") or []
    )

    bullet_text = ""
    target = None
    if proposal.get("bullet"):
        options = _target_options(resume_profile)
        default_index = _default_target_index(options, proposal)
        target = st.selectbox(
            "Add this bullet to", options=options, index=default_index, format_func=_target_label
        )
        if target[0] == "new_project":
            new_project_name = st.text_input(
                "New project name", value=proposal.get("suggested_target_name") or ""
            )
            target = ("new_project", new_project_name)
        bullet_text = st.text_area("Bullet text", value=proposal.get("bullet") or "", key="profile_update_bullet")

    col_approve, col_reject = st.columns(2)
    with col_approve:
        approve_clicked = st.button("Approve and save", type="primary")
    with col_reject:
        reject_clicked = st.button("Reject")

    if reject_clicked:
        append_log_entry(st.session_state["profile_update_raw_text"], proposal, decision="rejected")
        del st.session_state["profile_update_proposal"]
        st.info("Discarded — nothing written.")
        st.rerun()

    if approve_clicked:
        applied = {"skills": selected_skills, "bullet": None}
        if selected_skills:
            add_confirmed_skills(resume_profile, selected_skills)

        if bullet_text.strip() and target:
            target_type, target_name = target
            if not target_name or not target_name.strip():
                st.warning("New project needs a name before this can be saved.")
                return
            if target_type == "work_experience":
                add_bullet_to_work_experience(resume_profile, target_name, bullet_text.strip())
            elif target_type == "project":
                add_bullet_to_project(resume_profile, target_name, bullet_text.strip())
            else:
                add_new_project(resume_profile, target_name, bullet_text.strip())
            applied["bullet"] = {"target_type": target_type, "target_name": target_name, "text": bullet_text.strip()}

        _save_resume_profile(client, resume_profile)

        edited = selected_skills != (proposal.get("skills") or []) or bullet_text.strip() != (proposal.get("bullet") or "")
        append_log_entry(
            st.session_state["profile_update_raw_text"],
            proposal,
            decision="edited" if edited else "approved",
            applied=applied,
        )
        del st.session_state["profile_update_proposal"]
        st.success("Saved to resume_profile.json.")
        st.rerun()


def main():
    client = get_client()
    st.title("Job Search Dashboard")

    tab_review, tab_tracker, tab_apply, tab_log, tab_profile = st.tabs(
        ["Review", "Tracker", "Apply Kit", "Log Manual Application", "Update Profile"]
    )
    with tab_review:
        render_review_tab(client)
    with tab_tracker:
        render_tracker_tab(client)
    with tab_apply:
        render_apply_kit_tab(client)
    with tab_log:
        st.info("Coming soon — manual application logging isn't built yet.")
    with tab_profile:
        render_update_profile_tab(client)


if __name__ == "__main__":
    main()
