#!/usr/bin/env python3
"""Pull everything the README cards need into data/*.json.

Two sources, no third-party deps:
  * the public contribution calendar HTML (no auth needed)
  * the REST API for repo + pull-request counts (GITHUB_TOKEN if present)

Every search is pinned to `is:public` so a run with a personal token and a run
inside Actions produce the same numbers.

Run: python scripts/fetch_github_data.py
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

USER = "WasThatRudy"
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

# Own / club repos worth a card, in display order.
FEATURED = [
    "pointblank-club/Zenith",
    "pointblank-club/Kitten",
    "WasThatRudy/headlamp-kmesh-plugin",
]

# Upstream projects to surface, with the org label shown on the card.
# Counts come from the aggregated PR search below, so a repo rename here is
# the only thing that needs touching.
UPSTREAM = [
    ("kubernetes-sigs/headlamp", "Headlamp", "CNCF"),
    ("podman-container-tools/podman", "Podman", "Containers"),
    ("jaegertracing/jaeger-ui", "Jaeger UI", "CNCF"),
    ("Apicurio/apicurio-registry", "Apicurio Registry", "Red Hat"),
    ("flatcar/nebraska", "Nebraska", "Flatcar"),
]

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) readme-cards/1.0"


def get(url: str, accept: str = "application/vnd.github+json") -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token and "api.github.com" in url:
        req.add_header("Authorization", f"Bearer {token}")
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 429) and attempt < 3:
                time.sleep(8 * (attempt + 1))
                continue
            raise
        except urllib.error.URLError:
            if attempt < 3:
                time.sleep(3 * (attempt + 1))
                continue
            raise
    raise RuntimeError(f"unreachable: {url}")


def get_json(url: str):
    return json.loads(get(url))


# ---------------------------------------------------------------- calendar

TD_RE = re.compile(
    r'<td[^>]*data-date="(?P<date>\d{4}-\d{2}-\d{2})"[^>]*id="(?P<id>[^"]+)"[^>]*data-level="(?P<level>\d)"'
)
TIP_RE = re.compile(r'<tool-tip[^>]*for="(?P<id>[^"]+)"[^>]*>(?P<text>[^<]*)</tool-tip>')
COUNT_RE = re.compile(r"^(?:(\d[\d,]*)|No)\s+contribution")


def fetch_calendar() -> dict:
    html = get(f"https://github.com/users/{USER}/contributions", accept="text/html")
    tips = {m.group("id"): m.group("text") for m in TIP_RE.finditer(html)}

    days = []
    today = date.today().isoformat()
    for m in TD_RE.finditer(html):
        iso = m.group("date")
        if iso > today:  # GitHub pads the final week into the future
            continue
        text = tips.get(m.group("id"), "")
        hit = COUNT_RE.match(text.strip())
        count = int(hit.group(1).replace(",", "")) if (hit and hit.group(1)) else 0
        days.append({"date": iso, "count": count, "level": int(m.group("level"))})

    if len(days) < 300:
        raise SystemExit(f"only parsed {len(days)} days - the calendar markup likely changed")

    days.sort(key=lambda d: d["date"])
    return {
        "user": USER,
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total": sum(d["count"] for d in days),
        "days": days,
    }


# ------------------------------------------------------------------- stats


def search_prs(state_qualifier: str) -> tuple[int, Counter]:
    """Return (total, merged-per-repo) for every public PR matching the state."""
    base = "https://api.github.com/search/issues?per_page=100&advanced_search=true&page={page}&q="
    query = urllib.parse.quote(f"is:pr author:{USER} is:public {state_qualifier}")
    per_repo: Counter = Counter()
    total = 0
    for page in range(1, 11):  # search caps at 1000 results
        try:
            payload = get_json(base.format(page=page) + query)
        except Exception as exc:
            print(f"  ! PR search page {page} failed: {exc}", file=sys.stderr)
            break
        total = payload.get("total_count", total)
        items = payload.get("items", [])
        for item in items:
            repo = item.get("repository_url", "").replace("https://api.github.com/repos/", "")
            if repo:
                per_repo[repo] += 1
        if len(items) < 100:
            break
        time.sleep(2)
    return total, per_repo


def fetch_stats() -> dict:
    profile = get_json(f"https://api.github.com/users/{USER}")

    merged_total, merged_by_repo = search_prs("is:merged")
    time.sleep(2)
    open_total, open_by_repo = search_prs("is:open")

    repos = []
    for full in FEATURED:
        try:
            r = get_json(f"https://api.github.com/repos/{full}")
        except Exception as exc:
            print(f"  ! repo failed ({full}): {exc}", file=sys.stderr)
            continue
        repos.append(
            {
                "name": r["name"],
                "full_name": r["full_name"],
                "description": (r.get("description") or "").strip(),
                "language": (r.get("language") or ""),
                "stars": r.get("stargazers_count", 0),
                "forks": r.get("forks_count", 0),
                "url": r["html_url"],
                "merged_prs": merged_by_repo.get(r["full_name"], 0),
            }
        )

    upstream = []
    for full, label, org in UPSTREAM:
        upstream.append(
            {
                "repo": full,
                "label": label,
                "org": org,
                "merged": merged_by_repo.get(full, 0),
                "open": open_by_repo.get(full, 0),
            }
        )
    upstream.sort(key=lambda u: (-u["merged"], -u["open"], u["label"]))

    external = {k: v for k, v in merged_by_repo.items() if not k.startswith(f"{USER}/")}

    return {
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "followers": profile.get("followers", 0),
        "public_repos": profile.get("public_repos", 0),
        "merged_prs": merged_total,
        "open_prs": open_total,
        "merged_prs_external": sum(external.values()),
        "external_repo_count": len(external),
        "stars_earned": sum(r["stars"] for r in repos),
        "repos": repos,
        "upstream": upstream,
        "merged_by_repo": dict(merged_by_repo.most_common()),
    }


def write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"  wrote {path.relative_to(ROOT)}")


def main() -> None:
    print("fetching contribution calendar...")
    cal = fetch_calendar()
    print(f"  {len(cal['days'])} days, {cal['total']} contributions")
    write(DATA / "contributions.json", cal)

    print("fetching repo + PR stats...")
    stats = fetch_stats()
    print(
        f"  {stats['merged_prs']} merged PRs "
        f"({stats['merged_prs_external']} in {stats['external_repo_count']} other people's repos)"
    )
    write(DATA / "stats.json", stats)


if __name__ == "__main__":
    main()
