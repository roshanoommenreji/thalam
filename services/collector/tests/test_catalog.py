"""Backstage catalog files -> components (SPEC-002-R4). Task 8 adds the mirror's database half."""
# covers: SPEC-002-R4

from __future__ import annotations

from pathlib import Path

import pytest
from thalam_collector.catalog import DESCRIPTION_CAP, read_catalog
from thalam_collector.problems import Problem

GROUP = """\
apiVersion: backstage.io/v1alpha1
kind: Group
metadata: {name: team-a}
spec: {type: team}
"""

NO_COMPONENT = Problem("catalog/", "(folder)", "no Component in the catalog")


def _component(name: str, *, owner: str = "group:team-a", depends: str = "[]",
               description: str = "A service.", extra: str = "") -> str:
    return f"""\
apiVersion: backstage.io/v1alpha1
kind: Component
metadata: {{name: {name}, description: {description}{extra}}}
spec: {{type: service, lifecycle: production, owner: {owner}, dependsOn: {depends}}}
"""


def _write(tmp_path: Path, *docs: str, name: str = "team.yaml") -> Path:
    folder = tmp_path / "catalog"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text("---\n".join(docs), encoding="utf-8")
    return tmp_path


def test_several_documents_in_one_file(tmp_path: Path) -> None:
    root = _write(tmp_path, GROUP, _component("api", depends='["component:db-svc"]'),
                  _component("db-svc", owner="team-a"))
    catalog, problems = read_catalog(root)
    assert problems == []
    assert catalog.groups == frozenset({"team-a"})
    api = next(c for c in catalog.components if c.name == "api")
    assert (api.owner, api.depends_on, api.file) == ("team-a", ("db-svc",), "catalog/team.yaml")


def test_other_kinds_are_skipped(tmp_path: Path) -> None:
    api_doc = "apiVersion: backstage.io/v1alpha1\nkind: API\nmetadata: {name: x}\nspec: {}\n"
    catalog, problems = read_catalog(_write(tmp_path, GROUP, _component("api"), api_doc))
    assert problems == []
    assert [c.name for c in catalog.components] == ["api"]


def test_yaml_tags_are_never_run(tmp_path: Path) -> None:
    marker = tmp_path / "marker"
    planted = f"!!python/object/apply:builtins.open ['{marker.as_posix()}', 'w']\n"
    _, problems = read_catalog(_write(tmp_path, planted))
    file_problems = [p for p in problems if p.field == "(file)"]
    assert len(file_problems) == 1
    assert file_problems[0].message.startswith("not valid YAML")
    assert not marker.exists()


def test_a_yaml_error_names_the_line_and_the_real_problem(tmp_path: Path) -> None:
    _, problems = read_catalog(_write(tmp_path, "a: 1\n\tb: 2\n"))
    (found,) = [p for p in problems if p.field == "(file)"]
    assert found.file == "catalog/team.yaml"
    # The wording after the line number differs between libyaml and the pure-Python parser.
    assert found.message.startswith("not valid YAML at line 2: ")


HOSTILE = [
    pytest.param("bad.yaml", b"description: \xff\xfe\x80\n", "not UTF-8", id="not-utf8"),
    pytest.param("big.yaml", b"# " + b"x" * 1_048_576 + b"\n", "larger than 1 MiB", id="too-big"),
    pytest.param("deep.yaml", b"[" * 20_000, "not valid YAML", id="deeply-nested"),
    pytest.param("date.yaml", b"description: 2024-13-45\n",
                 "not valid YAML: a value could not be read (ValueError)", id="bad-timestamp"),
    pytest.param("tag.yaml", b"a: !!timestamp zzz\n",
                 "not valid YAML: a value could not be read (AttributeError)",
                 id="bad-tagged-scalar"),
    pytest.param("old.yml", b"kind: Group\n",
                 "only .yaml files are read: rename it to .yaml", id="yml-extension"),
]


