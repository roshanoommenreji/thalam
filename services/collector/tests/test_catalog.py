"""Backstage catalog files -> components (SPEC-002-R4). Task 8 adds the mirror's database half."""
# covers: SPEC-002-R4

from __future__ import annotations

from pathlib import Path

from thalam_collector.catalog import DESCRIPTION_CAP, read_catalog

GROUP = """\
apiVersion: backstage.io/v1alpha1
kind: Group
metadata: {name: team-a}
spec: {type: team}
"""


def _component(name: str, *, owner: str = "group:team-a", depends: str = "[]",
               description: str = "A service.") -> str:
    return f"""\
apiVersion: backstage.io/v1alpha1
kind: Component
metadata: {{name: {name}, description: {description}}}
spec: {{type: service, lifecycle: production, owner: {owner}, dependsOn: {depends}}}
"""


def _write(tmp_path: Path, *docs: str) -> Path:
    folder = tmp_path / "catalog"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "team.yaml").write_text("---\n".join(docs), encoding="utf-8")
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
    catalog, problems = read_catalog(_write(tmp_path, GROUP, api_doc))
    assert problems == [] and catalog.components == ()


def test_yaml_tags_are_never_run(tmp_path: Path) -> None:
    planted = "!!python/object/apply:os.system ['echo planted']\n"
    _, problems = read_catalog(_write(tmp_path, planted))
    assert [p.field for p in problems] == ["(file)"]
    assert "not valid YAML" in problems[0].message


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
    assert [p.field for p in problems] == [
        "documents[1].spec.dependsOn[0]", "documents[1].spec.dependsOn[1]",
        "documents[1].spec.dependsOn[2]"]


def test_a_component_cannot_depend_on_itself_or_appear_twice(tmp_path: Path) -> None:
    root = _write(tmp_path, GROUP, _component("api", depends='["component:api"]'),
                  _component("api"))
    messages = [p.message for p in read_catalog(root)[1]]
    assert "a component cannot depend on itself" in messages
    assert "'api' is defined twice" in messages


def test_descriptions_are_capped(tmp_path: Path) -> None:
    root = _write(tmp_path, GROUP, _component("api", description="x" * 5000))
    catalog, _ = read_catalog(root)
    assert len(catalog.components[0].description) == DESCRIPTION_CAP


def test_no_catalog_files_is_a_problem(tmp_path: Path) -> None:
    _, problems = read_catalog(tmp_path)
    assert [p.file for p in problems] == ["catalog/"]
