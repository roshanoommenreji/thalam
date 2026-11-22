"""Inline SVG diagrams for the dashboard, drawn in Python with no library.

Three shapes:
- `graph`: boxes on a grid joined by labelled arrows (architecture, Azure, DevOps);
- `sequence`: one column per participant and one arrow per step, top to bottom (flows);
- the release life cycle, which is a `graph` laid out in one row.

Every colour comes from a CSS class the page's stylesheet defines, so a diagram follows the light
and dark themes. Every text is escaped. Arrowhead ids are prefixed with the diagram's `uid`, so
several diagrams can share one page.
"""

from __future__ import annotations

import html
import math
from dataclasses import dataclass

EDGE_KINDS = ("data", "control", "write")
STEP_KINDS = ("call", "return", "write", "self")


def _e(text: object) -> str:
    return html.escape(str(text), quote=True)


def wrap(text: str, width: int) -> list[str]:
    """Greedy word wrap; a word longer than `width` keeps its own line."""
    lines: list[str] = []
    for word in text.split():
        if lines and len(lines[-1]) + 1 + len(word) <= width:
            lines[-1] += " " + word
        else:
            lines.append(word)
    return lines or [""]


@dataclass(frozen=True)
class Node:
    id: str
    label: str
    col: float
    row: float
    sub: str = ""
    kind: str = ""
    state: str = ""  # built | now | planned | external | missing | parked | up | unknown
    badge: str = ""  # a short mark in the top-right corner, such as the building phase
    href: str = ""
    title: str = ""  # the tooltip


@dataclass(frozen=True)
class Edge:
    src: str
    dst: str
    label: str = ""
    kind: str = "data"
    at: float = 0.5  # where along the arrow its label sits, 0 (start) to 1 (end)


def _clip(cx: float, cy: float, dx: float, dy: float, hw: float, hh: float) -> tuple[float, float]:
    """Where a ray from a box's centre in direction (dx, dy) leaves the box."""
    if dx == 0 and dy == 0:
        return cx, cy
    t = min(hw / abs(dx) if dx else math.inf, hh / abs(dy) if dy else math.inf)
    return cx + dx * t, cy + dy * t


def _markers(uid: str, kinds: tuple[str, ...]) -> str:
    return "<defs>" + "".join(
        f'<marker id="{uid}-{k}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
        f'markerHeight="7" orient="auto-start-reverse"><path class="ah {k}" '
        'd="M0,0 L10,5 L0,10 z"/></marker>' for k in kinds) + "</defs>"


def graph(nodes: list[Node], edges: list[Edge], *, uid: str, aria: str, colw: float = 172,
          rowh: float = 118, w: float = 148, h: float = 58, pad: float = 26,
          wrap_at: int = 19) -> str:
    """Boxes at (col, row) on a grid, joined by straight labelled arrows from edge to edge."""
    pos = {n.id: (pad + n.col * colw + w / 2, pad + n.row * rowh + h / 2) for n in nodes}
    width = max(x for x, _ in pos.values()) + w / 2 + pad
    height = max(y for _, y in pos.values()) + h / 2 + pad
    out = [f'<svg class="diagram" viewBox="0 0 {width:.0f} {height:.0f}" '
           f'style="min-width:{width * 0.7:.0f}px" role="img" aria-label="{_e(aria)}">',
           _markers(uid, EDGE_KINDS)]
    labels: list[str] = []
    for e in edges:
        (x1, y1), (x2, y2) = pos[e.src], pos[e.dst]
        sx, sy = _clip(x1, y1, x2 - x1, y2 - y1, w / 2 + 2, h / 2 + 2)
        ex, ey = _clip(x2, y2, x1 - x2, y1 - y2, w / 2 + 5, h / 2 + 5)
        kind = e.kind if e.kind in EDGE_KINDS else "data"
        out.append(f'<line class="edge {kind}" x1="{sx:.1f}" y1="{sy:.1f}" x2="{ex:.1f}" '
                   f'y2="{ey:.1f}" marker-end="url(#{uid}-{kind})"/>')
        if e.label:
            lx, ly = sx + (ex - sx) * e.at, sy + (ey - sy) * e.at
            labels.append(f'<text class="elabel" x="{lx:.1f}" y="{ly + 4:.1f}" '
                          f'text-anchor="middle">{_e(e.label)}</text>')
    out += labels  # above every line, so a crossing line never hides a label
    for n in nodes:
        cx, cy = pos[n.id]
        lines = wrap(n.label, wrap_at)[:2]
        block = 15 * len(lines) + (13 if n.sub else 0)
        y = cy - block / 2 + 11
        parts = [f"<title>{_e(n.title or n.label)}</title>",
                 f'<rect x="{cx - w / 2:.1f}" y="{cy - h / 2:.1f}" width="{w:.0f}" '
                 f'height="{h:.0f}" rx="9"/>']
        for line in lines:
            parts.append(f'<text class="nlabel" x="{cx:.1f}" y="{y:.1f}" text-anchor="middle">'
                         f"{_e(line)}</text>")
            y += 15
        if n.sub:
            parts.append(f'<text class="nsub" x="{cx:.1f}" y="{y - 1:.1f}" text-anchor="middle">'
                         f"{_e(n.sub)}</text>")
        if n.badge:
            bx, by = cx + w / 2 - 2, cy - h / 2 + 2
            parts.append(f'<circle class="nbadge" cx="{bx:.1f}" cy="{by:.1f}" r="9"/>'
                         f'<text class="nbadge-t" x="{bx:.1f}" y="{by + 3.5:.1f}" '
                         f'text-anchor="middle">{_e(n.badge)}</text>')
        group = f'<g class="node {_e(n.kind)} {_e(n.state)}">{"".join(parts)}</g>'
        out.append(f'<a href="#{_e(n.href)}">{group}</a>' if n.href else group)
    out.append("</svg>")
    return "".join(out)


