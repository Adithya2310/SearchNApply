# Build Plan

Full module details are in DESIGN.md. This doc is the build order/sequencing — and now, the current status.

## Phase 1 — COMPLETE, verified live (Aug 12, 2026)

All 7 items done, committed, pushed to GitHub, and confirmed running unattended:
- Sheets schema + read/write layer (5 tabs)
- M2 Resume Parser
- M1 Job Aggregator (Greenhouse/Lever/Adzuna/JSearch)
- M4 Matching/Scoring Engine (rule-based, `ai_provider=none` at runtime — confirmed zero API dependency)
- M5 Gmail Digest Sender
- M6 Company Watchlist Monitor
- GitHub Actions orchestration (`scan.yml` every ~30min, `watchlist.yml` every ~10min)

**Verified**: both workflows have run automatically on schedule with no failures, Jobs sheet is populating, digest emails are arriving unprompted.

**Known cleanup items, not blocking, low priority:**
- `Config.greenhouse_boards`/`lever_companies` still hold placeholder test values (`greenhouse`/`palantir`) — clear these, wasted scan capacity otherwise
- 5 of 7 Watchlist companies (Oracle, Qualcomm, FM Global, Microsoft, Google) are `inactive` — custom in-house ATS, no scraper built yet.

**Watchlist scaling (Aug 13, 2026):** M6's dispatch now has two tiers (`watchlist/monitor.py`) — adding a Greenhouse/Lever/Workday company is just a new Watchlist row, no code change. Adding a custom-scrape company is one new file at `job_sources/custom/<careers_identifier>.py` implementing `fetch_jobs(identifier, company_name=None, target_roles=None, existing_job_ids=None)`, dynamically loaded by `job_sources/custom/registry.py` — `watchlist/monitor.py` never needs to change. The 5 inactive custom-scrape rows' `careers_identifier` was migrated from a raw URL to the slug this registry expects; their real careers URLs (for whoever builds each scraper) are:
| Company | `careers_identifier` slug | Careers URL |
|---|---|---|
| Oracle | `oracle` | https://eeho.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/jobsearch/jobs |
| Qualcomm | `qualcomm` | https://careers.qualcomm.com/careers |
| FM Global | `fm_global` | https://jobs-fmglobal.icims.com/jobs/intro |
| Microsoft | `microsoft` | https://careers.microsoft.com/v2/global/en/home.html |
| Google | `google` | https://www.google.com/about/careers/applications/jobs/results/ |

---

## Strategic pivot (Aug 12, post-Phase-1)

**Original Phase 1 (M1 broad job aggregation) turned out to be lower value than expected** — Naukri/LinkedIn already cover broad discovery well. The real gap this system should fill is different: **actively monitoring specific target companies and turning a match into a filled, ready-to-submit application with minimal manual effort.**

This does not throw away Phase 1 — M6 (Watchlist), the Sheets backbone, resume_profile.json, and M4 scoring are all direct dependencies of the new priority. M1 keeps running (it's free, already live) but is deprioritized as a source of value.

**New centerpiece: M15 — Auto-Apply Engine.**

---

## M15 — Auto-Apply Engine (new module, full spec)

**Goal**: for watchlisted companies, when a posting matches, fill out that company's actual application form automatically — using a separate, purpose-built script per company (not one generic solution; portal login flows and forms differ too much company to company).

**Design decision — fill-and-confirm, NOT full auto-submit:**
The script does everything up to the final submit button — logs in, navigates to the job, fills every field, attaches the tailored resume — then **stops and shows the user a review/confirm screen** before the actual submit click.

Reasons this is the default, not just a suggestion:
- Company portals (especially Workday-based ones) often have CAPTCHA/bot-detection specifically targeting automated submission — a human present at the final step handles this naturally
- Most portal ToS prohibit automated submission; a detected pattern risks the account being flagged at exactly the companies being targeted
- Mistakes here are irreversible in a way draft emails aren't — a wrong resume attached or a bad field fill can't be unsent once submitted
- M4's scoring can false-positive (confirmed during Phase 1 testing) — auto-submitting on a scoring engine still being tuned is too much trust, too early

Full auto-submit can be reconsidered later, per-company, once a script has proven reliable over many manual-confirm runs — not the v1 default.

**Architecture**
```
applicators/
  base.py              # shared interface: login(), navigate_to_job(),
                        # fill_application(), review_and_confirm()
  <company>/
    apply.py           # that company's specific login + form flow
    selectors.py       # CSS/XPath selectors isolated here, so a portal
                        # redesign only breaks this one file
```
- **Tooling: Playwright**, not Selenium — better handling of dynamic/JS-heavy SPAs (Workday and similar modern portals)
- **Orchestrator** (`run_applications.py`): reads `Applications` rows marked `Interested` for companies with a script available, dispatches to the right `applicators/<company>/apply.py`, logs result back to the Sheet
- **Credentials**: stored via Python `keyring` (OS-level encryption — macOS Keychain), never in `.env`, never in the Sheet, never in any file. This module is **strictly local-only** — never runs in GitHub Actions, same reasoning as why outreach-sending stays manual: irreversible actions + credentials belong where a human is present.
- **Trigger**: a "Fill Application" button in the M7 dashboard, not automatic/scheduled

**Build order for M15 itself**: pick one company, build its script fully end-to-end (login → fill → confirm-screen) and prove the pattern works before replicating to others. Don't parallelize across companies until the first one is solid.

---

## Phase 2 — reprioritized (Aug 12–18)

Order changed from the original plan — M15's dependencies now come first.

1. **Expand/curate the Watchlist** — this is now the primary discovery lever, worth real time deciding which companies actually go on it (verify each one's ATS platform before adding — Greenhouse/Lever token vs. custom-scrape path, per DESIGN.md §M6)
2. **M9 — Resume Tailoring Engine** (Opus) — moved up; M15 needs a tailored resume to attach before it can fill anything, so this is now a hard dependency, not a nice-to-have
3. **M7 — Local Dashboard (Streamlit)**, specifically the review/confirm screen first — this is where M15's fill-and-confirm step lives, and where "Interested" gets marked
4. **M15 — Auto-Apply Engine** — start with one company end-to-end per the spec above
5. **M3 — Profile Updater** — folds into M7 once it exists, keeps resume_profile.json (and thus M9's output) accurate over time
6. **M8 — Contact Finder** (Hunter.io/Apollo.io) — still valuable for companies without an M15 script yet, or as a parallel outreach track
7. **M10 — Outreach Generator** (Opus) — drafts only, never auto-sent, per the no-LinkedIn-automation rule
8. **M11 — Analytics, M12 — Staleness Detector, M13 — Follow-up Reminder** — lower-risk, mechanical; good candidates for Gemini/cheaper models
9. **M14 — AI Provider Config abstraction** — already partially proven (M4 runs fully AI-free; Phase 1 modules confirmed this works). Extend cleanly to M3/M9/M10 as they're built.
10. **Testing + README polish** — last

## Sequencing rules (unchanged)

- Don't start a module until its dependencies are working and tested
- Model selection: Claude (Opus for design/quality-sensitive work like M9/M10 scoring-adjacent logic, Sonnet for standard implementation) for anything where output quality matters (goes to a real recruiter, or is genuinely hard reasoning); Gemini for mechanical/routine work (boilerplate, CRUD, simple bug fixes) to conserve Claude credit balance
- No more artificial time pressure — Aug 18 is the real deadline, review outputs properly rather than batching blind
