"""Release manifests, Jira-shaped files and the calendar (SPEC-002-R5)."""
# covers: SPEC-002-R5

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date
from pathlib import Path

import pytest
from thalam_collector.company import SUMMARY_CAP, read_company, to_graph
from thalam_collector.problems import LoadError
from thalam_shared.graph import Window, prod_version

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
    # The manifest is skipped, and its Jira versions are not blamed for it (one cause, one problem).
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


# --- Hardening (review of THL-34): no file may crash the load, and every cause is one problem ---


def _where(caught: pytest.ExceptionInfo[LoadError]) -> list[tuple[str, str]]:
    return [(p.file, p.field) for p in caught.value.problems]


def test_an_impossible_date_in_the_calendar_is_a_problem(company_tree: Make) -> None:
    root = company_tree(replace={"calendar.yaml": ("2026-12-19", "2026-13-19")})
    with pytest.raises(LoadError) as caught:
        read_company(root)
    assert _where(caught) == [("calendar.yaml", "(file)")]
    assert caught.value.problems[0].message.startswith("not valid YAML")


def test_an_impossible_date_in_a_release_window_is_a_problem(company_tree: Make) -> None:
    root = company_tree(replace={"releases/api.yaml": (
        "window: [2026-12-01, 2026-12-01]", "window: [2026-13-01, 2026-12-01]")})
    with pytest.raises(LoadError) as caught:
        read_company(root)
    assert _where(caught) == [("releases/api.yaml", "(file)")]


@pytest.mark.parametrize("name", ["releases/api.yaml", "jira/search.json", "jira/versions.json"])
def test_a_file_that_is_not_utf8_is_a_problem(company_tree: Make, name: str) -> None:
    root = company_tree()
    (root / name).write_bytes(b"\xff\xfe not text\n")
    with pytest.raises(LoadError) as caught:
        read_company(root)
    assert [p.message for p in caught.value.problems if p.file == name] == ["not UTF-8"]
    assert (name, "(file)") in _where(caught)


def test_malformed_json_names_the_file(company_tree: Make) -> None:
    root = company_tree(files={"jira/search.json": '{"issues": [\n'})
    with pytest.raises(LoadError) as caught:
        read_company(root)
    assert _where(caught) == [("jira/search.json", "(file)")]
    assert caught.value.problems[0].message.startswith("not valid JSON at line ")


def test_an_empty_manifest_is_a_problem(company_tree: Make) -> None:
    with pytest.raises(LoadError) as caught:
        read_company(company_tree(files={"releases/api.yaml": ""}))
    assert [(p.file, p.field, p.message) for p in caught.value.problems] == [
        ("releases/api.yaml", "(file)", "the file is empty")]


def test_a_two_document_manifest_is_a_problem(company_tree: Make) -> None:
    text = "component: api\nreleases: []\n---\ncomponent: api\nreleases: []\n"
    with pytest.raises(LoadError) as caught:
        read_company(company_tree(files={"releases/api.yaml": text}))
    assert [(p.file, p.field, p.message) for p in caught.value.problems] == [
        ("releases/api.yaml", "(file)", "one document per file")]


def test_a_top_level_type_error_says_which_file(company_tree: Make) -> None:
    root = company_tree(files={"releases/db-svc.yaml": "- a\n- b\n", "jira/search.json": "[]\n"})
    with pytest.raises(LoadError) as caught:
        read_company(root)
    assert sorted(_where(caught)) == [("jira/search.json", "(file)"),
                                      ("releases/db-svc.yaml", "(file)")]


def _search(*issues: dict[str, object]) -> str:
    return json.dumps({"issues": list(issues)})


def _issue(key: str, *ids: str) -> dict[str, object]:
    return {"key": key, "fields": {"summary": "s", "status": {"name": "To Do"},
                                   "fixVersions": [{"id": i} for i in ids]}}


def test_a_jira_key_listed_twice_for_a_release_is_a_problem(company_tree: Make) -> None:
    root = company_tree(files={"jira/search.json": _search(_issue("API-1", "2"),
                                                           _issue("API-1", "2"))})
    with pytest.raises(LoadError) as caught:
        read_company(root)
    assert [(p.file, p.field, p.message) for p in caught.value.problems] == [
        ("jira/search.json", "issues[1].fields.fixVersions[0]",
         "API-1 is listed twice for api 1.1.0")]


