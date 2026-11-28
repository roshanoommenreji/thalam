"""The release graph's queries, on graphs built by hand (SPEC-002-R9, R10, R11). No database."""
# covers: SPEC-002-R9, SPEC-002-R10, SPEC-002-R11

from __future__ import annotations

from collections.abc import Iterable
from datetime import date

import pytest
from thalam_shared.graph import (
    Component,
    Graph,
    GraphError,
    Need,
    Release,
    Step,
    UnknownName,
    Window,
    downstream,
    make_graph,
    must_ship_before,
    parse_range,
    parse_version,
    prod_version,
    release,
    release_order,
    upstream,
)
from thalam_shared.lifecycle import NOT_IN_FLIGHT, STATES

DAY = (date(2026, 12, 1), date(2026, 12, 1))


def rel(component: str, version: str, state: str = "planned",
        needs: Iterable[tuple[str, str]] = ()) -> Release:
    return Release(component, version, state, DAY, tuple(Need(c, s) for c, s in needs))


def graph_of(edges: Iterable[tuple[str, str]], releases: Iterable[Release],
             retired: Iterable[str] = ()) -> Graph:
    edges, releases, gone = list(edges), list(releases), set(retired)
    names = {n for edge in edges for n in edge} | {r.component for r in releases}
    return make_graph([Component(n, "team", n in gone) for n in names], edges, releases)


# The gate (SPEC-002-R13's first scenario), in miniature.
GATE = graph_of(
    [("cart-api", "pricing-svc"), ("cart-api", "catalog-svc"), ("pricing-svc", "ledger-svc")],
    [
        rel("catalog-svc", "2.5.0", "released"),
        rel("ledger-svc", "4.2.0", "released"),
        rel("ledger-svc", "4.3.0"),
        rel("pricing-svc", "1.7.0", "released"),
        rel("pricing-svc", "1.8.0", "scoped", [("ledger-svc", ">=4.1.0")]),
        rel("cart-api", "2.3.0", needs=[("pricing-svc", ">=1.8.0"), ("catalog-svc", ">=2.5.0")]),
    ],
)


def labels(steps: Iterable[Step]) -> list[str]:
    return [step.release.label for step in steps]


def test_upstream_and_downstream_are_transitive() -> None:
    assert upstream(GATE, "cart-api") == ["catalog-svc", "ledger-svc", "pricing-svc"]
    assert downstream(GATE, "ledger-svc") == ["cart-api", "pricing-svc"]
    assert upstream(GATE, "ledger-svc") == []


def test_a_diamond_of_edges_lists_each_component_once() -> None:
    g = graph_of([("a", "c"), ("a", "d"), ("c", "b"), ("d", "b")], [])
    assert upstream(g, "a") == ["b", "c", "d"]
    assert downstream(g, "b") == ["a", "c", "d"]


def test_an_unknown_component_is_named() -> None:
    with pytest.raises(UnknownName, match="no component named 'nope'"):
        upstream(GATE, "nope")


def test_prod_version_is_the_highest_released() -> None:
    g = graph_of([], [rel("a", "1.0.0", "released"), rel("a", "1.2.0", "released"),
                      rel("a", "1.3.0", "rolled_back"), rel("a", "1.4.0", "cancelled"),
                      rel("a", "1.5.0", "deploying"), rel("b", "1.0.0")])
    assert prod_version(g, "a") == "1.2.0"
    assert prod_version(g, "b") is None


def test_the_gate() -> None:
    answer = must_ship_before(GATE, "cart-api", "2.3")
    assert labels(answer.steps) == ["pricing-svc 1.8.0"]
    assert answer.steps[0].prod == "1.7.0"
    assert answer.steps[0].needed_by == "cart-api 2.3.0"
    assert [(s.need.component, s.prod) for s in answer.satisfied] == [
        ("catalog-svc", "2.5.0"), ("ledger-svc", "4.2.0")]
    assert answer.blockers == ()


def test_a_chain_comes_upstream_first_with_ties_in_name_order() -> None:
    g = graph_of([], [
        rel("pricing-svc", "1.8.0"),
        rel("payments-gw", "3.2.1"),
        rel("cart-api", "2.3.0", needs=[("pricing-svc", ">=1.8.0")]),
        rel("checkout-svc", "3.0.0", needs=[("cart-api", ">=2.3.0"), ("payments-gw", ">=3.2.0")]),
    ])
    answer = must_ship_before(g, "checkout-svc", "3.0.0")
    assert labels(answer.steps) == ["payments-gw 3.2.1", "pricing-svc 1.8.0", "cart-api 2.3.0"]


