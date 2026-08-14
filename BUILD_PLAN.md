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

This does not throw away Phase 1 — M6 (Watchlist), the Sheets backbone, resume_profile.json, and M4 scoring are all direct dependencies of the new priority.

**M1 fully paused (Aug 14, 2026):** after actually using the system, the broad scan's results were mostly low-value postings from small companies — not just lower-value than the Watchlist, but not useful enough to keep running. `scan.yml`'s schedule trigger was removed (`workflow_dispatch` still works for a manual run). **`watchlist.yml`/M6 is now the sole active discovery channel.** M1's code is untouched and easy to re-enable (re-add the `schedule:` block) if this changes.

**New centerpiece: M15 — Application Kit Generator** (redesigned Aug 13, 2026 — see below; the original login-automation spec was scrapped before any of it was built).

---

## M15 — Application Kit Generator (redesigned Aug 13, 2026)

**Original spec (never built) was login automation**: a Playwright script per company that logs into the real portal, fills the form, and stops for a manual confirm before submit. Scrapped in favor of something strictly safer, before writing any of it: even a fill-and-confirm design still means automated login traffic against a real account on a portal that may fingerprint/CAPTCHA/rate-limit automated sessions — the ban risk lives in the login step itself, not just the submit step, and there's no way to fully eliminate it while still automating login. Not worth the risk for what it saves.

**New goal**: for a job the user has marked `Interested`, generate every value a typical application form asks for from `resume_profile.json` + the job data, and display them in the M7 dashboard as copy-paste-ready fields. The user manually opens the real portal, logs in themselves, and pastes each value in. Zero automated interaction with any company's real site — no login, no form submission, no browser automation, no credential storage at all.

**Architecture**
```
application_kit/
  fields.py   # pure function: resume_profile + job/application row + Config
              # -> ordered {label: value} dict of standard form fields
              # (name, contact info, current employer/title, years of
              # experience, education, desired salary, resume filename).
              # No AI — deterministic, same profile data M4/M9 already use.
  pitch.py    # one AI call: short "why I'm interested in this role" blurb,
              # grounded only in real profile facts (same anti-fabrication
              # rule as M9) — the one field that's genuinely job-specific
              # and worth generating rather than reusing verbatim.
```
- **Trigger**: an "Apply Kit" tab in the M7 dashboard — pick an `Interested`/`Applied` Applications row, see every field as a copyable block
- **No new external dependencies**: no Playwright, no `keyring` — this is pure data generation + Streamlit display, reusing `ai_provider`/M14 for the one generated field
- **Still strictly manual for the actual submission** — same "nothing sends/submits itself" principle as everywhere else in this system, just applied one step earlier (no login either, not just no submit)

---

## Phase 2 — reprioritized (Aug 12–18)

Order changed from the original plan — M15's dependencies now come first.

1. **Expand/curate the Watchlist** — DEFERRED (Aug 13, explicit call): finish the other modules first, but keep the architecture scalable for it — done via the M6 dispatch refactor (see above); no new companies added yet.
2. **M9 — Resume Tailoring Engine** (Gemini) — DONE (Aug 13). Three-step: AI skill-gap extraction, interactive resolution, AI tailoring. Live-tested against real Sheet data.
3. **M7 — Local Dashboard (Streamlit)** — Review + Tracker + Apply Kit + Update Profile tabs DONE (Aug 13), live-tested via Streamlit's `AppTest` against the real Sheet. M9 (Resume Tailor) folded into Apply Kit on Aug 14, sharing its underlying functions with the standalone CLI (`resume_tailor/output.py` now shared by both). Only Log Manual Application is still a stub.
4. **M15 — Application Kit Generator** (redesigned from Auto-Apply, see above) — DONE (Aug 13). Apply Kit tab live-tested against real Sheet + real Gemini pitch generation.
5. **M3 — Profile Updater** — DONE (Aug 13). Chat-style free text → AI proposal → diff approval → `resume_profile.json` write + `profile_updates_log.jsonl` audit trail. Live-tested via `AppTest`.
6. **M8 — Contact Finder** (Hunter.io/Apollo.io) — DEPRIORITIZED (Aug 13, explicit call). Both are paid, and a company-domain search is unlikely to surface the specific recruiter for a specific req at the large enterprises on this user's target list — low expected ROI for the cost. Not built. A free alternative (pre-built LinkedIn/Google search links per application, no API) was proposed but not yet built either.
7. **M10 — Outreach Generator** — DONE (Aug 13). Email + LinkedIn connection note drafts (Gemini), wired into the Apply Kit tab; works without M8's contact info (falls back to a generic greeting). LinkedIn's 300-char cap enforced in code. Live-tested via `AppTest` against a temporary real Applications row (deleted after verifying), confirming outreach_message accumulates multiple sent drafts rather than overwriting.
8. **M11 — Analytics, M12 — Staleness Detector, M13 — Follow-up Reminder** — NOT STARTED; lower-risk, mechanical, good candidates for Gemini.
9. **M14 — AI Provider Config abstraction** — DONE for Gemini (live, used by M3/M9/M10/M15). Claude path is code-complete but not live-tested (no `ANTHROPIC_API_KEY` provisioned). Note: Gemini's free tier is capped at 20 requests/day per model — hit this cap during Aug 13's testing.
10. **Testing + README polish** — ONGOING, not finalized (132 tests passing; README.md itself hasn't been updated since Phase 1 to reflect any of Phase 2's actual modules).

## Sequencing rules (unchanged)

- Don't start a module until its dependencies are working and tested
- Model selection: Claude (Opus for design/quality-sensitive work like M9/M10 scoring-adjacent logic, Sonnet for standard implementation) for anything where output quality matters (goes to a real recruiter, or is genuinely hard reasoning); Gemini for mechanical/routine work (boilerplate, CRUD, simple bug fixes) to conserve Claude credit balance
- No more artificial time pressure — Aug 18 is the real deadline, review outputs properly rather than batching blind
