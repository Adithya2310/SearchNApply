# M4 — Matching / Scoring Engine (design spec)

**Status:** design only. This doc is the handoff from the design pass (Opus) to
the implementation pass (Sonnet), per BUILD_PLAN.md. Do not implement from
memory — implement from this.

## 1. Purpose & where it sits

Runs right after M1 fills the `Jobs` sheet. Reads each unscored job, computes a
`match_score` in **0–100**, writes it back, and auto-demotes weak matches to
`status = Ignored`. M5 later emails the `New` rows whose score clears the
threshold. M4 is the gate that keeps the digest signal-dense.

**Inputs**
- New `Jobs` rows (title, description_raw, location, salary_range, source, status, match_score)
- `resume_profile.json` (skills, work_experience[].tech_stack, etc.)
- `Config` sheet criteria (see §7 for the keys M4 reads)

**Output**
- `Jobs.match_score` filled per row (integer 0–100)
- `Jobs.status`: rows below threshold → `Ignored`; rows at/above → left `New`

## 2. Non-negotiable constraint: the default path must be zero-AI

Phase 1 has to keep running unattended after AI credits expire (DESIGN.md §5).
So the **rule-based scorer is the primary, always-on implementation** and must be
fully functional with `ai_provider = none`. AI is an *optional enhancement layer*
on one dimension only (see §6). Never let scoring hard-depend on a paid API.

This also aligns with M14: M4 reads `ai_provider` from Config and branches, so
`none` / `claude` / `gemini` all work without a rewrite.

## 3. The three dimensions

Each dimension returns either a score in `[0.0, 1.0]` **or the sentinel
`UNKNOWN`**. Distinguishing "scored low" from "no information" is the single most
important idea in this design — see §5.

### 3a. Skill overlap (the dominant signal, ~always known)

Build a weighted candidate skill set from the resume + Config, then measure how
strongly a job's text hits it.

1. **Vocabulary.** Union of `resume_profile.skills.languages`,
   `.skills.technologies_tools`, and every `work_experience[].tech_stack`. Dedupe
   case-insensitively. Merge with an alias map so lexical variants collapse to one
   skill, e.g. `React`↔`ReactJS`↔`React.js`, `Postgres`↔`PostgreSQL`,
   `JS`↔`JavaScript`, `TS`↔`TypeScript`, `.NET`↔`dotnet`↔`ASP.NET`,
   `GH Actions`↔`GitHub Actions`. Ship a starter alias dict; make it extensible.

2. **Weights.** Each skill gets a weight. Default `1.0`; **core skills** get `2.0`.
   Core skills = `Config.core_skills` if set, else derived heuristically from the
   most-recent `work_experience` entry's `tech_stack` plus the first ~3 listed
   languages (resumes front-load their strongest). This makes "matched Python +
   C# + .NET" outrank "matched some tool I listed once."

3. **Matching.** Lowercase `title + " " + description_raw`. For each vocab skill,
   test presence with a **word-boundary-aware** match. Symbolic/short names need
   special care — `C`, `C++`, `C#`, `Go`, `R`, `.NET` must not match substrings of
   ordinary words. Use per-skill regexes (escape `+`/`#`/`.`, require boundaries);
   for the truly ambiguous single letters (`C`, `R`, `Go`) require a delimiter like
   `C/C++`, `(C)`, `, C,` rather than a bare letter. Track *where* each skill
   matched (title vs description).

4. **Score (saturation-normalized, NOT fraction-of-all).**
   ```
   contribution(s) = weight(s) * (TITLE_MULTIPLIER if matched in title else 1.0)
   raw             = sum(contribution(s) for s in matched)
   skill_score     = min(1.0, raw / SKILL_SATURATION)
   ```
   `TITLE_MULTIPLIER` default `1.5`, `SKILL_SATURATION` default `4.0` (≈ four
   weight-1 hits, or two core hits, saturates to a top score). **Do not** normalize
   by `len(vocabulary)` — a broad resume shouldn't dilute the score, and JDs only
   name a handful of skills. Saturation means "hit enough of the skills that
   matter," which is the correct target.

   `skill_score` is `UNKNOWN` only if there is no text at all (empty title AND
   empty description). In practice it is essentially always known.

### 3b. Salary fit (usually UNKNOWN — design around that)

Reality from the live M1 pull: **~84% of jobs had no salary** (all Lever +
Greenhouse blank; only Adzuna populated, and those are *predicted* point
estimates). So the common case is missing, and the parser must be defensive.

