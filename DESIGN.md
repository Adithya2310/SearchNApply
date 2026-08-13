# Job Search Suite — System Design

## 1. Core principle

**One data store, two entry points.**

Everything — jobs the system finds automatically, and jobs you apply to manually — lands in the *same* Google Sheet with the *same* schema. The system doesn't care how an application started; it only cares about its current state. This is what makes analytics, follow-up reminders, and "come back to this later" all work uniformly.

---

## 2. Data layer — Google Sheet (single source of truth)

**Sheet 1: `Jobs`** (raw scan results, auto-populated)
| Column | Notes |
|---|---|
| job_id | hash of company+title+url, for dedup |
| source | greenhouse / lever / adzuna / jsearch |
| company | |
| title | |
| url | |
| location | |
| salary_range | if available |
| description_raw | |
| match_score | computed by matching engine |
| date_found | |
| status | `New` / `Reviewed` / `Ignored` / `Moved to Applications` |

**Sheet 2: `Applications`** (the unified tracker — this is the important one)
| Column | Notes |
|---|---|
| app_id | |
| source_type | `auto-discovered` or `manual` |
| linked_job_id | blank if manual and no matching Jobs row |
| company | |
| role | |
| job_url | |
| date_applied | |
| resume_version_used | filename/version tag |
| hr_name | |
| hr_email | |
| hr_linkedin | |
| outreach_sent | Y/N |
| outreach_message | what you actually sent, for your records |
| status | `Interested` / `Applied` / `In Outreach` / `Response Received` / `Interview` / `Rejected` / `Offer` / `No Response` |
| last_update_date | |
| next_followup_date | |
| notes | free text |

**Sheet 3: `Contacts`** (reusable — a recruiter might recur across postings)
| Column | Notes |
|---|---|
| contact_id | |
| name | |
| company | |
| email | |
| linkedin_url | |
| role_title | e.g. "Technical Recruiter" |
| last_contacted | |
| notes | |

**Sheet 4: `Config`**
Your skills list, salary range, target roles/locations, resume file path, AI provider setting (claude/gemini/none). One place to tune the whole system without touching code.

**Sheet 5: `Watchlist`** (companies you want tracked specifically)
| Column | Notes |
|---|---|
| company_name | e.g. "Microsoft" |
| careers_source | greenhouse / lever / workday / custom-scrape — however that company exposes jobs |
| careers_identifier | company slug/board ID needed to query that source |
| active | Y/N — pause without deleting |
| last_checked | |
| notify_immediately | Y/N — default Y, since the point of watching a specific company is not missing it

---

## 3. Every module — trigger, input, process, output

### Auto-discovery side (runs on schedule, no laptop needed)

**M1 — Job Aggregator**
- *Trigger:* GitHub Actions, every 15–30 min
- *Input:* Config sheet (target roles, salary, location)
- *Process:* Calls Greenhouse/Lever/Adzuna/JSearch APIs, dedupes by job_id
- *Output:* New rows in `Jobs` sheet, status `New`

**M2 — Resume Parser** *(runs once, or whenever you update your resume)*
- *Trigger:* Manual, when resume changes
- *Input:* Your resume file
- *Process:* Extracts skills, experience, achievements into structured JSON
- *Output:* `resume_profile.json`, used by M3, M4, and M9

**M3 — Profile Updater**
- *Trigger:* Whenever you have something new to add — no schedule, purely on-demand
- *Input:* Free-form text you type, e.g. *"shipped a Kafka-based event pipeline handling 2M messages/day at work"* or *"built a side project doing X with React and Postgres"*
- *Process:*
  - AI reads the text against your current `resume_profile.json`
  - Extracts: what skill(s) this demonstrates, which project/role it belongs under (asks you if ambiguous — e.g. "is this part of your current job at X, or a new entry?"), and a quantified achievement bullet if your input has numbers/impact in it
  - Shows you the proposed diff before saving anything — e.g. "Add skill: Kafka. Add bullet to 'Backend Engineer, CompanyX': ..." — you approve as-is, edit the wording inline, reject individual lines, or reject the whole thing
  - Nothing is written to `resume_profile.json` until you approve it
- *Output:*
  - On approval: the confirmed changes get merged into `resume_profile.json`
  - Every decision (approved/edited/rejected) plus the original raw input is kept in `profile_updates_log.jsonl` — a full audit trail of how your profile evolved, and an easy undo path if something slips through wrong
- *Where this lives:* the "Update Profile" tab in the M7 dashboard — a chat box, with the diff/approval view shown right below it in the same flow. Sonnet is the right model for the extraction step — simple structured-output work, not deep reasoning. The approval step itself needs no AI at all, it's just you reviewing a diff.
- *Implemented* (Aug 13, 2026) as `profile_updater/` (`extract.py` — the one AI call, via M14; `apply.py` — pure functions to merge a skill list or a bullet into an existing work_experience/project or a brand-new project; `log.py` — the `profile_updates_log.jsonl` audit trail), wired into `dashboard.py`'s Update Profile tab. Uses Gemini (same M14 abstraction as M9), not Sonnet specifically, since Config.ai_provider is the actual dispatch point regardless of which model DESIGN.md originally called out. "Ambiguous target" is resolved via a selectbox defaulting to the AI's best guess, not a conversational follow-up question — same practical effect (you resolve it), simpler to build in Streamlit's rerun-per-interaction model.

