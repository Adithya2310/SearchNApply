# SearchNApply

SearchNApply is a personal job-search automation suite. A scheduled cloud
side continuously scans job boards and a hand-picked list of target
companies, scores every posting against your resume, and emails you a
digest — with zero attention required. A local dashboard, which only runs
when you open it, is where you actually work a lead: review matches, get
copy-paste-ready application form values, generate a tailored resume, draft
outreach, and keep every application's status in one place.

Everything — whether the system found it or you logged it by hand — lives
in a single Google Sheet. There is no separate database, no second
tracking spreadsheet, and nothing is ever sent, submitted, or saved
anywhere without you explicitly clicking a button to approve it.

## Contents

- [How it's organized](#how-its-organized)
- [Setup](#setup)
- [Job Scanner](#job-scanner)
- [Match Scorer](#match-scorer)
- [Company Watchlist](#company-watchlist)
- [Digest & Alerts](#digest--alerts)
- [Dashboard](#dashboard)
  - [Review](#review)
  - [Tracker](#tracker)
  - [Apply Kit](#apply-kit)
  - [Update Profile](#update-profile)
  - [Log Manual Application](#log-manual-application-not-yet-built)
- [Resume Tailor](#resume-tailor)
- [AI Engine](#ai-engine)
- [Future Scope](#future-scope)

## How it's organized

One Google Sheet, five tabs, acting as the entire database:

| Tab | What lives here |
|---|---|
| `Jobs` | Every posting the system has ever found, auto-discovered, with its match score and status |
| `Applications` | Every job you're pursuing — whether the system found it or you logged it manually — through to outcome |
| `Contacts` | Recruiter/hiring-contact info, reusable across postings |
| `Config` | Every tunable setting (target roles, salary floor, AI provider, etc.) — no code edits needed to change how the system behaves |
| `Watchlist` | The specific companies you want monitored closely |

Two independent halves run on two independent schedules:

- **The cloud side** (GitHub Actions) — Job Scanner, Match Scorer, Company
  Watchlist, Digest & Alerts. Runs unattended, all day, whether or not your
  laptop is open.
- **The local side** (the Dashboard) — everything you actually *do* with a
  match: review it, generate application content, tailor a resume, draft
  outreach. Only runs when you type `streamlit run dashboard.py`.

## Setup

1. Copy `.env.example` to `.env` and fill in the real values — see
   `API_KEYS_NEEDED.md` for exactly which accounts/keys you need and where
   to get each one.
2. Put your Google service-account JSON key at the path named in
   `GOOGLE_APPLICATION_CREDENTIALS` (default `credentials/service_account.json`).
   Never commit this file — it's already gitignored.
3. Run `python scripts/seed_config.py` once to populate starter `Config`
   rows, then open the `Config` tab in your Sheet and edit the values to
   match you (target roles, locations, salary floor, etc.).
4. Parse your resume into `resume_profile.json` (M2 — this is the one
   step that's a one-time manual run per resume change; see DESIGN.md).
5. For the cloud side: push to GitHub and add the repo Secrets listed in
   `API_KEYS_NEEDED.md`'s "GitHub Actions repo Secrets" section — the
   workflows in `.github/workflows/` won't run without them.
6. For the local side: `pip install -r requirements.txt`, then
   `streamlit run dashboard.py`.

---

## Job Scanner

**What it does:** Continuously searches Greenhouse, Lever, Adzuna, and
JSearch for postings matching your target roles and locations, and adds
every new one to the `Jobs` tab.

**How it runs:** Automatically, via GitHub Actions, roughly every 30
minutes (`.github/workflows/scan.yml`). You never need to touch it. To run
it yourself for testing:

```bash
python scripts/run_job_scan.py
```

**Configuring what it searches for** — all from the `Config` tab, no code
changes:

| Config key | Example value | Meaning |
|---|---|---|
| `target_roles` | `software engineer,backend developer` | Comma-separated role keywords searched on Adzuna/JSearch |
| `target_locations` | `Bangalore,Pune,Remote` | Comma-separated locations; blank = no location filter |
| `adzuna_country` | `in` | Adzuna's country code (`us`, `gb`, `in`, ...) |
| `greenhouse_boards` | `stripe,figma` | Comma-separated Greenhouse board tokens to scan directly |
| `lever_companies` | `netflix` | Comma-separated Lever company slugs to scan directly |

Every new posting lands in `Jobs` with `status = New` — the [Match
Scorer](#match-scorer) picks it up from there automatically, so you never
see an unscored row.

> **Note:** Adzuna/JSearch cover *broad* discovery well, but so do
> Naukri/LinkedIn — the [Company Watchlist](#company-watchlist) below is
> the higher-value lever if you already know which companies you want.

---

## Match Scorer

**What it does:** Scores every new `Jobs` row from 0–100 against your
`resume_profile.json`, combining three signals — skill overlap, salary fit,
and location fit — and auto-marks anything below your threshold as
`Ignored` so your inbox only ever shows real candidates.

**How it runs:** Automatically, right after the [Job Scanner](#job-scanner)
and the [Company Watchlist](#company-watchlist). To run it yourself:

```bash
python scripts/run_matching.py
```

**Configuring how it scores:**

| Config key | Example value | Meaning |
|---|---|---|
| `match_threshold` | `40` | Scores below this get auto-marked `Ignored` (0–100 scale) |
| `weight_skill` / `weight_salary` / `weight_location` | `0.60` / `0.15` / `0.25` | How much each dimension counts toward the final score |
| `salary_floor` / `salary_target` / `salary_currency` | `1200000` / `2000000` / `INR` | Below the floor, score decays; at/above the target, full marks |
| `remote_ok` | `Y` | Whether remote postings should be considered at all |
| `user_country` | `India` | Used to catch "remote (within US only)" postings that would otherwise wrongly get full remote credit |
| `core_skills` | `Python,React,SQL` | Optional override for which skills count double — defaults to your most recent job's tech stack |

**Example:** with `salary_floor = 1200000`, `weight_salary = 0.15`, a
posting listing ₹1,500,000 scores higher on the salary dimension than one
listing ₹900,000 — but a strong skill match can still outweigh a merely
adequate salary, since skill overlap carries the largest default weight
(0.60).

No AI is involved anywhere in this scoring — it's entirely rule-based, so
it costs nothing to run and never depends on an API key being valid.

---

## Company Watchlist

**What it does:** Checks a short, specific list of companies you actually
care about — much more frequently than the broad Job Scanner — and fires
an **immediate** email the moment a new matching posting appears, instead
of waiting for the next digest.

**How it runs:** Automatically, roughly every 10 minutes
(`.github/workflows/watchlist.yml`). To run it yourself:

```bash
python scripts/run_watchlist.py
```

**Adding a company** is a row in the `Watchlist` tab — no code required
for the common case:

| `company_name` | `careers_source` | `careers_identifier` | `active` |
|---|---|---|---|
| Stripe | `greenhouse` | `stripe` | `Y` |
| Netflix | `lever` | `netflix` | `Y` |
| Acme Corp | `workday` | `acme/wd5/AcmeExternalCareers` | `Y` |

`careers_source` can be `greenhouse`, `lever`, or `workday` — all three are
"just add a row," since one shared integration per platform is reused
across every company on it. Figuring out which platform a company uses is
usually a quick check: does their careers page redirect to
`boards.greenhouse.io`, `jobs.lever.co`, or `*.myworkdayjobs.com`?

**If a company uses none of those** (`careers_source = custom-scrape`),
someone has to write a small scraper once — but even then, no other code
changes: drop a file at `job_sources/custom/<careers_identifier>.py`
implementing

```python
def fetch_jobs(identifier, company_name=None, target_roles=None, existing_job_ids=None):
    ...  # return a list of job dicts: title, url, location, description_raw, ...
```

and the Watchlist picks it up automatically the next time it runs — nothing
in `watchlist/monitor.py` needs to change.

Non-matching postings from watchlisted companies are still logged
(silently, no email) so you can find them later if your criteria change.

---

## Digest & Alerts

**What it does:** Two kinds of email, so you never have to check the Sheet
to know something happened.

- **Daily/rolling digest** — every [Job Scanner](#job-scanner) run,
  bundles every `Jobs` row with `status = New` and a score above your
  threshold into one email, then marks those rows `Reviewed`.
- **Watchlist alerts** — a standalone email the moment a
  [Company Watchlist](#company-watchlist) run finds a real match at one of
  your target companies — not bundled into the digest, since the whole
  point of watchlisting a company is speed.

**How it runs:** Automatically, as the last step of each scheduled run. To
send a digest yourself right now:

```bash
python scripts/run_digest.py
```

Uses a Gmail address + App Password (`GMAIL_ADDRESS`/`GMAIL_APP_PASSWORD`
in `.env`) — not OAuth, kept deliberately simple.

---

## Dashboard

**What it is:** A local Streamlit app — the only part of the system you
actually interact with day to day. It never runs on a schedule; it only
runs while you have it open.

```bash
streamlit run dashboard.py
```

It opens in your browser at `http://localhost:8501` with five tabs:

### Review

Browse every `Jobs` row (filterable by status), sorted by match score, with
the full description one click away. Two actions per posting:

- **Interested** — creates the linked row in `Applications`
  (`status = Interested`) and marks the `Jobs` row `Moved to Applications`.
  This is the one moment a job and an application get linked automatically.
- **Ignore** — marks the `Jobs` row `Ignored`. No `Applications` row is
  created.

### Tracker

A spreadsheet-style, inline-editable view of every `Applications` row —
auto-discovered and manually logged, side by side, since they're the same
schema (see [How it's organized](#how-its-organized)). Change a status,
add a note, set a follow-up date, click **Save changes**, and it writes
straight back to the Sheet.

### Apply Kit

Pick one application from a dropdown and get everything you need to
actually fill out that company's real application form — without any
automation ever touching the real site. You still log in and paste these
in yourself; nothing here submits anything anywhere.

**Application Fields** — generated straight from `resume_profile.json` and
`Config`, each shown as a copy-button-ready block:

```
Full Name                       Adithya NG
Email                           you@example.com
Phone                           +91 90000 00000
LinkedIn                        linkedin.com/in/you
GitHub                          github.com/you
Current/Most Recent Employer    Acme Corp
Current/Most Recent Title       Software Engineer
Years of Experience             2.5
Highest Education               B.E. in Computer Science, XYZ College
Desired Salary                  INR 1200000
Resume File to Attach           tailored_resumes/acme_backend_engineer_20260813.txt
Company Applying To             Acme Corp
Role Applying For               Backend Engineer
Job Posting URL                 https://acme.example/careers/123
```

**Interest Pitch** — click **Generate pitch** for a short, AI-written
"why I'm interested in this role" blurb, grounded strictly in your real
experience (it will never claim a skill or project that isn't actually in
your profile):

> *"My interest in the Backend Engineer role is driven by my hands-on
> experience architecting real-time data pipelines and automating CI/CD
> workflows at my current job — directly relevant to the scalability
> challenges this posting describes. I'm also proficient in the exact
> stack listed (Python, PostgreSQL), and I'd welcome the chance to bring
> that experience to Acme's platform team."*

**Outreach Drafts** — click **Generate email draft** and/or **Generate
LinkedIn note** for two independent, editable drafts:

- An email (subject + body) you can paste straight into your mail client.
- A LinkedIn connection note — capped at LinkedIn's real 300-character
  limit (enforced in code, not just asked for, since AI models don't
  count characters reliably).

Both work fine even with no known recruiter contact (falls back to a
generic-but-warm greeting). Once you've actually sent one, click **Mark
... sent → save to Applications** — it appends to that application's
`outreach_message` (so sending both an email *and* a LinkedIn note keeps
both records) and sets `outreach_sent = Y`.

### Update Profile

A chat box for keeping `resume_profile.json` accurate as you do new things
— you don't need to hand-edit JSON. Type something like:

> *"I built a small internal CLI tool at work using Python and Click to
> automate our deployment checklist, cutting manual release prep from 45
> minutes to 5."*

Click **Analyze**, and it proposes:

- **Skills to add** (e.g. `Click`) — shown as checkboxes, only genuinely
  new skills (already-known ones, even under a different name like
  "ReactJS" vs "React", are correctly excluded).
- **A bullet**, written in the same voice as your existing resume bullets,
  quantified if you gave it a number.
- **Where it belongs** — an existing job, an existing project, or a brand
  new project, defaulted to its best guess (e.g. "at work" → your current
  job) but always changeable via a dropdown.

**Nothing is written until you click Approve and save** — you can edit the
wording first, uncheck skills you don't want, or just click **Reject** to
discard the whole thing. Every decision (approved, edited, or rejected) is
appended to `profile_updates_log.jsonl` with the original text you typed —
a full audit trail if you ever want to see how (or why) something changed.

### Log Manual Application (not yet built)

For jobs you find and apply to entirely outside this system (a company's
own careers page you happened to click into) — a simple form: company,
role, URL, date, notes, straight into `Applications` with
`source_type = manual`. Once logged, it ages through the exact same
Tracker/Apply Kit/Outreach flow as anything the system found itself. See
[Future Scope](#future-scope).

---

## Resume Tailor

**What it does:** Given a specific job, rewrites and reorders your resume
to fit it — in three steps, not one blind generate:

1. **Finds the gaps.** One AI call extracts the skills the job actually
   asks for; a plain, rule-based comparison against your existing profile
   (the same alias-aware matching the Match Scorer uses, so "React" and
   "ReactJS" are recognized as the same thing) finds what's genuinely
   missing.
2. **Asks you about each gap**, one at a time:

   ```
   This job asks for 'Terraform', which isn't in your profile.
     [1] I know this already  [2] I'll learn it (project planned)  [3] skip >
   ```

   Answering "I know this already" adds it to your real profile on the
   spot — this *is* the approval step, the same principle as
   [Update Profile](#update-profile).
3. **Generates the tailored resume** — plain text, ATS-friendly (standard
   section headers, no tables/graphics/Markdown), with the resolved skills
   woven in naturally and every date/employer taken verbatim from your
   profile (dates are computed in code, never left for the AI to infer —
   it will not, for instance, invent "Present" for a job that's already
   ended).

You review the full draft before anything is saved.

**How to run it:**

```bash
# Against a real Jobs row:
python scripts/tailor_resume.py --job-id <job_id>

# Against a job description you have as a local file:
python scripts/tailor_resume.py --jd-file path/to/description.txt
```

Output is saved to `tailored_resumes/<company>_<role>_<date>.txt`. If the
job is already linked to an `Applications` row, that row's
`resume_version_used` is filled in automatically.

> Not yet wired into the Dashboard — for now it's a command-line step. See
> [Future Scope](#future-scope).

---

## AI Engine

Every AI-calling feature above (Resume Tailor, Update Profile, Apply Kit's
pitch/outreach) routes through one place: `ai_provider/`. It reads which
model to use from the `Config` tab, not from an environment variable or
hardcoded model name — so switching providers is a spreadsheet edit, not a
code change.

| Config key | Example | Meaning |
|---|---|---|
| `ai_provider` | `gemini` | `gemini`, `claude`, or `none` |
| `ai_model` | *(blank)* | Optional override, e.g. `gemini-2.5-pro` — blank uses that provider's default |

Currently running on **Gemini** (free tier). **Claude support is fully
written but not yet live-tested** — it just needs a real `ANTHROPIC_API_KEY`
in `.env` to switch on.

> **Gemini's free tier caps out at 20 requests/day per model.** Each real
> use of Resume Tailor/Update Profile/Apply Kit's AI features is 1–2
> requests, so this is generous for normal day-to-day use, but heavy
> back-to-back testing can exhaust it — it resets daily.

---

## Future Scope

Everything below is designed for (the data model and Config already
support it) but not yet built:

- **Log Manual Application tab** — the last stub in the Dashboard; logging
  a job you applied to entirely outside the system.
- **Contact Finder** — deliberately **not built**: Hunter.io/Apollo.io are
  both paid, and a company-domain search is unlikely to surface the
  specific recruiter for a specific opening at large enterprises (which is
  most of this system's actual target list) — low expected value for the
  cost. A cheaper alternative worth revisiting: pre-built LinkedIn/Google
  search links per application (no API, no cost) to speed up the manual
  lookup you'd otherwise be doing anyway.
- **Analytics** — response rate by source (auto-discovered vs. manual), by
  resume version, by outreach style — to see what's actually working once
  enough `Applications` history exists.
- **Staleness/Duplicate Detector** — flag postings open 60+ days or
  reposted listings as lower priority, folded into the Job Scanner's run.
- **Follow-up Reminder** — surface "N applications need a follow-up today"
  in the digest, based on `Applications.next_followup_date` — the actual
  payoff of logging manual applications, once that tab exists.
- **Claude as a live AI provider** — the code path exists (`ai_provider/claude.py`)
  and mirrors Gemini's interface exactly; it just hasn't been exercised
  against a real `ANTHROPIC_API_KEY` yet.
- **Resume Tailor inside the Dashboard** — currently a command-line step;
  folding it into the Apply Kit tab would mean one place for every
  per-application action instead of two.
- **Expanding the Watchlist** — the dispatch architecture already supports
  adding companies with zero code changes (Greenhouse/Lever/Workday) or
  one new file (custom-scrape); five companies (Oracle, Qualcomm, FM
  Global, Microsoft, Google) are already in the `Watchlist` tab as
  `inactive` placeholders with their real careers URLs recorded in
  `BUILD_PLAN.md`, waiting on their custom scrapers to be written.
- **Automated tests as living documentation** — 132 tests currently cover
  every feature above; this number will keep growing alongside new work,
  and is the fastest way to confirm nothing regressed after a change.
