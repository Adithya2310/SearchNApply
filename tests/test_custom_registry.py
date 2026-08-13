import types

import pytest

from job_sources.custom import registry


def test_returns_none_when_no_module_matches_slug():
    assert registry.get_fetcher("doesnotexist") is None


def test_returns_the_modules_fetch_jobs_function(monkeypatch):
    def fake_fetch_jobs(identifier, company_name=None, target_roles=None, existing_job_ids=None):
        return []

    fake_module = types.SimpleNamespace(fetch_jobs=fake_fetch_jobs)
    monkeypatch.setattr(
        registry.importlib, "import_module", lambda name: fake_module if name == "job_sources.custom.oracle" else (_ for _ in ()).throw(ModuleNotFoundError(name="job_sources.custom.oracle"))
    )

    assert registry.get_fetcher("oracle") is fake_fetch_jobs


def test_raises_when_module_exists_but_has_no_fetch_jobs(monkeypatch):
    fake_module = types.SimpleNamespace()
    monkeypatch.setattr(registry.importlib, "import_module", lambda name: fake_module)

    with pytest.raises(AttributeError):
        registry.get_fetcher("oracle")


def test_reraises_when_the_modules_own_internal_import_fails(monkeypatch):
    # The module file exists but itself fails to import something else —
    # must not be silently treated as "no scraper for this company".
    def raise_unrelated_missing_import(name):
        raise ModuleNotFoundError(name="some_other_missing_dependency")

    monkeypatch.setattr(registry.importlib, "import_module", raise_unrelated_missing_import)

    with pytest.raises(ModuleNotFoundError):
        registry.get_fetcher("oracle")