@pytest.mark.parametrize(("name", "content", "message"), HOSTILE)
def test_a_hostile_file_is_one_problem_and_the_rest_still_load(
        tmp_path: Path, name: str, content: bytes, message: str) -> None:
    root = _write(tmp_path, GROUP, _component("api"))
    (root / "catalog" / name).write_bytes(content)
    catalog, problems = read_catalog(root)
    assert [(p.file, p.field) for p in problems] == [(f"catalog/{name}", "(file)")]
    assert problems[0].message.startswith(message)  # libyaml and PyYAML word some errors apart
    assert [c.name for c in catalog.components] == ["api"]


def test_a_folder_named_like_a_catalog_file_is_not_read(tmp_path: Path) -> None:
    root = _write(tmp_path, GROUP, _component("api"))
    for folder in ("nested.yaml", "sub"):  # "kind: component" is a problem if anything reads it
        (root / "catalog" / folder).mkdir()
        (root / "catalog" / folder / "inner.yaml").write_text("kind: component\n", encoding="utf-8")
    assert read_catalog(root)[1] == []


def test_a_huge_reference_is_one_short_problem(tmp_path: Path) -> None:
    root = _write(tmp_path, GROUP, _component("web"),
                  _component("api", depends=f'["{"x" * 100_000}"]'))
    _, problems = read_catalog(root)
    assert len(problems) == 1
    assert problems[0].field == "documents[2].spec.dependsOn[0]"
    assert len(problems[0].message) < 500


def test_names_follow_backstage(tmp_path: Path) -> None:
    _, problems = read_catalog(_write(tmp_path, GROUP, _component("Not A Name")))
    assert any(p.field == "documents[1].metadata.name" for p in problems)


def test_the_owner_must_be_a_group_in_the_catalog(tmp_path: Path) -> None:
    _, problems = read_catalog(_write(tmp_path, GROUP, _component("api", owner="group:nobody")))
    assert [(p.field, p.message) for p in problems] == [
        ("documents[1].spec.owner", "no Group named 'nobody' in the catalog")]


def test_every_dependency_must_be_a_component_in_the_catalog(tmp_path: Path) -> None:
    root = _write(tmp_path, GROUP,
                  _component("api", depends='["component:ghost", "db-svc", "resource:db"]'))
    _, problems = read_catalog(root)
    assert [(p.field, p.message) for p in problems] == [
        ("documents[1].spec.dependsOn[0]", "no Component named 'ghost' in the catalog"),
        ("documents[1].spec.dependsOn[1]", "'db-svc' is not component:<name>"),
        ("documents[1].spec.dependsOn[2]", "'resource:db' is not component:<name>")]


def test_a_reference_with_a_trailing_newline_is_refused(tmp_path: Path) -> None:
    root = _write(tmp_path, GROUP, _component("api", depends='["component:api2\\n"]'),
                  _component("api2"))
    _, problems = read_catalog(root)
    assert [(p.field, p.message) for p in problems] == [
        ("documents[1].spec.dependsOn[0]", "'component:api2\\n' is not component:<name>")]


def test_a_component_cannot_depend_on_itself(tmp_path: Path) -> None:
    root = _write(tmp_path, GROUP, _component("api", depends='["component:api"]'))
    _, problems = read_catalog(root)
    assert problems == [Problem("catalog/team.yaml", "documents[1].spec.dependsOn[0]",
                                "a component cannot depend on itself")]


def test_every_later_copy_of_a_component_is_reported_at_its_own_place(tmp_path: Path) -> None:
    _write(tmp_path, GROUP, _component("api"), name="a.yaml")
    root = _write(tmp_path, _component("API"), _component("api"), name="b.yaml")
    _, problems = read_catalog(root)
    assert problems == [
        Problem("catalog/b.yaml", "documents[0].metadata.name",
                "'API' is defined twice (first at catalog/a.yaml documents[1])"),
        Problem("catalog/b.yaml", "documents[1].metadata.name",
                "'api' is defined twice (first at catalog/a.yaml documents[1])")]


