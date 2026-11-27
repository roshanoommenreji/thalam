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
    downstream,
    make_graph,
    must_ship_before,
    parse_range,
    parse_version,
    prod_version,
    release_order,
    upstream,
)

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


def test_the_lowest_satisfying_release_in_flight_is_chosen() -> None:
    g = graph_of([], [rel("b", "1.9.0"), rel("b", "1.8.0"), rel("b", "2.0.0", "cancelled"),
                      rel("a", "1.0.0", needs=[("b", ">=1.8.0")])])
    assert labels(must_ship_before(g, "a", "1.0.0").steps) == ["b 1.8.0"]


def test_a_need_nothing_meets_is_a_blocker() -> None:
    g = graph_of([], [rel("b", "2.0.0", "released"), rel("b", "3.0.0", "rolled_back"),
                      rel("a", "1.0.0", needs=[("b", ">=3.0.0")])])
    answer = must_ship_before(g, "a", "1.0.0")
    assert answer.steps == ()
    assert [(b.need.component, b.reason) for b in answer.blockers] == [
        ("b", "no release satisfies it")]


def test_a_need_on_a_retired_component_is_a_blocker() -> None:
    g = graph_of([], [rel("b", "2.0.0", "released"), rel("a", "1.0.0", needs=[("b", ">=1.0.0")])],
                 retired=["b"])
    assert [b.reason for b in must_ship_before(g, "a", "1.0.0").blockers] == ["b is retired"]


def test_a_loop_is_an_error_that_names_every_release_in_it() -> None:
    g = graph_of([], [rel("a", "1.0.0", needs=[("b", ">=1.0.0")]),
                      rel("b", "1.0.0", needs=[("a", ">=1.0.0")])])
    with pytest.raises(GraphError) as caught:
        must_ship_before(g, "a", "1.0.0")
    assert "a 1.0.0" in str(caught.value) and "b 1.0.0" in str(caught.value)


def test_release_order_puts_every_release_after_what_it_needs() -> None:
    order = [r.label for r in release_order(GATE)]
    assert order == ["ledger-svc 4.3.0", "pricing-svc 1.8.0", "cart-api 2.3.0"]


def test_release_order_refuses_a_loop() -> None:
    g = graph_of([], [rel("a", "1.0.0", needs=[("b", ">=1.0.0")]),
                      rel("b", "1.0.0", needs=[("a", ">=1.0.0")])])
    with pytest.raises(GraphError):
        release_order(g)


def test_versions_and_ranges() -> None:
    assert parse_version("2.3") == "2.3.0"
    assert parse_version("2.3.1") == "2.3.1"
    for bad in ("v2", "2", "2.3.1.4", ""):
        with pytest.raises(ValueError):
            parse_version(bad)
    assert parse_range(">=1.8.0,<2")
    for bad in ("~=1.0", "==1.*", "===1.0", "", "soon"):
        with pytest.raises(ValueError):
            parse_range(bad)
