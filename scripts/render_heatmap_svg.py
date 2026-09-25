#!/usr/bin/env python3
"""
Render data/contributions.json as a contribution calendar in the red Spidey
palette: 53 weeks x 7 days of rounded boxes that drop in with a diagonal
sweep once, then hold, plus a legend and a stats footer.

Standard library only. Run daily by the update-profile workflow.
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from theme import BLUE, FRAME, GOLD, MUTED, PAD, RED, TITLEBAR_H, window  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
IN = os.path.join(ROOT, "data", "contributions.json")
OUT = os.path.join(ROOT, "assets", "contributions.svg")

PALETTE = ["#161b22", "#4a1219", "#7d1a24", "#b32530", "#e23636", "#ff7a7a"]
CELL, GAP = 12, 3
STEP = CELL + GAP
LABEL_W, MONTH_H, FOOTER_H = 30, 20, 88
COL_T, ROW_T, DUR = 0.018, 0.045, 0.42


def level(count, top):
    """Scale to the busiest day so a quiet year still shows contrast."""
    if count == 0:
        return 0
    return max(1, min(5, 1 + int(4 * count / max(top, 1) + 0.5)))


def weeks(days):
    """Columns of 7 (Sunday first); None pads the first and last week."""
    first = datetime.date.fromisoformat(days[0]["date"])
    col = [None] * ((first.weekday() + 1) % 7)
    out = []
    for d in days:
        col.append(d)
        if len(col) == 7:
            out.append(col)
            col = []
    if col:
        out.append(col + [None] * (7 - len(col)))
    return out


def render(data):
    grid = weeks(data["days"])
    top = data["best_day"]["count"]
    W = PAD + LABEL_W + len(grid) * STEP + PAD
    grid_top = TITLEBAR_H + MONTH_H
    grid_left = PAD + LABEL_W
    H = grid_top + 7 * STEP + FOOTER_H + PAD

    parts = window(W, H, "erik@github: ~$ ./contributions.sh")
    parts.append("<style>@keyframes c{from{opacity:0;transform:translateY(-6px)}"
                 f"to{{opacity:1;transform:none}}}}.c{{opacity:0;animation:c {DUR}s "
                 "cubic-bezier(.2,.8,.2,1) both}</style>")

    seen = set()
    for ci, col in enumerate(grid):
        d = next(c for c in col if c)
        date = datetime.date.fromisoformat(d["date"])
        if date.day <= 7 and (date.year, date.month) not in seen and ci < len(grid) - 1:
            seen.add((date.year, date.month))
            parts.append(f'<text x="{grid_left + ci * STEP}" y="{TITLEBAR_H + 14}" '
                         f'fill="{MUTED}" font-size="10">{date.strftime("%b")}</text>')
    for ri, name in [(1, "Mon"), (3, "Wed"), (5, "Fri")]:
        parts.append(f'<text x="{PAD}" y="{grid_top + ri * STEP + CELL * 0.8:.1f}" '
                     f'fill="{MUTED}" font-size="9">{name}</text>')

    for ci, col in enumerate(grid):
        for ri, d in enumerate(col):
            if d is None:
                continue
            n = d["count"]
            parts.append(
                f'<rect class="c" x="{grid_left + ci * STEP}" y="{grid_top + ri * STEP}" '
                f'width="{CELL}" height="{CELL}" rx="2.5" fill="{PALETTE[level(n, top)]}" '
                f'style="animation-delay:{ci * COL_T + ri * ROW_T:.3f}s">'
                f'<title>{d["date"]}: {n} contribution{"" if n == 1 else "s"}</title></rect>')

    leg_y = grid_top + 7 * STEP + 6
    leg_x = W - PAD - len(PALETTE) * CELL - 34
    parts.append(f'<text x="{leg_x - 6}" y="{leg_y + 10}" fill="{MUTED}" font-size="10" '
                 'text-anchor="end">Less</text>')
    for i, c in enumerate(PALETTE):
        parts.append(f'<rect x="{leg_x + i * CELL}" y="{leg_y}" width="{CELL - 1}" '
                     f'height="{CELL - 1}" rx="2.2" fill="{c}"/>')
    parts.append(f'<text x="{leg_x + len(PALETTE) * CELL + 4}" y="{leg_y + 10}" '
                 f'fill="{MUTED}" font-size="10">More</text>')

    sep = leg_y + CELL + 14
    parts.append(f'<line x1="0" y1="{sep}" x2="{W}" y2="{sep}" stroke="{FRAME}"/>')
    cur, best, rng = data["current_streak"]["length"], data["longest_streak"]["length"], data["range"]
    day = data["best_day"]
    y = sep + 26
    parts.append(f'<text x="{PAD}" y="{y}" font-size="13" fill="{MUTED}">'
                 f'<tspan fill="{RED}" font-weight="700">{data["total"]:,}</tspan>'
                 ' contributions in the last year</text>')
    parts.append(f'<text x="{W - PAD}" y="{y}" font-size="12" fill="{MUTED}" text-anchor="end">'
                 f'{rng["start"]} &#8594; {rng["end"]}</text>')
    y += 24
    plural = lambda k: f'{k} day{"" if k == 1 else "s"}'  # noqa: E731
    parts.append(f'<text x="{PAD}" y="{y}" font-size="13" fill="{MUTED}">current streak '
                 f'<tspan fill="{BLUE}" font-weight="700">{plural(cur)}</tspan>'
                 f'  &#183;  longest <tspan fill="{BLUE}" font-weight="700">{plural(best)}</tspan></text>')
    parts.append(f'<text x="{W - PAD}" y="{y}" font-size="12" fill="{MUTED}" text-anchor="end">'
                 f'best day <tspan fill="{GOLD}" font-weight="700">{day["count"]}</tspan>'
                 f' on {day["date"]}</text>')
    parts.append("</svg>")
    return "".join(parts)


if __name__ == "__main__":
    with open(IN) as f:
        svg = render(json.load(f))
    with open(OUT, "w") as f:
        f.write(svg)
    print(f"wrote {OUT} ({len(svg):,} bytes)")
