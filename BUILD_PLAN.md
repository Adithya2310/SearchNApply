# Build Plan

Full module details are in DESIGN.md — this doc is just the build order and sequencing logic.

## Phase 1 — build first (unattended/passive scanning loop)

Goal: everything in this phase must be able to run without the user's laptop being on, and without any further AI credits being spent once it's live.

1. **Sheet schema + read/write layer** — build this first; every module below depends on it. Schema is in DESIGN.md Section 2 (5 tabs: Jobs, Applications, Contacts, Config, Watchlist).
2. **M2 — Resume Parser** — one-time parse of the user's resume into `resume_profile.json`.
3. **M1 — Job Aggregator** — Greenhouse/Lever/Adzuna/JSearch integrations, dedup logic.
4. **M4 — Matching/Scoring Engine** — design the scoring logic carefully (this benefits from stronger reasoning — use Opus for designing the algorithm even if Sonnet implements it). Score = skill overlap + salary fit + location fit.
5. **M5 — Gmail Digest Sender** — SMTP + App Password (not OAuth, keep it simple). Summarizes new matched jobs.
6. **M6 — Company Watchlist Monitor** — reuses M4's scoring logic. Separate, more frequent schedule than M1. Sends immediate standalone emails, not bundled into the M5 digest.
7. **GitHub Actions orchestration** — wire M1, M4, M5, M6 into scheduled workflows. Confirm they actually run end-to-end on the schedule before considering Phase 1 done.

**Definition of done for Phase 1:** the system finds jobs, scores them, and emails the user a digest — completely unattended — plus watchlisted companies trigger immediate alerts. No dashboard, no outreach, no contact-finding yet.

## Phase 2 — build second (active/decision-making side)

8. **M7 — Local Dashboard** (Streamlit). Tabs: Review, Log Manual Application, Update Profile, Tracker. Runs only when the user opens it — never scheduled.
9. **M3 — Profile Updater** — lives inside the M7 dashboard's "Update Profile" tab. Chat-based extraction (Sonnet) + mandatory diff approval before any write to `resume_profile.json`.
10. **M8 — Contact Finder** — Hunter.io/Apollo.io integration, checks `Contacts` sheet before re-querying.
11. **M9 — Resume Tailoring Engine** (Opus) — rewrites resume per job description.
12. **M10 — Outreach Generator** (Opus) — drafts recruiter email + LinkedIn message. Drafts only — never auto-sends.
13. **M11 — Analytics** — response rate by source/resume version/outreach style.
14. **M12 — Duplicate/Staleness Detector** — folds into M1's run, flags stale/reposted listings.
15. **M13 — Follow-up Reminder** — folds into the scheduled GitHub Actions run, surfaces in the M5 digest.
16. **M14 — AI Provider Config abstraction** — should ideally be designed alongside Phase 1 (M4 in particular), but full implementation/testing across all AI-calling modules happens here.
17. **Testing + README polish** — end-to-end run-through, make sure a future session (with or without this same AI) can pick the project up cleanly.

## Sequencing rules

- Don't start a module until its dependencies are working and tested — e.g. don't build M4 (Matching) before `resume_profile.json` exists from M2.
- Within Phase 1, prioritize "runs end-to-end, even if rough" over "polished." Polish is explicitly a Phase 2 concern.
- Model selection: Opus only for M4 (scoring logic design), M9 (resume tailoring), M10 (outreach generation) — everything else should default to Sonnet to conserve credits.