@dataclass(frozen=True)
class Step:
    src: str
    dst: str
    label: str
    kind: str = "call"


def sequence(lanes: list[tuple[str, str]], steps: list[Step], *, uid: str, aria: str,
             colw: float = 124, head: float = 40, steph: float = 40, pad: float = 14) -> str:
    """Participants across the top with dashed lifelines; numbered arrows down the page."""
    index = {lane: i for i, (lane, _) in enumerate(lanes)}
    width = pad * 2 + len(lanes) * colw
    top = pad + head + 16
    height = top + len(steps) * steph + pad

    def x(lane: str) -> float:
        return pad + index[lane] * colw + colw / 2

    # Capped and centred, so a flow with few lanes is not blown up to the card's full width.
    out = [f'<svg class="diagram seq" viewBox="0 0 {width:.0f} {height:.0f}" '
           f'style="min-width:{width * 0.72:.0f}px;max-width:{width * 1.25:.0f}px;margin:0 auto" '
           f'role="img" aria-label="{_e(aria)}">',
           _markers(uid, ("call", "return", "write"))]
    for lane, label in lanes:
        cx = x(lane)
        out.append(f'<line class="lifeline" x1="{cx:.1f}" y1="{pad + head:.1f}" x2="{cx:.1f}" '
                   f'y2="{height - pad / 2:.1f}"/>')
        out.append(f'<rect class="lane" x="{cx - colw / 2 + 6:.1f}" y="{pad:.1f}" '
                   f'width="{colw - 12:.0f}" height="{head:.0f}" rx="8"/>')
        lines = wrap(label, 16)[:2]
        y = pad + head / 2 + 4 - 7 * (len(lines) - 1)
        for line in lines:
            out.append(f'<text class="lanelabel" x="{cx:.1f}" y="{y:.1f}" text-anchor="middle">'
                       f"{_e(line)}</text>")
            y += 14
    for i, s in enumerate(steps):
        y = top + i * steph + steph / 2 + 6
        text = f"{i + 1} · {s.label}"
        half = len(text) * 3.3 + 4
        x1, x2 = x(s.src), x(s.dst)
        if s.kind == "self" or s.src == s.dst:
            left = index[s.src] == len(lanes) - 1
            d = -1 if left else 1
            out.append(f'<path class="step self" d="M{x1:.1f},{y - 8:.1f} h{22 * d} v14 '
                       f'h{-18 * d}" marker-end="url(#{uid}-call)"/>')
            tx = x1 + 30 * d
            out.append(f'<text class="slabel" x="{tx:.1f}" y="{y + 2:.1f}" '
                       f'text-anchor="{"end" if left else "start"}">{_e(text)}</text>')
            continue
        kind = s.kind if s.kind in ("call", "return", "write") else "call"
        d = 1 if x2 > x1 else -1
        out.append(f'<line class="step {kind}" x1="{x1 + 3 * d:.1f}" y1="{y:.1f}" '
                   f'x2="{x2 - 5 * d:.1f}" y2="{y:.1f}" marker-end="url(#{uid}-{kind})"/>')
        mid = min(max((x1 + x2) / 2, pad + half), width - pad - half)
        out.append(f'<text class="slabel" x="{mid:.1f}" y="{y - 7:.1f}" '
                   f'text-anchor="middle">{_e(text)}</text>')
    out.append("</svg>")
    return "".join(out)


def chain(states: list[str], ends: list[str], *, uid: str, aria: str) -> str:
    """A life cycle: states in one row, the last one splitting into its possible ends."""
    nodes = [Node(f"s{i}", s, col=i, row=0.5, kind="state") for i, s in enumerate(states)]
    last = len(states)
    nodes += [Node(f"e{j}", s, col=last, row=j, kind="state end") for j, s in enumerate(ends)]
    edges = [Edge(f"s{i}", f"s{i + 1}") for i in range(len(states) - 1)]
    edges += [Edge(f"s{last - 1}", f"e{j}") for j in range(len(ends))]
    return graph(nodes, edges, uid=uid, aria=aria, colw=128, rowh=56, w=108, h=40, pad=10,
                 wrap_at=14)