def test_a_duplicate_group_is_reported(tmp_path: Path) -> None:
    _write(tmp_path, GROUP, _component("api"), name="a.yaml")
    root = _write(tmp_path, GROUP.replace("team-a", "TEAM-A"), name="b.yaml")
    assert read_catalog(root)[1] == [
        Problem("catalog/b.yaml", "documents[0].metadata.name",
                "'TEAM-A' is defined twice (first at catalog/a.yaml documents[0])")]


def test_names_compare_without_regard_to_case(tmp_path: Path) -> None:
    root = _write(tmp_path, GROUP, _component("api"),
                  _component("web", owner="group:TEAM-A", depends='["component:API"]'))
    catalog, problems = read_catalog(root)
    assert problems == []
    web = next(c for c in catalog.components if c.name == "web")
    assert (web.owner, web.depends_on) == ("team-a", ("api",))


def test_a_self_dependency_is_found_whatever_the_case(tmp_path: Path) -> None:
    root = _write(tmp_path, GROUP, _component("api", depends='["component:API"]'))
    assert [p.message for p in read_catalog(root)[1]] == ["a component cannot depend on itself"]


def test_only_the_default_namespace_is_read(tmp_path: Path) -> None:
    root = _write(tmp_path, GROUP, _component("api", extra=", namespace: other"))
    assert read_catalog(root)[1] == [
        Problem("catalog/team.yaml", "documents[1].metadata.namespace",
                "only the default namespace is read")]


def test_descriptions_are_capped(tmp_path: Path) -> None:
    root = _write(tmp_path, GROUP, _component("api", description="x" * 5000))
    catalog, _ = read_catalog(root)
    assert len(catalog.components[0].description) == DESCRIPTION_CAP


def test_descriptions_are_flattened_to_one_line_of_plain_text(tmp_path: Path) -> None:
    # libyaml refuses a YAML-escaped lone surrogate, so a zero-width space stands in for one.
    raw = '"a\\x00b\\x1bc\\nd\\u2028e\\u200bf   g"'
    catalog, problems = read_catalog(_write(tmp_path, GROUP, _component("api", description=raw)))
    assert problems == []
    assert catalog.components[0].description == "a b c d e f g"


def test_an_empty_description_is_an_empty_string(tmp_path: Path) -> None:
    catalog, problems = read_catalog(_write(tmp_path, GROUP, _component("api", description="")))
    assert problems == []
    assert catalog.components[0].description == ""


def test_a_document_with_a_bad_kind_never_vanishes(tmp_path: Path) -> None:
    docs = ["metadata: {name: x}\n", "kind: 3\n", "kind: component\nmetadata: {name: y}\n",
            "kind: GROUP\nmetadata: {name: z}\n"]
    _, problems = read_catalog(_write(tmp_path, GROUP, _component("api"), *docs))
    assert [(p.field, p.message) for p in problems] == [
        ("documents[2].kind", "kind must be a string such as 'Component'"),
        ("documents[3].kind", "kind must be a string such as 'Component'"),
        ("documents[4].kind", "kind must be exactly 'Component'"),
        ("documents[5].kind", "kind must be exactly 'Group'")]


def test_an_empty_document_is_skipped(tmp_path: Path) -> None:
    root = _write(tmp_path, GROUP, "", _component("api"), "")
    catalog, problems = read_catalog(root)
    assert problems == []
    assert [c.name for c in catalog.components] == ["api"]


def test_a_catalog_with_no_component_fails(tmp_path: Path) -> None:
    assert read_catalog(_write(tmp_path, GROUP))[1] == [NO_COMPONENT]


def test_a_catalog_of_empty_files_fails(tmp_path: Path) -> None:
    assert read_catalog(_write(tmp_path, "", name="empty.yaml"))[1] == [NO_COMPONENT]
    assert read_catalog(_write(tmp_path, "# only a comment\n", name="empty.yaml"))[1] == [
        NO_COMPONENT]


def test_no_catalog_files_is_a_problem(tmp_path: Path) -> None:
    _, problems = read_catalog(tmp_path)
    assert [p.file for p in problems] == ["catalog/"]