1. **Parse** `salary_range` best-effort into `(min, max, period, currency)`:
   - Adzuna style `"104099.3-104099.3"` → min/max floats (equal ⇒ point estimate).
   - JSearch may give a human string ("$120K–$150K a year") or nothing.
   - Normalize hourly→annual (`* ~2080`) when a period is detectable.
   - Currency: see §8 (open question). For now, if a currency symbol/code is
     present and differs from `Config.salary_currency`, either skip conversion
     (treat magnitude as-is, note the limitation) or apply an optional static
     rate map. **Do not** silently compare across currencies as if equal.
   - Unparseable or empty ⇒ salary dimension is `UNKNOWN`.

2. **Score** against `Config.salary_floor` (minimum acceptable) and optional
   `Config.salary_target` (ideal). Use the job's `max` (fall back to `min`):
   ```
   figure >= target                 -> 1.0
   floor <= figure < target         -> 0.5 + 0.5 * (figure - floor)/(target - floor)
   figure < floor                   -> max(0.0, 0.5 * figure/floor)   # below floor decays, not a cliff
   salary UNKNOWN                   -> UNKNOWN   (NOT 0, NOT 0.5 — see §5)
   Config.salary_floor not set      -> UNKNOWN   (user hasn't expressed a preference)
   ```
   Optionally pull *predicted* Adzuna salaries (min==max) partway toward neutral
   to reflect lower confidence — nice-to-have, not required for v1.

### 3c. Location fit

Job location strings are messy: `"Ontario"`, `"London, United Kingdom"`,
`"New York City, New York"`, `"Anywhere"`, `""`.

1. Config: `target_locations` (list, already a seeded key), `remote_ok`
   (default `Y`), `user_country` (optional — where the user actually is).
2. Detect remote via keywords in location OR title/description:
   `remote`, `anywhere`, `distributed`, `work from home`, `wfh`.
