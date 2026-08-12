import re

from .aliases import SEARCH_EXCLUDED_VARIANTS, VARIANTS_BY_CANONICAL, canonicalize
from .constants import UNKNOWN

TITLE_MULTIPLIER = 1.5
DEFAULT_SATURATION = 4.0

# "C", "R", "Go" are also ordinary English words/letters (grade C, the
# pronoun-adjacent "go", a stray "R") — matching them on a bare word boundary
# produces too many false positives. Require them to sit in list-like
# punctuation context (comma/slash/parens/etc.), not just surrounded by
# regular prose whitespace. C++/C#/.NET are distinctive enough to not need
# this extra restriction — the standard symbol-aware boundary is enough.
AMBIGUOUS_CANONICALS = {"c", "r", "go"}
# Deliberately no comma/colon on the LEFT side check — "communication
# skills, C level stakeholders" has a comma-space immediately before "C"
# too, same shape as a real list ("Languages: C, ..."). Only a trailing
# delimiter reliably distinguishes an enumerated list from ordinary prose.
#
# Deliberately no '.' either — confirmed against real scanned jobs:
# "Arthur C. Clarke famously said..." puts a period right after a bare "C"
# from an ordinary middle initial, identical in shape to a period ending an
# enumerated list ("...Python, and R."). The false positive (any "X. Y"
# name) is far more common than the list-ending case it was meant to catch.
TRAILING_LIST_DELIMS = set(",/;:()[]|-\n")

# Bare "js"/"ts" satisfy the normal non-alnum boundary check inside
# "Node.js"/"Next.js"/"config.ts" too, since '.' counts as non-alnum on both
# sides — confirmed against real scanned jobs. Reject those specifically by
# excluding a literal '.' immediately before the match; a genuine standalone
# "JS"/"TS" mention is essentially never preceded by a dot.
DOT_SUFFIX_EXCLUDED_VARIANTS = {"js", "ts"}

_PATTERN_CACHE = {}


def _split_csv(value):
    return [v.strip() for v in (value or "").split(",") if v.strip()]


def _variant_pattern(variant):
    parts = [p for p in re.split(r"[\s\-]+", variant.strip()) if p]
    if not parts:
        return None
    escaped = [re.escape(p) for p in parts]
    body = r"[\s-]+".join(escaped)
    # Non-alnum lookaround (not \b) so symbols like + and # at the edge of a
    # match still get a real boundary check — \b's word-char definition
    # doesn't reliably bound tokens like "C++" or "C#".
    pattern = rf"(?<![A-Za-z0-9]){body}(?![A-Za-z0-9])"
    return re.compile(pattern, re.IGNORECASE)


def _pattern_for(variant):
    if variant not in _PATTERN_CACHE:
        _PATTERN_CACHE[variant] = _variant_pattern(variant)
    return _PATTERN_CACHE[variant]


def _has_trailing_delimiter(text, end):
    """True if a list-like delimiter follows the match (skipping at most
    one space) or the match runs to the end of the text, e.g. "C/C++",
    "(C)", ", C,", or "...Python, R" as the last item. Only the trailing
    side is checked — a leading comma-space is just as common in ordinary
    prose ("skills, C level stakeholders") as in a real list, so it can't
    distinguish the two; a *trailing* delimiter reliably can.
    """
    if end >= len(text):
        return True
    pos = end
    if text[pos] == " " and pos + 1 < len(text):
        pos += 1
    return pos < len(text) and text[pos] in TRAILING_LIST_DELIMS


def build_vocabulary(resume_profile, config):
    """Weighted skill vocabulary: canonical skill name -> weight (2.0 for
    core skills, 1.0 otherwise). Core skills = Config.core_skills if set,
    else the most-recent work_experience entry's tech_stack unioned with the
    first ~3 listed languages (resumes front-load their strongest skills).
    """
    skills_block = resume_profile.get("skills", {}) or {}
    languages = skills_block.get("languages", []) or []

    raw_names = []
    raw_names += languages
    raw_names += skills_block.get("technologies_tools", []) or []
    for exp in resume_profile.get("work_experience", []) or []:
        raw_names += exp.get("tech_stack", []) or []

    canonical_names = {canonicalize(name) for name in raw_names if name and name.strip()}

    core_override = config.get("core_skills")
    if core_override:
        core = {canonicalize(s) for s in _split_csv(core_override)}
    else:
        core = set()
        work_experience = resume_profile.get("work_experience", []) or []
        if work_experience:
            core |= {canonicalize(t) for t in (work_experience[0].get("tech_stack", []) or [])}
        core |= {canonicalize(lang) for lang in languages[:3]}

    return {name: (2.0 if name in core else 1.0) for name in canonical_names}


class SkillResult:
    __slots__ = ("score", "matched")

    def __init__(self, score, matched):
        self.score = score
        self.matched = matched


def score_skills(job_row, vocabulary, saturation=DEFAULT_SATURATION):
    """Skill-overlap dimension. UNKNOWN only when the job has no text at
    all; otherwise always a real score (0.0 included) since "no skills
    matched" is a real signal, not missing information.
    """
    title = (job_row.get("title") or "").strip()
    description = (job_row.get("description_raw") or "").strip()
    if not title and not description:
        return SkillResult(UNKNOWN, [])

    title_lower = title.lower()
    title_len = len(title_lower)
    combined = f"{title_lower} {description.lower()}"

    matched = []
    raw_total = 0.0
    for canonical, weight in vocabulary.items():
        variants = [
            v
            for v in VARIANTS_BY_CANONICAL.get(canonical, [canonical])
            if v not in SEARCH_EXCLUDED_VARIANTS
        ]
        found_title = False
        found_desc = False
        for variant in variants:
            pattern = _pattern_for(variant)
            if not pattern:
                continue
            for m in pattern.finditer(combined):
                if canonical in AMBIGUOUS_CANONICALS and not _has_trailing_delimiter(
                    combined, m.end()
                ):
                    continue
                if variant in DOT_SUFFIX_EXCLUDED_VARIANTS and m.start() > 0 and combined[m.start() - 1] == ".":
                    continue
                if m.start() < title_len:
                    found_title = True
                else:
                    found_desc = True

        if found_title or found_desc:
            contribution = weight * (TITLE_MULTIPLIER if found_title else 1.0)
            raw_total += contribution
            matched.append(canonical)

    score = min(1.0, raw_total / saturation) if raw_total > 0 else 0.0
    return SkillResult(score, sorted(matched))
