"""Shared look for every SVG in this repo: a dark terminal window with a
Spider-Man red/blue accent, matching erikkarasek.cz."""

BG = "#0d1117"
BG2 = "#141a24"
FRAME = "#30363d"
MUTED = "#7d8590"
TEXT = "#e6edf3"
INK = "#c9d1d9"
RED = "#e23636"
BLUE = "#4d9de0"
GOLD = "#f2cc60"

FONT = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
PAD = 20
TITLEBAR_H = 30


def window(width, height, title):
    """Opening tag, background, frame, title bar with traffic lights."""
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="{FONT}">',
        '<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{BG2}"/><stop offset="1" stop-color="{BG}"/>'
        '</linearGradient></defs>',
        f'<rect width="{width}" height="{height}" rx="12" fill="url(#bg)"/>',
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="12" '
        f'fill="none" stroke="{FRAME}"/>',
        f'<line x1="0" y1="{TITLEBAR_H}" x2="{width}" y2="{TITLEBAR_H}" stroke="{FRAME}"/>',
        *[
            f'<circle cx="{PAD + i * 16}" cy="{TITLEBAR_H / 2}" r="5" fill="{c}"/>'
            for i, c in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"])
        ],
        f'<text x="{width / 2}" y="{TITLEBAR_H / 2 + 4}" fill="{MUTED}" font-size="12" '
        f'text-anchor="middle">{title}</text>',
    ]
