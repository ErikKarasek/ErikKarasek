#!/usr/bin/env python3
"""
Read daily contribution counts from GitHub's public contributions fragment
(the same HTML the profile page loads) and write data/contributions.json with
the days plus streaks and totals.

Standard library only, no token. Run daily by the update-profile workflow.
"""
import datetime
import json
import os
import re
import sys
import urllib.request

USERNAME = os.environ.get("GH_PROFILE_USER", "ErikKarasek")
URL = f"https://github.com/users/{USERNAME}/contributions"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "contributions.json")

CELL = re.compile(r'<td\b[^>]*\bdata-date="(\d{4}-\d{2}-\d{2})"[^>]*\bid="([^"]+)"')
TIP = re.compile(r'<tool-tip\b[^>]*\bfor="([^"]+)"[^>]*>([^<]*)</tool-tip>')


def fetch_days():
    req = urllib.request.Request(URL, headers={"User-Agent": "profile-readme/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        page = resp.read().decode("utf-8")

    tips = dict(TIP.findall(page))
    days = []
    for date, cell_id in CELL.findall(page):
        m = re.match(r"\s*([\d,]+) contribution", tips.get(cell_id, ""))
        days.append({"date": date, "count": int(m.group(1).replace(",", "")) if m else 0})
    if len(days) < 300:
        sys.exit(f"only {len(days)} calendar cells found; GitHub's markup may have changed")
    return sorted(days, key=lambda d: d["date"])


def streak_ending(days, idx):
    """Length and start of the run of active days ending at idx."""
    start = idx
    while start >= 0 and days[start]["count"] > 0:
        start -= 1
    return idx - start, days[start + 1]["date"] if idx > start else None


def build(days):
    # Today isn't over yet, so an empty today doesn't break the current streak.
    last = len(days) - 1 if days[-1]["count"] else len(days) - 2
    cur_len, cur_start = streak_ending(days, last)

    best_len, best_start, best_end, run = 0, None, None, 0
    for i, d in enumerate(days):
        run = run + 1 if d["count"] else 0
        if run > best_len:
            best_len, best_start, best_end = run, days[i - run + 1]["date"], d["date"]

    total = sum(d["count"] for d in days)
    top = max(days, key=lambda d: d["count"])
    return {
        "username": USERNAME,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "range": {"start": days[0]["date"], "end": days[-1]["date"]},
        "total": total,
        "active_days": sum(1 for d in days if d["count"]),
        "current_streak": {"length": cur_len, "start": cur_start,
                           "end": days[last]["date"] if cur_len else None},
        "longest_streak": {"length": best_len, "start": best_start, "end": best_end},
        "best_day": {"date": top["date"], "count": top["count"]},
        "days": days,
    }


if __name__ == "__main__":
    data = build(fetch_days())
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(data, f, indent=1)
        f.write("\n")
    print(f"{data['total']} contributions, current streak {data['current_streak']['length']}, "
          f"longest {data['longest_streak']['length']}")