**M4 — Matching/Scoring Engine**
- *Trigger:* Right after M1 finds new jobs
- *Input:* New `Jobs` rows + `resume_profile.json` + Config criteria
- *Process:* Scores each job (skill overlap, salary fit, location fit)
- *Output:* `match_score` filled in on `Jobs` sheet; low scores auto-marked `Ignored`

**M5 — Gmail Digest Sender**
- *Trigger:* End of each GitHub Actions run (or once daily, your choice)
- *Input:* `Jobs` rows with status `New` and match_score above threshold
- *Process:* Formats a summary email
- *Output:* Email to your inbox with job list + links; marks rows `Reviewed`

**M6 — Company Watchlist Monitor**
- *Trigger:* GitHub Actions, separate schedule from M1 — can run more frequently (e.g. every 5–10 min) since it's checking a small, fixed list rather than broad search
- *Input:* Active rows in `Watchlist` sheet
- *Process:*
  - Queries each company's career page directly using its `careers_source`/`careers_identifier`. Companies on Greenhouse/Lever/Workday expose clean, queryable job boards — this is easy and reliable. Companies with only a custom careers page need lightweight scraping, which is more fragile and may need occasional fixing if they redesign their site.
  - Runs every new listing through the same M4 matching engine (same skills/salary criteria — no separate logic needed)
- *Output:*
  - Matches get added to `Jobs` (tagged `source = watchlist:<company>`) **and** trigger an immediate standalone email — not bundled into the M5 daily digest, since the whole point is speed for a company you specifically care about
  - Non-matches are still logged (silently) to `Jobs` so you can see later that a role existed even if it didn't clear your bar, in case your criteria change

*Note on setup effort:* the actual API/scrape logic for a company is written once per company, then reused. Microsoft, being large, almost certainly runs one of the standard ATS platforms (worth checking in Claude Code which one, since that determines the integration path) rather than needing custom scraping.

### Manual/decision side (runs on your laptop, only when you choose)

**M7 — Local Dashboard** (Streamlit, opens in browser on your machine)
- *Trigger:* You run `streamlit run dashboard.py`
- *Views:*
  - **Review tab** — see `Jobs` rows, mark `Interested` or `Ignored`. Marking `Interested` creates the `Applications` row (`source_type = auto-discovered`, `linked_job_id` set, `status = Interested`) — this is the one moment a Jobs row and an Applications row get linked automatically — and flips the Jobs row's own status to `Moved to Applications` (this is what that status value is for). Marking `Ignored` just sets `Jobs.status = Ignored`, no Applications row.
  - **Log Manual Application tab** — a form: company, role, URL, HR name/email/LinkedIn, resume version, date, notes. Submitting writes directly into `Applications` with `source_type = manual`
  - **Update Profile tab** — chat box for M3; see the proposed diff and approve/edit/reject before anything is saved to `resume_profile.json`
  - **Tracker tab** — view/edit all `Applications` rows, update status as things progress
  - **Process button** — triggers M8–M10 for anything marked `Interested`

**M8 — Contact Finder**
- *Trigger:* You click "Process" in dashboard for a given job
- *Input:* Company name + role
- *Process:* Queries Hunter.io/Apollo for recruiter name/email; checks `Contacts` sheet first to avoid re-lookup
- *Output:* Fills `hr_name`, `hr_email`, `hr_linkedin` in `Applications`; adds/updates `Contacts` row

**M9 — Resume Tailoring Engine** *(Gemini by default, swappable — see M14)*
- *Trigger:* Same "Process" click in M7 (dashboard not built yet — for now, `scripts/tailor_resume.py --job-id <id>` or `--jd-file <path>`)
- *Input:* Job description + `resume_profile.json` + `Config.ai_provider`/`ai_model`
- *Process, three steps, not a single one-shot generate:*
  1. **Gap detection** (`resume_tailor/gaps.py`) — one AI call extracts the JD's required skills as a list; diffed (via `matching/aliases.canonicalize`, same alias-collapsing used for scoring) against everything already in `resume_profile.json` to find genuine gaps.
  2. **Interactive resolution** — for each gap skill, the user is asked: already know it (add to profile + resume), planning to learn it (noted, not added to either), or skip. Confirmed skills are merged into `resume_profile.json` immediately — this *is* the approval step, same principle as M3's diff-approval, just triggered from M9 instead of the chat box.
  3. **Tailoring** (`resume_tailor/tailor.py`) — a second AI call rewrites/reorders resume content against the JD, given the now-current profile and the resolved skill list as keywords to weave in.
- *Output:* An ATS-friendly (plain text, standard section headers, no tables/graphics) tailored resume file under `tailored_resumes/`, shown to the user for review before being written; filename logged in `Applications.resume_version_used` if a linked Applications row already exists.

