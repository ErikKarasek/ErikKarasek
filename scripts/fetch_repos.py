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
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

USERNAME = os.environ.get("GH_PROFILE_USER", "ErikKarasek")
API = "https://api.github.com"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "repos.json")

# Repos that exist only to hold files, not work worth drawing a building for.
SKIP = {".github"}

# What counts as code when measuring a repo. Height means lines of source, so
# a repo full of product photos and 3D models does not out-tower a real app.
CODE_SUFFIXES = {
    ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".py", ".rs", ".swift", ".go",
    ".java", ".kt", ".rb", ".php", ".sh", ".zsh", ".sql", ".css", ".scss", ".html",
    ".vue", ".svelte", ".c", ".h", ".cpp", ".hpp", ".m", ".mm", ".lua", ".dart",
    ".toml", ".yml", ".yaml", ".gradle", ".pl", ".r", ".ex", ".exs",
}
SKIP_PARTS = {"node_modules", "dist", "build", ".next", "vendor", "pods",
              "third_party", "generated", ".venv", "venv", "target"}
SKIP_NAMES = {"package-lock.json", "pnpm-lock.yaml", "yarn.lock", "composer.lock",
              "cargo.lock", "podfile.lock", "gemfile.lock", "poetry.lock"}
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


def code_size(clone_url):
    """
    Lines of source in the default branch, from a shallow clone.

    The GitHub API only reports how much disk a repo takes, which is mostly
    assets for anything with images or 3D models. Cloning is the cheapest way
    to count actual code: depth 1, deleted right after.
    """
    tmp = tempfile.mkdtemp(prefix="city-")
    try:
        subprocess.run(["git", "clone", "--depth", "1", "--quiet", clone_url, tmp],
                       check=True, capture_output=True, timeout=180)
        files = subprocess.run(["git", "-C", tmp, "ls-files"],
                               check=True, capture_output=True, text=True, timeout=60).stdout
        lines = 0
        counted = 0
        for rel in files.splitlines():
            low = rel.lower()
            if any(part in SKIP_PARTS for part in low.split("/")[:-1]):
                continue
            name = low.split("/")[-1]
            if name in SKIP_NAMES or ".min." in name:
                continue
            if os.path.splitext(low)[1] not in CODE_SUFFIXES:
                continue
            path = os.path.join(tmp, rel)
            try:
                with open(path, "rb") as f:
                    lines += f.read().count(b"\n") + 1
                counted += 1
            except OSError:
                continue
        return lines, counted
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as err:
        print(f"  could not measure {clone_url}: {err}")
        return 0, 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


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
        lines, code_files = code_size(r["clone_url"])
        out.append({
            "name": r["name"],
            "kb": r["size"],
            "lines": lines,
            "code_files": code_files,
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

    out.sort(key=lambda r: -r["lines"])
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
    print(f"{len(data['repos'])} public repos, "
          f"{sum(r['lines'] for r in data['repos']):,} lines of code, "
          f"{data['commits_in_window']} commits in the last {data['window_hours']} h")
