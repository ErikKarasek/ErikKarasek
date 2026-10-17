#!/usr/bin/env python3
"""
Render data/repos.json as a night skyline where every public repo is a building:
height from the size of the repo, lit windows from the commits of the last day,
scaffolding for an open pull request, boarded windows for anything untouched for
months, an antenna on the repo that currently leads the CV, a crane on anything
built this month.

Standard library only. Run daily by the update-profile workflow, after
fetch_repos.py.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from theme import BLUE, FRAME, GOLD, INK, MUTED, PAD, RED, TEXT, TITLEBAR_H, window  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
IN = os.path.join(ROOT, "data", "repos.json")
OUT = os.path.join(ROOT, "assets", "city.svg")

FEATURED = os.environ.get("CITY_FEATURED", "wisp")  # gets the antenna

MIN_W = 865            # matches the contribution graph above it in the README
MAX_BUILDING_W = 72
GAP = 9
MIN_H, MAX_H = 54, 240
SKY_H = 26             # breathing room above the tallest roof
STREET_H = 66          # room under the ground line for the rotated labels
LABEL_RUN = 4.6        # horizontal px each label character eats at 34 degrees
FOOTER_H = 58

WALL = "#1b2430"
WALL_EDGE = "#39465a"
WALL_DEAD = "#39424e"
ROOF = "#2b3644"
WINDOW_OFF = "#222a35"
WINDOW_DEAD = "#232b36"
BOARD = "#4a3a2a"
DOOR = "#33404f"
STREET = "#10151d"
KERB = "#2a3340"


def esc(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def plural(n, one, few):
    return f"{n} {one if n == 1 else few}"


def height_of(kb, tallest):
    """Square-ish scale, so a monorepo towers without flattening the small ones."""
    if tallest <= 0:
        return MIN_H
    return round(MIN_H + (MAX_H - MIN_H) * (kb / tallest) ** 0.62)


def stars(width, top, bottom, parts):
    for i in range(54):
        x = (i * 97) % (width - 2 * PAD) + PAD
        y = top + 8 + (i * 53) % max(1, bottom - top - 16)
        r = 1.4 if i % 7 == 0 else 0.9
        parts.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="#9fb0c0" '
                     f'opacity="{0.18 + (i % 5) * 0.12:.2f}"/>')


def windows(x, y, w, h, commits, dead, parts, seed):
    """Lit windows fill from the ground up, so the count stays readable."""
    cols = max(2, (w - 12) // 12)
    rows = max(2, (h - 16) // 14)
    left = commits
    for row in reversed(range(rows)):
        for col in range(cols):
            wx = x + 7 + col * 12
            wy = y + 9 + row * 14
            if dead:
                parts.append(f'<rect x="{wx}" y="{wy}" width="8" height="9" fill="{WINDOW_DEAD}"/>')
                parts.append(f'<line x1="{wx}" y1="{wy + 9}" x2="{wx + 8}" y2="{wy}" '
                             f'stroke="{BOARD}" stroke-width="1.6"/>')
                continue
            if left > 0:
                left -= 1
                delay = ((row + col + seed) % 7) * 0.45
                parts.append(f'<rect class="lit" x="{wx}" y="{wy}" width="8" height="9" '
                             f'fill="{GOLD}" style="animation-delay:{delay:.2f}s"/>')
            else:
                parts.append(f'<rect x="{wx}" y="{wy}" width="8" height="9" fill="{WINDOW_OFF}"/>')
    return commits - left  # how many actually fit


def scaffolding(x, y, w, h, parts):
    """Poles and planks over the lower floors, where real scaffolding starts."""
    top = y + round(h * 0.42)
    bottom = y + h - 2
    parts.append(f'<g stroke="{BLUE}" stroke-opacity="0.6" stroke-width="1.1" fill="none">')
    poles = max(3, w // 18 + 1)
    for pole in range(poles):
        px = x - 3 + (w + 6) * pole // (poles - 1)
        parts.append(f'<line x1="{px}" y1="{top}" x2="{px}" y2="{bottom}"/>')
    decks = max(3, (bottom - top) // 15)
    for level in range(decks + 1):
        ly = top + (bottom - top) * level // decks
        parts.append(f'<line x1="{x - 3}" y1="{ly}" x2="{x + w + 3}" y2="{ly}"/>')
    parts.append("</g>")


def antenna(cx, roof, parts):
    parts.append(f'<line x1="{cx}" y1="{roof - 3}" x2="{cx}" y2="{roof - 34}" '
                 f'stroke="#55626f" stroke-width="2"/>')
    parts.append(f'<circle class="beacon" cx="{cx}" cy="{roof - 36}" r="3.4" fill="{RED}"/>')


def crane(x, w, roof, parts):
    """A small jib standing on the roof, not a gallows floating beside it."""
    mast = x + w - 11
    top = roof - 34
    parts.append(f'<g stroke="{GOLD}" stroke-opacity="0.7" stroke-width="1.4" fill="none">')
    parts.append(f'<line x1="{mast}" y1="{roof - 3}" x2="{mast}" y2="{top}"/>')
    parts.append(f'<line x1="{mast - 15}" y1="{top + 4}" x2="{mast + 9}" y2="{top + 4}"/>')
    parts.append(f'<line x1="{mast - 11}" y1="{top + 4}" x2="{mast - 11}" y2="{top + 13}"/>')
    parts.append("</g>")


def street(width, ground, parts):
    parts.append(f'<rect x="0" y="{ground}" width="{width}" height="{STREET_H}" fill="{STREET}"/>')
    parts.append(f'<line x1="0" y1="{ground}" x2="{width}" y2="{ground}" stroke="{FRAME}"/>')
    for x in range(PAD, width - PAD, 28):
        parts.append(f'<rect x="{x}" y="{ground + 30}" width="13" height="2" fill="{KERB}"/>')


def render(data):
    repos = data["repos"]
    if not repos:
        sys.exit("no repos in data/repos.json")

    # Sorted by size, then folded so the tallest sits in the middle: a skyline,
    # not a descending bar chart. Height still means size either way.
    left, right = [], []
    for i, r in enumerate(repos):
        (left if i % 2 == 0 else right).append(r)
    repos = left[::-1] + right

    count = len(repos)
    inner = MIN_W - 2 * PAD
    bw = min(MAX_BUILDING_W, (inner - GAP * (count - 1)) // count)
    if bw < 26:  # too many repos for one row: widen the window instead
        bw = 26
    span = count * bw + (count - 1) * GAP
    x0 = max(PAD, (MIN_W - span) // 2)
    # Labels run down and to the right at 34 degrees, so the rightmost ones need
    # room past the last roof or they get clipped.
    tail = max(x0 + i * (bw + GAP) + bw // 2 + len(r["name"]) * LABEL_RUN
               for i, r in enumerate(repos))
    width = max(MIN_W, span + 2 * PAD, round(tail) + PAD)

    tallest = max(r["kb"] for r in repos)
    ground = TITLEBAR_H + SKY_H + MAX_H
    height = ground + STREET_H + FOOTER_H

    lit_total = 0
    parts = window(width, height, f"erik@github: ~$ ./city.sh --window {data['window_hours']}h")
    parts.append(
        # Only looping animations, and none of them fades anything in. An entry
        # animation would need animation-fill-mode:both, whose backwards fill
        # hides the whole skyline anywhere animations do not run: a thumbnail,
        # a social preview, a PDF, a reader in reduced motion.
        "<style>"
        "@keyframes flick{0%,94%{opacity:1}95%,100%{opacity:.42}}"
        "@keyframes blink{0%,70%{opacity:1}71%,100%{opacity:.2}}"
        ".lit{animation:flick 4.5s steps(1,end) infinite}"
        ".beacon{animation:blink 1.7s steps(1,end) infinite}"
        "@media(prefers-reduced-motion:reduce){.lit,.beacon{animation:none}}"
        "</style>")

    stars(width, TITLEBAR_H, ground - MAX_H + 40, parts)

    if data["commits_in_window"]:
        parts.append(f'<defs><linearGradient id="glow" x1="0" y1="0" x2="0" y2="1">'
                     f'<stop offset="0" stop-color="{RED}" stop-opacity="0.14"/>'
                     f'<stop offset="1" stop-color="{RED}" stop-opacity="0"/>'
                     f'</linearGradient></defs>')
        parts.append(f'<rect x="0" y="{ground - MAX_H - 10}" width="{width}" '
                     f'height="{MAX_H + 10}" fill="url(#glow)"/>')

    for i, r in enumerate(repos):
        x = x0 + i * (bw + GAP)
        h = height_of(r["kb"], tallest)
        y = ground - h
        dead = r["stale"]

        parts.append("<g>")
        parts.append(f'<title>{esc(r["name"])}: {r["kb"]:,} kB, '
                     f'{plural(r["commits"], "commit", "commits")} in the last '
                     f'{data["window_hours"]} h, last push {r["pushed"][:10]}</title>')
        parts.append(f'<rect x="{x}" y="{y}" width="{bw}" height="{h}" fill="{WALL}" '
                     f'stroke="{WALL_DEAD if dead else WALL_EDGE}"/>')
        parts.append(f'<rect x="{x - 2}" y="{y - 3}" width="{bw + 4}" height="3" fill="{ROOF}"/>')

        # A repo that moved always gets one window, even when GitHub never said
        # how many commits were behind it (see fetch_repos.activity).
        lit = r["commits"] or (1 if r.get("events") else 0)
        lit_total += windows(x, y, bw, h, lit, dead, parts, i)

        parts.append(f'<rect x="{x + bw // 2 - 4}" y="{ground - 11}" width="9" height="11" '
                     f'fill="{WALL_DEAD if dead else DOOR}"/>')

        if r["open_prs"] and not dead:
            scaffolding(x, y, bw, h, parts)
        if r["name"].lower() == FEATURED.lower():
            antenna(x + bw // 2, y, parts)
        if r["new"]:
            crane(x, bw, y, parts)
        parts.append("</g>")

    street(width, ground, parts)

    for i, r in enumerate(repos):
        cx = x0 + i * (bw + GAP) + bw // 2
        fill = MUTED if r["stale"] else TEXT
        parts.append(f'<text transform="translate({cx},{ground + 15}) rotate(34)" '
                     f'fill="{fill}" font-size="10">{esc(r["name"])}</text>')

    sep = ground + STREET_H
    parts.append(f'<line x1="0" y1="{sep}" x2="{width}" y2="{sep}" stroke="{FRAME}"/>')

    tall = max(repos, key=lambda r: r["kb"])  # repos is folded, not sorted, by now
    asleep = sum(1 for r in repos if r["stale"])
    active = data.get("active_repos", sum(1 for r in repos if r.get("events")))
    commits = data["commits_in_window"]
    y = sep + 24

    # The headline follows whichever number is honest today: GitHub counts
    # commits for a plain push but not for a first push to a new branch.
    if commits:
        head = (f'<tspan fill="{RED}" font-weight="700">{commits}</tspan>'
                f' commit{"" if commits == 1 else "s"} in the last {data["window_hours"]} hours'
                f', across <tspan fill="{INK}">{plural(active, "repo", "repos")}</tspan>')
    elif active:
        head = (f'<tspan fill="{RED}" font-weight="700">{plural(active, "repo", "repos")}</tspan>'
                f' moved in the last {data["window_hours"]} hours')
    else:
        head = f'nothing pushed in the last {data["window_hours"]} hours; the city sleeps'
    parts.append(f'<text x="{PAD}" y="{y}" font-size="13" fill="{MUTED}">{head}'
                 f' &#183; <tspan fill="{INK}">{len(repos)}</tspan> public repos</text>')
    parts.append(f'<text x="{width - PAD}" y="{y}" font-size="12" fill="{MUTED}" '
                 f'text-anchor="end">tallest <tspan fill="{BLUE}" font-weight="700">'
                 f'{esc(tall["name"])}</tspan> at {tall["kb"]:,} kB</text>')
    y += 22
    parts.append(f'<text x="{PAD}" y="{y}" font-size="11" fill="{MUTED}">'
                 f'<tspan fill="{GOLD}">&#9632;</tspan> lit window = a commit in public'
                 f'   <tspan fill="{BLUE}">&#9647;</tspan> scaffolding = open PR'
                 f'   <tspan fill="{RED}">&#9679;</tspan> antenna = leads the CV'
                 + (f'   boarded up = {plural(asleep, "repo", "repos")} quiet for months'
                    if asleep else '')
                 + '</text>')
    if lit_total < commits:
        parts.append(f'<text x="{width - PAD}" y="{y}" font-size="11" fill="{MUTED}" '
                     f'text-anchor="end">some buildings ran out of windows</text>')
    parts.append("</svg>")
    return "".join(parts)


if __name__ == "__main__":
    with open(IN) as f:
        svg = render(json.load(f))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        f.write(svg)
    print(f"wrote {OUT} ({len(svg):,} bytes)")
