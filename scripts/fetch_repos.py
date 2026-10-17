#!/usr/bin/env python3
"""
Collect what the city needs about every public repo: how big it is, when it was
last pushed, how many commits landed in the last 24 hours and whether a pull
request is open. Writes data/repos.json.

Standard library only. A token is optional: GH_TOKEN (or GITHUB_TOKEN, which
Actions provides) only raises the rate limit, it never widens what is visible,
so the city stays public-only either way.

Run daily by the update-profile workflow, before render_city_svg.py.
"""
import datetime
import json
import os
import sys
import urllib.error
import urllib.request

USERNAME = os.environ.get("GH_PROFILE_USER", "ErikKarasek")
API = "https://api.github.com"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "repos.json")

# Repos that exist only to hold files, not work worth drawing a building for.
SKIP = {".github"}
WINDOW_H = 24          # commits counted this far back
STALE_DAYS = 90        # no push for this long: the building gets boarded up
NEW_DAYS = 14          # created this recently: it still has a crane on it
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")


def get(path, params=None):
    url = f"{API}{path}"
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    headers = {
        "User-Agent": "profile-readme/1.0",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def repos():
    """Public, non-fork repos owned by the user, largest first."""
    out = []
    for page in range(1, 4):
        batch = get(f"/users/{USERNAME}/repos",
                    {"per_page": 100, "page": page, "type": "owner", "sort": "pushed"})
        out += batch
        if len(batch) < 100:
            break
    # The private filter is deliberate: with a personal token the same endpoint
    # would also return private repos, and this city is public-only on purpose.
    return [r for r in out
            if not r["private"] and not r["fork"] and r["name"] not in SKIP]


def activity(since):
    """
    Per repo, what landed in public inside the window.

    Two numbers, because GitHub only sometimes says how many commits there were.
    A plain push carries its commit count; opening a pull request carries the
    count of the branch behind it; pushing a brand new branch often shows up as
    a CreateEvent alone, with no count at all. So `commits` is what GitHub
    actually counted and `events` is how many times something moved, and the
    city lights at least one window whenever a repo moved.

    The feed is not strictly ordered by time, so every page is filtered rather
    than stopping at the first old entry.
    """
    out = {}

    def bump(name, commits=0):
        row = out.setdefault(name, {"commits": 0, "events": 0})
        row["commits"] += commits
        row["events"] += 1

    for page in range(1, 4):
        try:
            events = get(f"/users/{USERNAME}/events/public", {"per_page": 100, "page": page})
        except urllib.error.HTTPError:
            break
        for e in events:
            when = datetime.datetime.strptime(e["created_at"], "%Y-%m-%dT%H:%M:%SZ")
            when = when.replace(tzinfo=datetime.timezone.utc)
            if when < since:
                continue
            name = e["repo"]["name"].split("/")[-1]
            payload = e.get("payload", {})
            if e["type"] == "PushEvent":
                bump(name, payload.get("size", 0))
            elif e["type"] == "PullRequestEvent" and payload.get("action") == "opened":
                bump(name, (payload.get("pull_request") or {}).get("commits", 0))
            elif e["type"] in ("CreateEvent", "PullRequestEvent"):
                bump(name)
        if len(events) < 100:
            break
    return out


def open_prs(repo):
    """Open pull requests, which is what puts scaffolding on a building."""
    try:
        return len(get(f"/repos/{repo}/pulls", {"state": "open", "per_page": 10}))
    except urllib.error.HTTPError:
        return 0


def build():
    now = datetime.datetime.now(datetime.timezone.utc)
    since = now - datetime.timedelta(hours=WINDOW_H)
    moved = activity(since)

    out = []
    for r in repos():
        pushed = datetime.datetime.strptime(r["pushed_at"], "%Y-%m-%dT%H:%M:%SZ")
        pushed = pushed.replace(tzinfo=datetime.timezone.utc)
        created = datetime.datetime.strptime(r["created_at"], "%Y-%m-%dT%H:%M:%SZ")
        created = created.replace(tzinfo=datetime.timezone.utc)
        row = moved.get(r["name"], {"commits": 0, "events": 0})
        out.append({
            "name": r["name"],
            "kb": r["size"],
            "commits": row["commits"],
            "events": row["events"],
            "open_prs": open_prs(r["full_name"]),
            "pushed": r["pushed_at"],
            "days_since_push": (now - pushed).days,
            "days_since_created": (now - created).days,
            "stale": (now - pushed).days >= STALE_DAYS or r["archived"],
            "new": (now - created).days <= NEW_DAYS,
            "language": r["language"] or "",
            "stars": r["stargazers_count"],
            "url": r["html_url"],
        })

    out.sort(key=lambda r: -r["kb"])
    return {
        "username": USERNAME,
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window_hours": WINDOW_H,
        "scope": "public",
        "commits_in_window": sum(r["commits"] for r in out),
        "active_repos": sum(1 for r in out if r["events"]),
        "repos": out,
    }


if __name__ == "__main__":
    try:
        data = build()
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as err:
        # Keep yesterday's city rather than failing the daily run.
        if os.path.exists(OUT):
            print(f"github api unreachable ({err}); keeping the existing {OUT}")
            sys.exit(0)
        sys.exit(f"github api unreachable and no cached data: {err}")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(data, f, indent=1)
        f.write("\n")
    print(f"{len(data['repos'])} public repos, {data['commits_in_window']} commits "
          f"in the last {data['window_hours']} h")
