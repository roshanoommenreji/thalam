"""Release manifests, Jira-shaped files and the calendar (SPEC-002-R5)."""
# covers: SPEC-002-R5

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from pathlib import Path

import pytest
from thalam_collector.company import SUMMARY_CAP, read_company
from thalam_collector.problems import LoadError

Make = Callable[..., Path]


def test_a_valid_company(company_tree: Make) -> None:
    company = read_company(company_tree())
    by_label = {f"{r.component} {r.version}": r for r in company.releases}
    assert sorted(by_label) == ["api 1.0.0", "api 1.1.0", "db-svc 2.0.0"]
    assert by_label["api 1.1.0"].needs == (("db-svc", ">=2.0.0"),)
    assert by_label["api 1.1.0"].jira_version_id == "2"
    assert [e.state for e in by_label["api 1.0.0"].events][-1] == "released"
    assert by_label["api 1.0.0"].events[0].window == (date(2026, 10, 1), date(2026, 10, 1))
    assert [(i.jira_key, i.component, i.version, i.status) for i in company.items] == [
        ("API-1", "api", "1.1.0", "In Progress")]
    assert [(w.name, w.kind) for w in company.windows] == [("year-end freeze", "freeze")]
    assert company.warnings == ()


def test_a_replan_moves_the_window(company_tree: Make) -> None:
    root = company_tree(replace={"releases/db-svc.yaml": (
        "      - scoped 2026-11-02T10:00:00+05:30\n",
        "      - scoped 2026-11-02T10:00:00+05:30\n"
        "      - replan 2026-11-05T10:00:00+05:30 2026-11-24 2026-11-25\n")})
    db_svc = next(r for r in read_company(root).releases if r.component == "db-svc")
    assert db_svc.events[-1].kind == "replan"
    assert db_svc.events[-1].window == (date(2026, 11, 24), date(2026, 11, 25))


def test_a_manifest_refuses_unknown_fields(company_tree: Make) -> None:
    root = company_tree(replace={"releases/api.yaml": ("component: api\n",
                                                       "component: api\ncolour: blue\n")})
    with pytest.raises(LoadError) as caught:
        read_company(root)
    # The manifest is then skipped, so the Jira files' api versions name no release too.
    assert ("releases/api.yaml", "colour") in [(p.file, p.field) for p in caught.value.problems]


@pytest.mark.parametrize("bad", ["~=2.0", "==2.*", "soon"])
def test_ranges_use_comparison_operators_only(company_tree: Make, bad: str) -> None:
    root = company_tree(replace={"releases/api.yaml": ('">=2.0.0"', f'"{bad}"')})
    with pytest.raises(LoadError) as caught:
        read_company(root)
    assert caught.value.problems[0].field == "releases[1].needs.db-svc"


def test_jira_extra_fields_are_ignored_and_summaries_capped(company_tree: Make) -> None:
    root = company_tree(replace={"jira/search.json": (
        '"Call the new db endpoint"', '"' + "s" * 400 + '", "priority": {"name": "High"}')})
    item = read_company(root).items[0]
    assert len(item.summary) == SUMMARY_CAP == 255


def test_a_need_outside_the_catalog_edge_loads_with_a_warning(company_tree: Make) -> None:
    root = company_tree(replace={"catalog/team.yaml": (', dependsOn: ["component:db-svc"]', "")})
    assert read_company(root).warnings == (
        "api 1.1.0 needs db-svc, but api's catalog entry does not depend on it",)