def test_a_diamond_of_needs_lists_each_release_once() -> None:
    g = graph_of([], [
        rel("b", "1.0.0"),
        rel("c", "1.0.0", needs=[("b", ">=1.0.0")]),
        rel("d", "1.0.0", needs=[("b", ">=1.0.0")]),
        rel("a", "1.0.0", needs=[("c", ">=1.0.0"), ("d", ">=1.0.0")]),
    ])
    assert labels(must_ship_before(g, "a", "1.0.0").steps) == ["b 1.0.0", "c 1.0.0", "d 1.0.0"]


def test_the_lowest_satisfying_release_in_flight_is_chosen() -> None:
    g = graph_of([], [rel("b", "1.9.0"), rel("b", "1.8.0"), rel("b", "2.0.0", "cancelled"),
                      rel("a", "1.0.0", needs=[("b", ">=1.8.0")])])
    assert labels(must_ship_before(g, "a", "1.0.0").steps) == ["b 1.8.0"]


def test_a_cancelled_or_rolled_back_release_is_never_a_step() -> None:
    g = graph_of([], [rel("b", "1.8.0", "cancelled"), rel("b", "1.9.0", "rolled_back"),
                      rel("b", "2.0.0"), rel("a", "1.0.0", needs=[("b", ">=1.8.0")])])
    assert labels(must_ship_before(g, "a", "1.0.0").steps) == ["b 2.0.0"]


@pytest.mark.parametrize("state", sorted(set(STATES) - NOT_IN_FLIGHT))
def test_a_release_in_any_in_flight_state_can_be_a_step(state: str) -> None:
    g = graph_of([], [rel("b", "1.8.0", state), rel("a", "1.0.0", needs=[("b", ">=1.8.0")])])
    assert labels(must_ship_before(g, "a", "1.0.0").steps) == ["b 1.8.0"]


def test_a_need_nothing_meets_is_a_blocker() -> None:
    g = graph_of([], [rel("b", "2.0.0", "released"), rel("b", "3.0.0", "rolled_back"),
                      rel("a", "1.0.0", needs=[("b", ">=3.0.0")])])
    answer = must_ship_before(g, "a", "1.0.0")
    assert answer.steps == ()
    assert [(b.need.component, b.reason) for b in answer.blockers] == [
        ("b", "no release satisfies >=3.0.0 (prod runs 2.0.0)")]


def test_a_blocker_says_when_nothing_is_in_prod() -> None:
    g = graph_of([], [rel("a", "1.0.0", needs=[("b", ">=1.0.0")]), rel("b", "0.5.0")])
    assert [b.reason for b in must_ship_before(g, "a", "1.0.0").blockers] == [
        "no release satisfies >=1.0.0 (prod runs nothing)"]


def test_prod_above_the_range_blocks_and_a_lower_released_version_never_counts() -> None:
    g = graph_of([], [rel("b", "1.5.0", "released"), rel("b", "3.0.0", "released"),
                      rel("a", "1.0.0", needs=[("b", "<2")])])
    answer = must_ship_before(g, "a", "1.0.0")
    assert answer.steps == () and answer.satisfied == ()
    assert [b.reason for b in answer.blockers] == ["no release satisfies <2 (prod runs 3.0.0)"]


def test_a_need_on_a_retired_component_is_a_blocker() -> None:
    g = graph_of([], [rel("b", "2.0.0", "released"), rel("a", "1.0.0", needs=[("b", ">=1.0.0")])],
                 retired=["b"])
    assert [b.reason for b in must_ship_before(g, "a", "1.0.0").blockers] == ["b is retired"]


LOOP = [
    rel("t", "1.0.0", needs=[("a", ">=1.0.0")]),
    rel("a", "1.0.0", needs=[("b", ">=1.0.0")]),
    rel("b", "1.0.0", needs=[("c", ">=1.0.0")]),
    rel("c", "1.0.0", needs=[("a", ">=1.0.0")]),
]
LOOP_MESSAGE = "the needs form a loop: a 1.0.0 → b 1.0.0 → c 1.0.0 → a 1.0.0"


def test_a_loop_reads_as_who_needs_whom_and_leaves_out_its_tail() -> None:
    g = graph_of([], LOOP)
    with pytest.raises(GraphError) as caught:
        must_ship_before(g, "t", "1.0.0")
    assert str(caught.value) == LOOP_MESSAGE
    with pytest.raises(GraphError) as again:
        release_order(g)
    assert str(again.value) == LOOP_MESSAGE


def test_release_order_puts_every_release_after_what_it_needs() -> None:
    order = [r.label for r in release_order(GATE)]
    assert order == ["ledger-svc 4.3.0", "pricing-svc 1.8.0", "cart-api 2.3.0"]


