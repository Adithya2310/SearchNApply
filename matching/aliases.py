import re

_TRAILING_PAREN_RE = re.compile(r"\s*\([^)]*\)\s*$")


def clean_skill_name(name):
    """Strip a trailing parenthetical qualifier, e.g. 'GitHub Actions (CI/CD)'
    -> 'GitHub Actions', so the qualifier doesn't become part of the canonical
    skill name used for matching.
    """
    name = (name or "").strip()
    name = _TRAILING_PAREN_RE.sub("", name).strip()
    return name


# Each group is lexical variants of one skill; the first entry is the
# canonical form. Groups are intentionally small and resume-driven — extend
# as new skills/variants come up rather than trying to be exhaustive upfront.
ALIAS_GROUPS = [
    ["react", "reactjs", "react.js"],
    ["next", "nextjs", "next.js"],
    ["node", "nodejs", "node.js"],
    ["postgres", "postgresql"],
    ["js", "javascript"],
    ["ts", "typescript"],
    [".net", "dotnet", "dot net", "asp.net", "asp .net", ".net core", ".net 8", ".net 6"],
    ["github actions", "gh actions", "github action"],
    ["c#", "csharp", "c-sharp"],
    ["c++", "cpp"],
    ["sql server", "sqlserver", "mssql"],
    ["ci/cd", "cicd", "ci cd"],
]

# Bare "next" collapses too often with ordinary English ("our next phase of
# growth", standard boilerplate in nearly every job posting) to search for
# directly — confirmed against real scanned jobs, where it inflated ~9% of
# scores with no genuine Next.js mention. The canonical skill still matches
# fine via its unambiguous compound variants ("nextjs", "next.js"), which in
# practice co-occur with any real Next.js JD anyway.
SEARCH_EXCLUDED_VARIANTS = {"next"}

VARIANTS_BY_CANONICAL = {}
_CANONICAL_BY_VARIANT = {}
for _group in ALIAS_GROUPS:
    _canonical = _group[0]
    VARIANTS_BY_CANONICAL[_canonical] = list(_group)
    for _variant in _group:
        _CANONICAL_BY_VARIANT[_variant] = _canonical


def canonicalize(raw_name):
    """Collapse lexical variants (React/ReactJS/React.js) to one canonical,
    lowercase skill name. Skills with no alias entry canonicalize to
    themselves (cleaned + lowercased).
    """
    key = clean_skill_name(raw_name).lower()
    return _CANONICAL_BY_VARIANT.get(key, key)