3. **Score**
   ```
   remote job AND remote_ok AND not geo-restricted away from user_country -> 1.0
   location matches a target (city/region/country)                       -> 1.0
   same country as a target, different city                              -> 0.6
   location present, no match, not remote                                -> 0.0
   job location empty                                                    -> UNKNOWN
   target_locations empty (user set no preference)                       -> UNKNOWN
   ```
   Matching is token/substring based, case-insensitive, after light
   normalization.

   **Geo-restricted remote (added 2026-08-12, found via live testing):**
   "Remote" alone in a listing doesn't mean remote-from-anywhere — real
   postings say things like `"Remote within United States"` or
   `"Remote within Canada or United States"` in the `location` field
   itself. If `user_country` is set and the location field contains a
   `remote (within|in|for|based in) <region>` phrase that doesn't name
   the user's country, that restriction wins over the bare "remote"
   keyword — the listing falls through to the normal (non-remote)
   matching logic instead of getting automatic full credit. If
   `user_country` is unset, this check is skipped entirely (can't judge,
   so don't penalize) and behavior is unchanged from before.

## 4. Combining into match_score

Weighted average over the dimensions, then scale to 0–100.

Default weights (Config-tunable, see §7): **skill 0.60, location 0.25, salary 0.15.**
Rationale: skill is the most reliable and most informative signal and is
~always present; salary is usually UNKNOWN so a big weight would just inject a
constant; location is important but often remote/UNKNOWN.

## 5. Handling UNKNOWN — dynamic reweighting (the key mechanic)

Do **not** fill an UNKNOWN dimension with a neutral constant. Instead drop it and
renormalize the *remaining* weights to sum to 1:

```
present = {dim: (score, weight) for dim if score is not UNKNOWN}
match   = sum(score*weight for present) / sum(weight for present)
match_score = round(100 * match * staleness_multiplier)   # staleness_multiplier defaults 1.0, see §9
```

Skill is essentially always present, so there is always ≥1 scored dimension.

Why this matters concretely: with the **current** Config (no `salary_floor`, empty
`target_locations`), salary and location are both UNKNOWN, so M4 gracefully
degrades to **pure skill-overlap ranking** — exactly right until the user sets
preferences. Add a `salary_floor` and it starts counting; add `target_locations`
and location starts counting. No code change, no weird "everything scores 50
because two dimensions are neutral" artifact.

## 6. AI provider hook (M14), scoped to the skill dimension only

Put skill scoring behind one interface:
```
score_skills(job, profile, config) -> SkillResult(score, matched_skills, rationale?)
```
- `ai_provider = none` → the deterministic §3a implementation. **This is the
  default and the always-on Phase-1 path.**
- `ai_provider = claude | gemini` → an implementation that asks the model for a
  *semantic* skill-overlap judgment (catches "event-driven microservices" ≈ the
  resume's "Kafka event pipeline", which lexical matching misses) and returns the
  same `SkillResult` shape.

Salary and location stay deterministic in **all** modes — no value in spending
tokens on numeric/string comparisons. If AI mode is on: batch multiple jobs per
call and cache results by `job_id` so re-runs don't re-spend. Any API/network
failure must **fall back to the rule-based scorer**, never crash the scan.

## 7. Config keys M4 introduces (all optional, sensible defaults)

| key | default | meaning |
|---|---|---|
| `match_threshold` | `75` | score `<` this ⇒ status set to `Ignored` |
| `weight_skill` / `weight_salary` / `weight_location` | `0.60/0.15/0.25` | dimension weights |
| `skill_saturation` | `4.0` | weighted-hit sum that saturates skill_score to 1.0 |
| `core_skills` | *(derived)* | comma-list; overrides the core-skill heuristic |
| `salary_floor` | *(unset ⇒ salary UNKNOWN)* | minimum acceptable annual salary |
| `salary_target` | *(optional)* | ideal salary (top of the ramp) |
| `salary_currency` | `USD` | base currency for comparison |
| `remote_ok` | `Y` | whether remote jobs score full location |
| `target_locations` | *(already seeded, empty)* | comma-list of acceptable locations |
| `user_country` | *(unset ⇒ geo-restriction check skipped)* | where the user actually is; used to detect "Remote within X" restrictions that exclude them |
| `ai_provider` | `none` | already exists; selects skill-scoring mode |

Keeping every knob in Config honors the project rule: tune the whole system
without touching code.

## 8. Which rows M4 processes (idempotency)

Process only rows where `match_score` is **empty** (regardless of source). Once a
row is scored, never rescore it — this makes re-runs safe and never clobbers a
status the user changed by hand in the dashboard (`Reviewed`/`Interested`/etc.),
nor resurrects a row M4 previously set to `Ignored`. Write scores with the batched
`append`/`update` path (M1 already proved per-row Sheets writes blow the
read-quota; reuse the batched client methods — ideally one bulk update, not one
call per row).

## 9. Forward-compat hooks (don't build now, just don't block them)

- **M12 staleness:** leave `staleness_multiplier` in the final formula (default
  1.0). M12 can later scale stale/reposted jobs down without touching M4's core.
- **Score breakdown persistence:** the scorer function should *return* the full
  breakdown (per-dimension scores + matched skills + rationale), even though the
  current `Jobs` schema only stores the final int. M5 can use the in-memory
  breakdown during the same run. See §10 open question.

## 10. Open decisions for the user (please confirm before implementing)

1. **Persist the breakdown?** The `Jobs` tab has only a `match_score` column.
   Options: (a) store just the 0–100 int [no schema change, recommended for now];
   (b) add a `match_detail` column (skills matched + per-dimension scores) — a
   schema change touching `sheets/schema.py` + a re-run of `ensure_schema`, useful
   for debugging and for M5's digest to explain *why* a job matched. Recommend (a)
   now, revisit if the digest feels opaque.
2. **One threshold or two?** DESIGN.md implies a single `match_threshold` (below ⇒
   Ignored; at/above ⇒ digest). A split (`ignore_threshold` < `digest_threshold`)
   would create a reviewable middle band that's scored but neither emailed nor
   hidden. Recommend single threshold for v1.
3. **Salary currency:** skip cross-currency conversion for v1 (note the caveat), or
   ship a small static rate map in Config? Recommend skip-with-caveat for v1.
4. **Missing-dimension policy:** confirm dynamic reweighting (§5) over the
   neutral-constant alternative. Recommend reweighting (degrades to skill-only
   cleanly with the current empty Config).

## 11. Testability note for the implementer

The rule-based path is fully deterministic → unit-test it with fixture jobs and a
fixture profile (mock the Sheet exactly like `tests/fake_gspread.py`, no network).
Cover: symbolic-skill boundaries (`C`/`C#`/`C++`/`.NET` don't false-match), title
vs description weighting, saturation cap, salary UNKNOWN vs below-floor vs above-
target, remote detection, empty-Config degrades to skill-only, and the
below-threshold → `Ignored` transition. Keep the live (real-Sheet) test to a
single end-to-end run per the project's live-test-before-commit rule.