def test_ties_sort_by_version_not_by_label_text() -> None:
    g = graph_of([], [rel("x", "1.10.0"), rel("x", "1.9.0"), rel("x", "1.2.0")])
    assert [r.label for r in release_order(g)] == ["x 1.2.0", "x 1.9.0", "x 1.10.0"]


def test_must_ship_before_lists_ties_lowest_version_first() -> None:
    g = graph_of([], [
        rel("b", "1.10.0"), rel("b", "1.9.0"),
        rel("c", "1.0.0", needs=[("b", ">=1.10.0")]),
        rel("d", "1.0.0", needs=[("b", "==1.9.0")]),
        rel("a", "1.0.0", needs=[("c", ">=1.0.0"), ("d", ">=1.0.0")]),
    ])
    steps = labels(must_ship_before(g, "a", "1.0.0").steps)
    assert steps.index("b 1.9.0") < steps.index("b 1.10.0")
    assert steps[:2] == ["b 1.9.0", "b 1.10.0"]


def test_versions_and_ranges() -> None:
    assert parse_version("2.3") == "2.3.0"
    assert parse_version("2.3.1") == "2.3.1"
    for bad in ("v2", "2", "2.3.1.4", "", "٢.٣"):
        with pytest.raises(ValueError):
            parse_version(bad)
    assert parse_range(">=1.8.0,<2")
    assert parse_range(">=1.8.0, <2.0")


@pytest.mark.parametrize("bad", [
    "~=1.0", "==1.*", "===1.0", "", " ", "soon",
    ">=1!2.0", ">=1.0.0rc1", "==1.0.0.dev1", "==1.0+local", "==1.0.post1",
    ">=1.0,", "==1.0.0,,", ",>=1.0", ">=1.0.0.0",
])
def test_a_range_outside_the_plain_operators_is_refused(bad: str) -> None:
    with pytest.raises(ValueError, match="not a version range"):
        parse_range(bad)


# make_graph: a Graph that builds is well-formed, and canonical.


def test_the_same_facts_in_another_order_build_an_equal_graph() -> None:
    windows = [Window("w1", "freeze", date(2026, 12, 20), date(2026, 12, 27)),
               Window("w1", "blackout", date(2026, 12, 20), date(2026, 12, 27)),
               Window("w1", "freeze", date(2026, 12, 1), date(2026, 12, 2))]

    def build(needs: list[tuple[str, str]], wins: list[Window]) -> Graph:
        return make_graph([Component("a", "t"), Component("b", "t")], [],
                          [rel("a", "1.0.0", needs=needs), rel("b", "1.0.0")], wins)

    one = build([("b", ">=1"), ("b", "<3")], windows)
    two = build([("b", "<3"), ("b", ">=1")], list(reversed(windows)))
    assert one == two


def _built(**changes: object) -> Graph:
    facts: dict[str, object] = {
        "components": [Component("a", "t"), Component("b", "t")],
        "edges": [("a", "b")],
        "releases": [rel("a", "1.0.0", needs=[("b", ">=1.0.0")])],
    }
    facts.update(changes)
    return make_graph(**facts)  # type: ignore[arg-type]


@pytest.mark.parametrize(("changes", "name"), [
    ({"edges": [("zzz", "b")]}, "zzz"),
    ({"edges": [("a", "yyy")]}, "yyy"),
    ({"releases": [rel("xxx", "1.0.0")]}, "xxx"),
    ({"releases": [rel("a", "1.0.0", needs=[("www", ">=1.0.0")])]}, "www"),
])
def test_make_graph_names_a_component_it_does_not_hold(changes: dict[str, object],
                                                      name: str) -> None:
    with pytest.raises(UnknownName, match=name):
        _built(**changes)


def test_make_graph_refuses_a_need_whose_range_does_not_parse() -> None:
    with pytest.raises(ValueError, match="not a version range"):
        _built(releases=[rel("a", "1.0.0", needs=[("b", "soon")])])


def test_make_graph_normalises_versions() -> None:
    g = _built(releases=[rel("a", "1.0")])
    assert g.releases[0].version == "1.0.0"
    assert release(g, "a", "1.0").label == "a 1.0.0"


def test_make_graph_refuses_a_version_that_is_not_one() -> None:
    with pytest.raises(ValueError, match="not a version"):
        _built(releases=[rel("a", "soon")])


def test_make_graph_refuses_two_releases_with_one_label() -> None:
    with pytest.raises(ValueError, match="a 1.0.0"):
        _built(releases=[rel("a", "1.0"), rel("a", "1.0.0")])