def test_one_issue_naming_a_fix_version_twice_is_a_problem(company_tree: Make) -> None:
    root = company_tree(files={"jira/search.json": _search(_issue("API-1", "2", "2"))})
    with pytest.raises(LoadError) as caught:
        read_company(root)
    assert [(p.field, p.message) for p in caught.value.problems] == [
        ("issues[0].fields.fixVersions[1]", "API-1 is listed twice for api 1.1.0")]


def test_one_issue_may_belong_to_two_releases(company_tree: Make) -> None:
    root = company_tree(files={"jira/search.json": _search(_issue("API-1", "2", "3"))})
    assert [(i.component, i.version) for i in read_company(root).items] == [
        ("api", "1.1.0"), ("db-svc", "2.0.0")]


def test_a_fix_version_that_names_no_jira_version_is_a_problem(company_tree: Make) -> None:
    root = company_tree(files={"jira/search.json": _search(_issue("API-1", "9"))})
    with pytest.raises(LoadError) as caught:
        read_company(root)
    assert [(p.file, p.field) for p in caught.value.problems] == [
        ("jira/search.json", "issues[0].fields.fixVersions[0]")]
    assert "no Jira version with id '9'" in caught.value.problems[0].message


def test_no_manifests_is_one_problem(company_tree: Make) -> None:
    root = company_tree(files={"releases/api.yaml": None, "releases/db-svc.yaml": None})
    with pytest.raises(LoadError) as caught:
        read_company(root)
    assert [(p.file, p.field, p.message) for p in caught.value.problems] == [
        ("releases/", "(folder)", "no release manifests")]


def test_a_yml_manifest_is_refused_not_skipped(company_tree: Make) -> None:
    root = company_tree()
    (root / "releases/api.yaml").rename(root / "releases/api.yml")
    with pytest.raises(LoadError) as caught:
        read_company(root)
    assert [(p.file, p.field, p.message) for p in caught.value.problems] == [
        ("releases/api.yml", "(file)", "only .yaml files are read: rename it to .yaml")]


def test_a_folder_named_like_a_manifest_is_not_read(company_tree: Make) -> None:
    root = company_tree()
    (root / "releases/old.yaml").mkdir()
    assert len(read_company(root).releases) == 3


def test_summary_and_status_are_flattened_to_plain_text(company_tree: Make) -> None:
    # NUL, ESC and a newline are control characters; U+202E reorders text when printed, so it is
    # flattened too (thalam_collector.text decides this once for every untrusted string).
    ugly = "a\x1bb\x00c\nd‮e"
    root = company_tree(replace={
        "jira/search.json": ('"Call the new db endpoint"', json.dumps(ugly))})
    assert read_company(root).items[0].summary == "a b c d e"
    root = company_tree(replace={"jira/search.json": ('"In Progress"', json.dumps("In\x00\nP"))})
    assert read_company(root).items[0].status == "In P"


_LONG = "x" * 1000
_BIG_ECHOES = [
    ("jira/versions.json", '"name": "api 1.1.0"', f'"name": "{_LONG}"'),
    ("releases/api.yaml", "version: 1.1.0", f"version: 1.1.{_LONG}"),
    ("releases/api.yaml", '">=2.0.0"', f'"{_LONG}"'),
    ("releases/api.yaml", "component: api\n", f"component: {_LONG}\n"),
    ("releases/api.yaml", "planned 2026-11-10T10", f"{'z' * 1000} 2026-11-10T10"),
    ("releases/api.yaml", "planned 2026-11-10T10:00:00+05:30", f"planned {'9' * 1000}"),
    ("releases/api.yaml", "planned 2026-11-10T10:00:00+05:30",
     f"replan 2026-11-10T10:00:00+05:30 {'9' * 1000} 2026-11-11"),
    ("calendar.yaml", "kind: freeze", f"kind: {_LONG}"),
]


@pytest.mark.parametrize(("name", "old", "new"), _BIG_ECHOES)
def test_a_problem_never_echoes_a_long_value(company_tree: Make, name: str, old: str,
                                             new: str) -> None:
    root = company_tree(replace={name: (old, new)})
    with pytest.raises(LoadError) as caught:
        read_company(root)
    assert caught.value.problems
    assert all(len(str(p)) < 250 for p in caught.value.problems), [
        str(p)[:100] for p in caught.value.problems]


