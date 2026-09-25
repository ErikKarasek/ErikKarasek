"""
Turn a portrait photo into a monochrome ASCII-art SVG that types itself in
row by row, like a terminal printing it, and then holds still.

GitHub strips JavaScript from READMEs but runs SMIL animation inside an SVG
loaded through <img>, which is what makes the reveal work.

Needs Pillow. Run once, locally, whenever the photo changes:

    python scripts/make_ascii_svg.py [photo] [out.svg]
    STATIC=1 python scripts/make_ascii_svg.py   # no animation, for previews
"""
import html
import os
import sys

from PIL import Image, ImageEnhance, ImageOps

sys.path.insert(0, os.path.dirname(__file__))
from theme import FRAME, INK, MUTED, PAD, RED, TITLEBAR_H, window  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "assets", "source-photo.jpg")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "assets", "portrait.svg")

COLS = 90
CELL_W = 6
CELL_H = 11
RAMP = " .`:-=+*cs#%@"  # light (sparse) -> dark (dense); the space blanks the background
GAMMA = 1.25            # >1 pushes skin tones towards the sparse end
WHITE_FLOOR = 0.86      # anything brighter than this is background

ROW_DUR = 0.09          # one row's wipe; the stagger equals it, so one cursor sweeps down

im = Image.open(SRC).convert("L")
im = ImageOps.autocontrast(im, cutoff=1)
im = ImageEnhance.Contrast(im).enhance(1.0)
# Character cells are taller than wide, so sample fewer rows than columns.
ROWS = round(COLS * im.height / im.width * CELL_W / CELL_H)
im = im.resize((COLS, ROWS), Image.LANCZOS)
px = im.load()

rows = []
for y in range(ROWS):
    line = []
    for x in range(COLS):
        lum = (px[x, y] / 255.0) ** GAMMA
        if lum >= WHITE_FLOOR:
            line.append(" ")
        else:
            line.append(RAMP[min(len(RAMP) - 1, int((1 - lum) * (len(RAMP) - 1) + 0.5))])
    rows.append("".join(line))

ART_W, ART_H = COLS * CELL_W, ROWS * CELL_H
STATUS_H = 34
W = ART_W + PAD * 2
H = TITLEBAR_H + PAD // 2 + ART_H + STATUS_H + PAD // 2
STATIC = bool(os.environ.get("STATIC"))

parts = window(W, H, "erik@github: ~$ ./portrait.sh")
art_top = TITLEBAR_H + PAD // 2
for ry, line in enumerate(rows):
    row_y = art_top + ry * CELL_H
    text = (f'<text xml:space="preserve" x="{PAD}" y="{row_y + CELL_H * 0.78:.1f}" fill="{INK}" '
            f'font-size="{CELL_H * 0.9:.1f}" textLength="{ART_W}" lengthAdjust="spacing">'
            f'{html.escape(line)}</text>')
    if STATIC or not line.strip():
        parts.append(text)
        continue
    delay = ry * ROW_DUR
    parts.append(
        f'<clipPath id="r{ry}"><rect x="{PAD}" y="{row_y}" height="{CELL_H}" width="0">'
        f'<animate attributeName="width" from="0" to="{ART_W}" begin="{delay:.2f}s" '
        f'dur="{ROW_DUR}s" fill="freeze"/></rect></clipPath>'
        f'<g clip-path="url(#r{ry})">{text}</g>'
        f'<rect y="{row_y + 1}" width="{CELL_W}" height="{CELL_H - 2}" fill="{RED}" opacity="0">'
        f'<animate attributeName="x" from="{PAD}" to="{PAD + ART_W}" begin="{delay:.2f}s" '
        f'dur="{ROW_DUR}s" fill="freeze"/>'
        f'<set attributeName="opacity" to="0.9" begin="{delay:.2f}s"/>'
        f'<set attributeName="opacity" to="0" begin="{delay + ROW_DUR:.2f}s"/></rect>'
    )

line_y = art_top + ART_H + PAD // 2
status_y = line_y + 22
parts.append(f'<line x1="0" y1="{line_y}" x2="{W}" y2="{line_y}" stroke="{FRAME}"/>')
prompt, name = "erik@github:~$ whoami ", "Erik Karásek"
parts.append(f'<text x="{PAD}" y="{status_y}" fill="{MUTED}" font-size="13">'
             f'{prompt}<tspan fill="{INK}">{name}</tspan></text>')
# monospace advance is ~0.6em, so the cursor sits one space after the name
parts.append(f'<rect x="{PAD + (len(prompt + name) + 1) * 13 * 0.6:.0f}" y="{status_y - 12}" width="8" height="14" fill="{RED}">'
             '<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;0.5;0.51;1" '
             'dur="1s" repeatCount="indefinite"/></rect>')
parts.append("</svg>")

with open(OUT, "w") as f:
    f.write("".join(parts))
print(f"wrote {OUT}: {W}x{H}, {COLS}x{ROWS} chars")
