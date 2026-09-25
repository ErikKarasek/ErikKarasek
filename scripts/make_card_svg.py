"""
A neofetch-style info panel that fades in line by line and then holds.
Sized to sit beside the ASCII portrait at the same height.

Edit INFO below and rerun; no dependencies:

    python scripts/make_card_svg.py [height] [out.svg]
"""
import html
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from theme import BLUE, FRAME, GOLD, INK, PAD, RED, TEXT, TITLEBAR_H, window  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
HEIGHT = int(sys.argv[1]) if len(sys.argv) > 1 else 660
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "assets", "card.svg")

USER = "erik@github"
# (key, value); a None key starts a new section with the value as its heading.
INFO = [
    ("Name", "Erik Karásek"),
    ("Role", "Full-stack developer"),
    ("Day job", "Analyst / Tester @ Unicorn"),
    ("Country", "Czech Republic"),
    ("Web", "erikkarasek.cz"),
    (None, "stack"),
    ("Languages", "TypeScript, Python, Rust"),
    ("Frontend", "React, Vite, GSAP"),
    ("Mobile", "React Native, Expo"),
    ("Desktop", "Tauri"),
    ("Backend", "Supabase, PostgreSQL"),
    ("AI", "agents, tool calling"),
    ("Cloud", "Cloudflare Workers"),
    (None, "building"),
    ("Nexus Grind", "desktop + mobile app"),
    ("Job Tracker", "AI job-hunt board"),
    ("Portfolio", "Spider-Man themed"),
]

FS = 14
LINE_H = 24
KEY_W = 13  # characters reserved for the key column
CHAR_W = FS * 0.6
W = 440
FADE = 0.35
STEP = 0.12
START = 0.3

parts = window(W, HEIGHT, "erik@github: ~$ neofetch")
parts.append("<style>@keyframes in{from{opacity:0;transform:translateX(-6px)}"
             "to{opacity:1;transform:none}}"
             f".l{{opacity:0;animation:in {FADE}s ease-out both}}</style>")

y = TITLEBAR_H + PAD + FS
n = 0


def line(content):
    global y, n
    parts.append(f'<g class="l" style="animation-delay:{START + n * STEP:.2f}s">{content}</g>')
    y += LINE_H
    n += 1


line(f'<text x="{PAD}" y="{y}" font-size="{FS + 1}" font-weight="700">'
     f'<tspan fill="{RED}">erik</tspan><tspan fill="{TEXT}">@</tspan>'
     f'<tspan fill="{BLUE}">github</tspan></text>')
line(f'<text x="{PAD}" y="{y - 8}" font-size="{FS}" fill="{FRAME}">{"─" * len(USER)}</text>')
y -= 8

for key, value in INFO:
    if key is None:
        y += 6
        line(f'<text x="{PAD}" y="{y}" font-size="{FS - 2}" fill="{GOLD}">'
             f'── {html.escape(value)} {"─" * (40 - len(value))}</text>')
        continue
    line(f'<text x="{PAD}" y="{y}" font-size="{FS}">'
         f'<tspan fill="{RED}" font-weight="700">{html.escape(key)}</tspan>'
         f'<tspan x="{PAD + KEY_W * CHAR_W}" fill="{INK}">{html.escape(value)}</tspan></text>')

# neofetch's colour blocks, pinned to the bottom of the panel
block_y = HEIGHT - PAD - 18
blocks = ["#30363d", RED, "#27c93f", GOLD, BLUE, "#bc8cff", "#39c5cf", INK]
row = "".join(f'<rect x="{PAD + i * 26}" y="{block_y}" width="24" height="18" rx="2" fill="{c}"/>'
              for i, c in enumerate(blocks))
parts.append(f'<g class="l" style="animation-delay:{START + n * STEP:.2f}s">{row}</g>')
parts.append("</svg>")

if y > block_y:
    sys.exit(f"INFO does not fit: text ends at y={y}, blocks start at {block_y}")
with open(OUT, "w") as f:
    f.write("".join(parts))
print(f"wrote {OUT}: {W}x{HEIGHT}, {n} lines")
