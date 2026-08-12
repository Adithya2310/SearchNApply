# Job Search Suite — Start Here

This folder contains the full spec for a job search automation system. Read the docs below **in this order** before writing any code.

## Read order

1. **DESIGN.md** — the complete system design: data schema, every module's trigger/input/process/output. This is the source of truth for what to build.
2. **BUILD_PLAN.md** — the phased build order and today's exact priority list.
3. **API_KEYS_NEEDED.md** — every external account/API key this system depends on, and what each is used for.
4. **.env.example** — the exact environment variable names the code should expect (copy to `.env` and fill in real values — never commit `.env`).

## What this system is, in one paragraph

An automated job search pipeline: a scheduled job (GitHub Actions) scans multiple job sources plus a configurable company watchlist, scores matches against a resume profile, and emails a digest. A local dashboard (run on the user's laptop, not hosted) lets the user review matches, log manually-applied jobs, chat-update their resume profile, find recruiter contacts, generate a tailored resume + outreach drafts per job, and track everything through to outcome. Everything — auto-discovered or manually logged — lives in one Google Sheet acting as the database.

## Non-negotiable design principles

- **One data store, two entry points.** Auto-discovered jobs and manually-logged applications go into the same `Applications` sheet with the same schema. Nothing gets a separate tracking system.
- **AI calls are isolated behind a provider config**, not hardcoded to one model. Every module that calls an LLM (M3, M4, M9, M10) must read `AI_PROVIDER` from config and branch accordingly, so the system can run on Claude, Gemini, or a no-AI rule-based fallback later without a rewrite.
- **The scheduled/cloud side (GitHub Actions) and the manual/local side (dashboard) are separate deployables.** The cloud side must run unattended and never block on user input. The local side never runs on a schedule — only when the user opens it.
- **Nothing sends anything automatically without explicit user action.** Outreach emails and LinkedIn messages are drafted, never auto-sent. Resume profile updates are drafted, never auto-merged — always require approval (see M3 in DESIGN.md).
- **No LinkedIn automation/scraping of any kind.** No auto-connecting, no auto-messaging, no bot activity on LinkedIn. It will get accounts banned. Contact discovery uses Hunter.io/Apollo.io (built for exactly this) plus manual LinkedIn lookup by the user.
- **No attempts to find personal phone numbers.** Work email + LinkedIn is the ceiling for contact discovery. Do not scrape data-broker sites or similar.

## Current status

Check with the user which phase/module is currently in progress before assuming a clean start — this may be a continuation of earlier work, not a fresh build. If unsure, ask.
