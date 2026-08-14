# TASK — Watchlist custom-scrape integrations

Six independent tasks, one per company, each building that company's
`job_sources/custom/<slug>.py` job-listing integration for the Watchlist
system. Each section below is fully self-contained — copy one section's
prompt into an agent to run it standalone. All six are independent of each
other (different files, no shared state) and can run in parallel.

---

## Oracle

Build the custom-scrape job-listing integration for Oracle in the Watchlist system (searchnapply repo).

Company: Oracle | Watchlist slug: oracle | Careers URL: https://eeho.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/jobsearch/jobs
ATS: Oracle Fusion Cloud Recruiting (Oracle's own product, not a third-party ATS).

Step 1 — Investigate: Determine whether this careers page's own frontend calls a public JSON API to load job listings. This is the same technique that found job_sources/workday.py's /wday/cxs/<tenant>/<site>/jobs endpoint — inspect what the page's JS fetches (network requests), not just the rendered HTML. Oracle Fusion Recruiting sites often expose a REST endpoint under a path like /hcmRestApi/resources/.../recruitingCEJobRequisitions or similar — verify the actual path for this tenant rather than assuming.

Step 2 — Implement (only if a usable API exists): Create job_sources/custom/oracle.py implementing:
    fetch_jobs(identifier, company_name=None, target_roles=None, existing_job_ids=None)
returning a list of dicts with keys: source, company, title, url, location, salary_range, description_raw. Study job_sources/workday.py for the established pattern and job_sources/custom/registry.py for the dispatch contract. Oracle is a large employer — if the listing API doesn't return full descriptions, follow Workday's two-stage pattern: compute job_id from lightweight listing data via job_sources/dedup.py's compute_job_id, and only pay for a per-job detail fetch on genuinely new postings (skip anything in existing_job_ids).

Step 3 — Test: Write tests/test_oracle.py mocking HTTP calls, matching tests/test_workday.py's rigor (payload shape, dedup-skips-detail-fetch-for-known-jobs, dedup-across-queries).

Step 4 — Live-verify: Make one real call against the real Oracle careers site and confirm it returns real postings — report 2-3 real title/url samples, or the real failure if it doesn't work.

Step 5 — If no usable API exists and this would require full HTML scraping or JS-rendered browser automation to work reliably, say so plainly instead of writing something fragile — report that Oracle isn't a good custom-scrape candidate right now and why.

Constraints: don't touch the Watchlist Google Sheet, don't commit anything.

Report back: what you found (API or not), the real sample output if it works, and the test pass/fail count for your new test file.

---

## FM Global

Build the custom-scrape job-listing integration for FM Global in the Watchlist system (searchnapply repo).

Company: FM Global | Watchlist slug: fm_global | Careers URL: https://jobs-fmglobal.icims.com/jobs/intro
ATS: iCIMS (TalentBrew-branded front end). Note: AMD also runs on iCIMS (careers-amd.icims.com) — if you find a generically-reusable iCIMS API pattern, mention it, since it may also apply there, but your deliverable is scoped to FM Global only.

Step 1 — Investigate: Determine whether this careers page's frontend calls a public JSON API to load job listings (same technique that found job_sources/workday.py's endpoint — inspect what the page's own JS fetches, not just rendered HTML). iCIMS sites commonly expose a search/results endpoint (often under a path involving /jobs/search or a JSON search-results call) that populates listings client-side — verify the actual path for this tenant.

Step 2 — Implement (only if a usable API exists): Create job_sources/custom/fm_global.py implementing:
    fetch_jobs(identifier, company_name=None, target_roles=None, existing_job_ids=None)
returning a list of dicts with keys: source, company, title, url, location, salary_range, description_raw. Study job_sources/workday.py for the established pattern and job_sources/custom/registry.py for the dispatch contract. If the listing API lacks full descriptions, follow Workday's two-stage pattern (compute_job_id from listing data via job_sources/dedup.py, detail-fetch only new postings not in existing_job_ids).

Step 3 — Test: Write tests/test_fm_global.py mocking HTTP calls, matching tests/test_workday.py's rigor.

Step 4 — Live-verify: Make one real call against the real FM Global careers site and confirm it returns real postings — report 2-3 real title/url samples, or the real failure if it doesn't work.

Step 5 — If no usable API exists and this would require full HTML scraping or JS-rendered browser automation, say so plainly instead of writing something fragile — report that FM Global isn't a good custom-scrape candidate right now and why.

Constraints: don't touch the Watchlist Google Sheet, don't commit anything.

Report back: what you found (API or not), the real sample output if it works, and the test pass/fail count for your new test file.

---

## Qualcomm

Build the custom-scrape job-listing integration for Qualcomm in the Watchlist system (searchnapply repo).

Company: Qualcomm | Watchlist slug: qualcomm | Careers URL: https://careers.qualcomm.com/careers
ATS: Eightfold AI.

Step 1 — Investigate: Determine whether this careers page's frontend calls a public JSON API to load job listings (same technique that found job_sources/workday.py's endpoint — inspect what the page's own JS fetches, not just rendered HTML). Eightfold-based career sites often expose a search API (frequently under a path involving /api/apply/v2/jobs or similar, varies by tenant) that populates listings client-side — verify the actual path for this tenant.

Step 2 — Implement (only if a usable API exists): Create job_sources/custom/qualcomm.py implementing:
    fetch_jobs(identifier, company_name=None, target_roles=None, existing_job_ids=None)
returning a list of dicts with keys: source, company, title, url, location, salary_range, description_raw. Study job_sources/workday.py for the established pattern and job_sources/custom/registry.py for the dispatch contract. Qualcomm is a large employer — if the listing API doesn't return full descriptions, follow Workday's two-stage pattern (compute_job_id from listing data via job_sources/dedup.py, detail-fetch only new postings not in existing_job_ids).

Step 3 — Test: Write tests/test_qualcomm.py mocking HTTP calls, matching tests/test_workday.py's rigor.

Step 4 — Live-verify: Make one real call against the real Qualcomm careers site and confirm it returns real postings — report 2-3 real title/url samples, or the real failure if it doesn't work.

Step 5 — If no usable API exists and this would require full HTML scraping or JS-rendered browser automation, say so plainly instead of writing something fragile — report that Qualcomm isn't a good custom-scrape candidate right now and why.

Constraints: don't touch the Watchlist Google Sheet, don't commit anything.

Report back: what you found (API or not), the real sample output if it works, and the test pass/fail count for your new test file.

---

## AMD

Build the custom-scrape job-listing integration for AMD in the Watchlist system (searchnapply repo).

Company: AMD | Watchlist slug: amd | Careers URL: https://careers.amd.com (a branded front end over ATS: iCIMS, backed by https://careers-amd.icims.com). Note: FM Global also runs on iCIMS — if you find a generically-reusable iCIMS API pattern, mention it, since it may also apply there, but your deliverable is scoped to AMD only.

Step 1 — Investigate: Determine whether careers.amd.com's frontend (or the underlying careers-amd.icims.com) calls a public JSON API to load job listings (same technique that found job_sources/workday.py's endpoint — inspect what the page's own JS fetches, not just rendered HTML). iCIMS sites commonly expose a search/results endpoint that populates listings client-side — verify the actual path for this tenant; it hasn't been confirmed yet for AMD specifically.

Step 2 — Implement (only if a usable API exists): Create job_sources/custom/amd.py implementing:
    fetch_jobs(identifier, company_name=None, target_roles=None, existing_job_ids=None)
returning a list of dicts with keys: source, company, title, url, location, salary_range, description_raw. Study job_sources/workday.py for the established pattern and job_sources/custom/registry.py for the dispatch contract. AMD is a large employer — if the listing API doesn't return full descriptions, follow Workday's two-stage pattern (compute_job_id from listing data via job_sources/dedup.py, detail-fetch only new postings not in existing_job_ids).

Step 3 — Test: Write tests/test_amd.py mocking HTTP calls, matching tests/test_workday.py's rigor.

Step 4 — Live-verify: Make one real call against the real AMD careers site and confirm it returns real postings — report 2-3 real title/url samples, or the real failure if it doesn't work.

Step 5 — If no usable API exists and this would require full HTML scraping or JS-rendered browser automation, say so plainly instead of writing something fragile — report that AMD isn't a good custom-scrape candidate right now and why.

Constraints: don't touch the Watchlist Google Sheet, don't commit anything.

Report back: what you found (API or not), the real sample output if it works, and the test pass/fail count for your new test file.

---

## Microsoft

Build the custom-scrape job-listing integration for Microsoft in the Watchlist system (searchnapply repo).

Company: Microsoft | Watchlist slug: microsoft | Careers URL: https://careers.microsoft.com/v2/global/en/home.html
ATS: in-house/custom, Adobe AEM-based front end — no third-party ATS fingerprint found in earlier research.

Step 1 — Investigate: Determine whether this careers page's frontend calls a public JSON API to load job listings (same technique that found job_sources/workday.py's endpoint — inspect what the page's own JS fetches, not just rendered HTML). Microsoft's careers site has historically exposed a search API under paths involving /v2/global/en/search-results or similar for its "external" candidate site — verify the actual current path and response shape, since this may have changed.

Step 2 — Implement (only if a usable API exists): Create job_sources/custom/microsoft.py implementing:
    fetch_jobs(identifier, company_name=None, target_roles=None, existing_job_ids=None)
returning a list of dicts with keys: source, company, title, url, location, salary_range, description_raw. Study job_sources/workday.py for the established pattern and job_sources/custom/registry.py for the dispatch contract. Microsoft has an enormous number of open postings — you must follow Workday's two-stage pattern: compute job_id from lightweight listing data via job_sources/dedup.py's compute_job_id, and only pay for a per-job detail fetch on genuinely new postings not already in existing_job_ids. Also support filtering by target_roles in the search query itself if the API allows it, to avoid pulling the entire company's listings every run.

Step 3 — Test: Write tests/test_microsoft.py mocking HTTP calls, matching tests/test_workday.py's rigor (payload shape, dedup-skips-detail-fetch-for-known-jobs, dedup-across-queries).

Step 4 — Live-verify: Make one real call against the real Microsoft careers site and confirm it returns real postings — report 2-3 real title/url samples, or the real failure if it doesn't work.

Step 5 — If no usable API exists and this would require full HTML scraping or JS-rendered browser automation, say so plainly instead of writing something fragile — report that Microsoft isn't a good custom-scrape candidate right now and why.

Constraints: don't touch the Watchlist Google Sheet, don't commit anything.

Report back: what you found (API or not), the real sample output if it works, and the test pass/fail count for your new test file.

---

## Google

Build the custom-scrape job-listing integration for Google in the Watchlist system (searchnapply repo).

Company: Google | Watchlist slug: google | Careers URL: https://www.google.com/about/careers/applications/jobs/results/
ATS: proprietary, in-house — earlier research found no public API and confirmed reports that Google no longer offers an official jobs data API.

Step 1 — Investigate: Confirm (don't just assume from prior notes) whether this careers page's frontend calls any public JSON API to load job listings — inspect what the page's own JS fetches, not just rendered HTML, the same technique that found job_sources/workday.py's endpoint. Treat this as a genuine re-check, since ATS/API availability can change.

Step 2 — Implement (only if a usable API exists): Create job_sources/custom/google.py implementing:
    fetch_jobs(identifier, company_name=None, target_roles=None, existing_job_ids=None)
returning a list of dicts with keys: source, company, title, url, location, salary_range, description_raw. Study job_sources/workday.py for the established pattern and job_sources/custom/registry.py for the dispatch contract. If a listing API exists but lacks full descriptions, follow Workday's two-stage pattern (compute_job_id from listing data via job_sources/dedup.py, detail-fetch only new postings not in existing_job_ids).

Step 3 — Test (only if you build something): Write tests/test_google.py mocking HTTP calls, matching tests/test_workday.py's rigor.

Step 4 — Live-verify (only if you build something): Make one real call against the real Google careers site and confirm it returns real postings — report 2-3 real title/url samples, or the real failure if it doesn't work.

Step 5 — This one is the most likely of the six to have no usable API: if confirmed, say so plainly and do not attempt full HTML scraping or JS-rendered browser automation just to have something — report that Google isn't a good custom-scrape candidate right now and why, and recommend it stay inactive in the Watchlist.

Constraints: don't touch the Watchlist Google Sheet, don't commit anything.

Report back: what you found (API or not), the real sample output if it works, and the test pass/fail count for your new test file.