def test_a_window_name_is_not_echoed_whole(company_tree: Make) -> None:
    text = ("windows:\n"
            f"  - {{name: {_LONG}, kind: freeze, starts: 2026-12-19, ends: 2027-01-04}}\n"
            f"  - {{name: {_LONG}, kind: freeze, starts: 2026-12-19, ends: 2027-01-04}}\n")
    with pytest.raises(LoadError) as caught:
        read_company(company_tree(files={"calendar.yaml": text}))
    assert caught.value.problems
    assert all(len(str(p)) < 250 for p in caught.value.problems)


def test_a_wrongly_cased_name_gets_a_hint_but_still_fails(company_tree: Make) -> None:
    root = company_tree(replace={"releases/api.yaml": ("component: api\n", "component: API\n")})
    with pytest.raises(LoadError) as caught:
        read_company(root)
    assert [(p.file, p.field, p.message) for p in caught.value.problems] == [
        ("releases/api.yaml", "component",
         "no component named 'API' in the catalog (did you mean 'api'?)")]


def test_a_wrongly_cased_need_gets_a_hint(company_tree: Make) -> None:
    root = company_tree(replace={"releases/api.yaml": ("needs: {db-svc:", "needs: {DB-SVC:")})
    with pytest.raises(LoadError) as caught:
        read_company(root)
    assert [(p.field, p.message) for p in caught.value.problems] == [
        ("releases[1].needs.DB-SVC",
         "no component named 'DB-SVC' in the catalog (did you mean 'db-svc'?)")]


def test_a_failed_manifest_does_not_also_fail_its_jira_files(company_tree: Make) -> None:
    # One cause, one problem: api's two Jira versions and its item would each have said so too.
    root = company_tree(replace={"releases/api.yaml": ("component: api\n", "component: ghost\n")})
    with pytest.raises(LoadError) as caught:
        read_company(root)
    assert [(p.file, p.field, p.message) for p in caught.value.problems] == [
        ("releases/api.yaml", "component", "no component named 'ghost' in the catalog")]


def test_unknown_fields_are_refused_in_a_release_and_in_a_window(company_tree: Make) -> None:
    root = company_tree(replace={
        "releases/db-svc.yaml": ("  - version: 2.0.0\n", "  - version: 2.0.0\n    colour: blue\n"),
        "calendar.yaml": ("kind: freeze,", "kind: freeze, colour: blue,")})
    with pytest.raises(LoadError) as caught:
        read_company(root)
    assert sorted(_where(caught)) == [("calendar.yaml", "windows[0].colour"),
                                      ("releases/db-svc.yaml", "releases[0].colour")]


def test_the_company_becomes_the_graph_its_files_describe(company_tree: Make) -> None:
    g = to_graph(read_company(company_tree()))
    assert {name: c.owner for name, c in g.components.items()} == {
        "api": "team-a", "db-svc": "team-a"}
    assert {name: set(deps) for name, deps in g.depends_on.items()} == {
        "api": {"db-svc"}, "db-svc": set()}
    assert sorted((r.component, r.version, r.state, r.window) for r in g.releases) == [
        ("api", "1.0.0", "released", (date(2026, 10, 1), date(2026, 10, 1))),
        ("api", "1.1.0", "planned", (date(2026, 12, 1), date(2026, 12, 1))),
        ("db-svc", "2.0.0", "scoped", (date(2026, 11, 20), date(2026, 11, 20)))]
    assert [(n.component, n.spec) for r in g.releases for n in r.needs] == [("db-svc", ">=2.0.0")]
    assert g.windows == (
        Window("year-end freeze", "freeze", date(2026, 12, 19), date(2027, 1, 4)),)
    assert prod_version(g, "api") == "1.0.0"


def test_a_5000_character_jira_version_name_gives_a_short_message(company_tree: Make) -> None:
    root = company_tree(replace={"jira/versions.json": (
        '"name": "api 1.1.0"', '"name": "' + "x" * 5000 + '"')})
    with pytest.raises(LoadError) as caught:
        read_company(root)
    named = [p for p in caught.value.problems if "names no release" in p.message]
    assert len(named) == 1 and len(named[0].message) < 200
