# Column order per DESIGN.md Section 2. This is the source of truth for
# what gets written to each tab; SheetsClient enforces it.

SHEETS = {
    "Jobs": [
        "job_id",
        "source",
        "company",
        "title",
        "url",
        "location",
        "salary_range",
        "description_raw",
        "match_score",
        "date_found",
        "status",
    ],
    "Applications": [
        "app_id",
        "source_type",
        "linked_job_id",
        "company",
        "role",
        "job_url",
        "date_applied",
        "resume_version_used",
        "hr_name",
        "hr_email",
        "hr_linkedin",
        "outreach_sent",
        "outreach_message",
        "status",
        "last_update_date",
        "next_followup_date",
        "notes",
    ],
    "Contacts": [
        "contact_id",
        "name",
        "company",
        "email",
        "linkedin_url",
        "role_title",
        "last_contacted",
        "notes",
    ],
    # DESIGN.md describes Config as a flat set of tunables rather than a
    # fixed table, so it's modeled as key/value rows.
    "Config": [
        "key",
        "value",
        "notes",
    ],
    "Watchlist": [
        "company_name",
        "careers_source",
        "careers_identifier",
        "active",
        "last_checked",
        "notify_immediately",
    ],
}