**M10 — Outreach Generator** *(Opus)*
- *Trigger:* Same "Process" click
- *Input:* Job description + contact info + your resume profile
- *Process:* Drafts recruiter email + LinkedIn connection message
- *Output:* Draft shown in dashboard for your review/edit; you send manually; once sent, you mark `outreach_sent = Y` and paste the final version into `outreach_message`
- *Implemented* (Aug 13, 2026) as `outreach/generate.py` (Gemini via M14, not Opus specifically — same rationale as M9/M3), wired into the Apply Kit tab right below M9's pitch section. Two independent drafts, generated on demand: an email (subject + body, JSON) and a LinkedIn connection note — the latter has LinkedIn's hard 300-character cap enforced in code (truncated at a word boundary), not just asked for in the prompt, since models don't count characters reliably. "Contact info" from M8 is optional, not required — M8 itself was deprioritized (see BUILD_PLAN.md: paid API, low expected value for the mostly-large-enterprise target list), so drafts fall back to a generic-but-warm greeting when no contact name exists rather than blocking on it. Marking either draft "sent" appends to `Applications.outreach_message` (not overwrites), so sending both an email and a LinkedIn note for the same application keeps both records.

### Support modules (run quietly in the background)

**M11 — Analytics**
- *Trigger:* On demand, dashboard tab
- *Input:* All `Applications` rows
- *Process:* Response rate by source (manual vs auto), by resume version, by outreach style
- *Output:* Simple charts — tells you what's actually working

**M12 — Duplicate/Staleness Detector**
- *Trigger:* Part of M1's run
- *Process:* Flags jobs open >60 days or reposted listings as lower priority in scoring

**M13 — Follow-up Reminder**
- *Trigger:* Daily, part of the scheduled GitHub Actions run
- *Input:* `Applications` rows where `next_followup_date` has passed and status isn't terminal (Rejected/Offer)
- *Output:* Included in the Gmail digest — "3 applications need a follow-up today"
- *Why this matters for manual logging:* this is the actual payoff of logging manual applications — you stop losing track of the ones you applied to outside the system

**M14 — AI Provider Config**
- Not a "module" you interact with — an abstraction layer every AI-calling module (M3, M4, M9, M10) reads from. Implemented as `ai_provider/provider.py`, dispatching on `Config.ai_provider` (`claude` / `gemini` / `none`) with an optional `Config.ai_model` override per provider. Since it reads the Sheet, not an env var, switching provider/model is a Config edit — and will be directly wireable to a dropdown once M7's UI exists, with no code change either way.
- `ai_provider/gemini.py` is live (in use by M9 as of Aug 13, 2026). `ai_provider/claude.py` is code-complete but not live-tested — no `ANTHROPIC_API_KEY` provisioned yet.

---

## 4. How manual logging actually plays out in practice

1. You apply to a job directly on a company's careers page (never touched the system)
2. Open the dashboard → "Log Manual Application" tab → fill in what you have (even just company + role + date, HR details optional if you don't have them yet)
3. It's now a first-class row in `Applications`, same as system-discovered ones
4. Later, if you find the recruiter's LinkedIn separately, you edit that row and add it — or run M8 (Contact Finder) against it manually
5. M13 (Follow-up Reminder) picks it up automatically going forward, same as anything else

No separate system, no separate spreadsheet to remember — everything ages through the same pipeline once it's logged.

---

## 5. Build phases (credit-expiry aware)

**Phase 1 — TODAY, before Aug 12 UTC cutoff ($100 batch, expires ~Aug 12 5:30 AM IST):**
Priority: get the *passive scanning loop* live, since that runs unattended and keeps working even after credits are gone.
1. M2 Resume Parser
2. M1 Job Aggregator
3. M4 Matching Engine (Opus for scoring logic design, Sonnet to implement)
4. Sheet schema (all 5 tabs) + read/write layer
5. M5 Gmail Digest
6. M6 Company Watchlist Monitor (reuses M4's matching logic — cheap to add once M4 exists)
7. GitHub Actions wired up and confirmed running on schedule for both M1 and M6

**Phase 2 — Aug 13–18 ($100 batch):**
8. M7 Dashboard (including manual logging tab — build this early in phase 2, it's high value and low cost)
9. M3 Profile Updater (lives inside M7, build it alongside the dashboard)
10. M8 Contact Finder
11. M9 Resume Tailoring (Opus)
12. M10 Outreach Generator (Opus)
13. M11 Analytics
14. M12 Staleness Detector
15. M13 Follow-up Reminder
16. M14 AI Provider Config abstraction
17. Testing + README

---

## 6. Right now, in order

1. Open Claude Code
2. Paste in the Sheet schema from Section 2 — have it create the Sheets API read/write layer first, since every other module depends on it
3. Then M2 → M1 → M4 → M5 → GitHub Actions, in that order
4. Stop polishing anything once it works — Phase 1's only goal today is "running unattended," not "pretty"
