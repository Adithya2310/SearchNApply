# External Accounts & API Keys Needed

The user needs to create these accounts and provide the resulting keys/credentials. Claude Code should NOT attempt to sign up for these on the user's behalf — surface exactly what's needed and let the user provide it via `.env`.

## Required for Phase 1

| Service | Used by | Free tier? | Notes |
|---|---|---|---|
| Google Cloud project + Sheets API | Everything (the Sheet is the DB) | Yes | Needs a service account JSON key with edit access to the target Sheet |
| Gmail account + App Password | M5 Digest, M6 Watchlist alerts | Yes | Requires 2FA enabled on the Google account first, then generate an App Password under Security settings |
| Adzuna API | M1 Aggregator | Yes, free tier | Sign up at developer.adzuna.com |
| JSearch (via RapidAPI) | M1 Aggregator | Yes, free tier with limits | Sign up at rapidapi.com, subscribe to JSearch |
| GitHub repo + Actions | Orchestration | Yes | Store all keys below as repo Secrets, never commit them |

## Required for Phase 2

| Service | Used by | Free tier? | Notes |
|---|---|---|---|
| Hunter.io or Apollo.io | M8 Contact Finder | Yes, limited (~25-50 lookups/month free) | Pick one to start; both have similar free tiers |
| Anthropic API key | M3, M4, M9, M10 (when AI_PROVIDER=claude) | No — paid, this is separate from Claude Code credits | Only needed if AI_PROVIDER is set to claude for the *running* system, not the building |
| Gemini API key | M3, M4, M9, M10 (when AI_PROVIDER=gemini) | Yes, generous free tier | The intended low-cost default per the user's plan |

## Not needed / deliberately excluded

- **No LinkedIn API or scraping credentials** — the system does not automate LinkedIn in any way.
- **No phone number lookup service** — out of scope by design.

## Where these go

All keys are read from environment variables — see `.env.example` for exact names. Locally, copy `.env.example` to `.env`. For GitHub Actions, add the same values as repo Secrets (Settings → Secrets and variables → Actions).

## GitHub Actions repo Secrets (Phase 1 orchestration)

`.github/workflows/scan.yml` (M1+M4+M5) and `.github/workflows/watchlist.yml` (M6) read these repo Secrets — set them all under Settings → Secrets and variables → Actions → New repository secret:

| Secret name | Value |
|---|---|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | The **full contents** of the service account JSON key file (not a path — paste the whole JSON as the secret value). The workflow writes it to `credentials/service_account.json` at runtime. |
| `GOOGLE_SHEETS_SPREADSHEET_ID` | Same value as the local `.env` |
| `GMAIL_ADDRESS` | Same value as the local `.env` |
| `GMAIL_APP_PASSWORD` | Same value as the local `.env` |
| `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` | scan.yml only (M1's Adzuna integration) |
| `RAPIDAPI_JSEARCH_KEY` | scan.yml only (M1's JSearch integration) |

Both workflows also need to actually exist on GitHub before their `schedule:` cron triggers will fire — commit + push `.github/workflows/*.yml` to the default branch. Note: GitHub disables scheduled workflows automatically after 60 days with no commits to the repo — if the repo goes quiet, a scheduled run may silently stop firing until a new commit re-enables it.
