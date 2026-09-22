#!/usr/bin/env python3
"""
How many times the app has been downloaded, from GitHub's own counters.

    python3 tools/downloads.py            # totals, current versions, change since last run
    python3 tools/downloads.py --all      # plus every release
    python3 tools/downloads.py --json     # machine-readable

Every installer is a GitHub release asset, so every download goes through
GitHub's per-asset `download_count` — the site's buttons and the app's own
updater alike (updater.py fetches `browser_download_url`, the same link). So:

  * This counts downloads, not people. An existing user who auto-updates
    downloads the installer again and is counted again.
  * GitHub keeps one running total per file and nothing else — no dates, no
    countries. The only way to see change over time is to remember the last
    answer, which is what the history file is for.

Site-originated downloads are counted separately in GA4 as `download_mac` /
`download_windows` (site/src/components/Seo.astro). GitHub's total minus
GA4's is roughly the auto-updates.

Stdlib only. GITHUB_TOKEN is used if set; one run is a single request, well
inside the 60/hour unauthenticated limit, so it is optional.
"""

import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = "Elad-hor/language-flipper-desktop"
API = f"https://api.github.com/repos/{REPO}/releases?per_page=100&page={{page}}"

HISTORY_PATH = Path.home() / ".config" / "lf-downloads" / "history.jsonl"

PLATFORMS = ("mac", "windows")


def platform_of(asset_name: str):
    """Asset filename -> platform. Early releases (v0.1.0, v0.1.59) carried
    both installers under one untagged release, so the tag suffix can't be
    trusted — the file extension can."""
    name = asset_name.lower()
    if name.endswith(".dmg"):
        return "mac"
    if name.endswith(".exe") or (name.endswith(".zip") and "windows" in name):
        return "windows"
    return None


def _version_key(tag: str):
    """'v0.1.111-mac' -> (0, 1, 111). Compared as numbers: as strings,
    0.1.67 sorts above 0.1.111."""
    core = tag.lstrip("v").split("-")[0]
    try:
        return tuple(int(p) for p in core.split("."))
    except ValueError:
        return ()


def summarize(releases):
    """Reduce the raw releases API payload to what's worth reading.

    Drafts and prereleases are left out: an -rc reaches no user (the updater
    and the site both skip it), so its downloads are only our own testing.
    """
    totals = {p: 0 for p in PLATFORMS}
    current = {}
    rows = []
    for rel in releases:
        if rel.get("draft") or rel.get("prerelease"):
            continue
        for asset in rel.get("assets", []):
            plat = platform_of(asset["name"])
            if plat is None:
                continue
            count = asset["download_count"]
            totals[plat] += count
            row = {
                "tag": rel["tag_name"],
                "published": (rel.get("published_at") or "")[:10],
                "platform": plat,
                "downloads": count,
            }
            rows.append(row)
            best = current.get(plat)
            if best is None or _version_key(row["tag"]) > _version_key(best["tag"]):
                current[plat] = row
    rows.sort(key=lambda r: (r["published"], _version_key(r["tag"])), reverse=True)
    return {
        "totals": totals,
        "total": sum(totals.values()),
        "current": current,
        "releases": rows,
    }


def fetch_releases():
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "lf-downloads"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    releases, page = [], 1
    while True:
        req = urllib.request.Request(API.format(page=page), headers=headers)
        with urllib.request.urlopen(req, timeout=20) as r:
            batch = json.load(r)
        releases.extend(batch)
        if len(batch) < 100:
            return releases
        page += 1


def last_snapshot(path=HISTORY_PATH):
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return None
    for line in reversed(lines):
        if line.strip():
            return json.loads(line)
    return None


def save_snapshot(summary, path=HISTORY_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "totals": summary["totals"],
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def _delta(now, before, plat):
    if not before:
        return ""
    return f"  (+{now - before['totals'].get(plat, 0)})"


def render(summary, before, show_all):
    t = summary["totals"]
    since = f"  — change since {before['at'][:16].replace('T', ' ')} UTC" if before else ""
    prev_total = sum(before["totals"].values()) if before else 0
    out = [
        f"Downloads (all time){since}",
        f"  Mac      {t['mac']:>6}{_delta(t['mac'], before, 'mac')}",
        f"  Windows  {t['windows']:>6}{_delta(t['windows'], before, 'windows')}",
        f"  Total    {summary['total']:>6}"
        + (f"  (+{summary['total'] - prev_total})" if before else ""),
        "",
        "Current version (what the site and the updater hand out now):",
    ]
    for plat in PLATFORMS:
        row = summary["current"].get(plat)
        if row:
            out.append(
                f"  {plat:<8} {row['tag']:<18} since {row['published']}  {row['downloads']:>5}"
            )
    if show_all:
        out += ["", "Every release, newest first:"]
        for r in summary["releases"]:
            out.append(
                f"  {r['published']}  {r['tag']:<18} {r['platform']:<8} {r['downloads']:>5}"
            )
    out += [
        "",
        "Counts downloads, not people: auto-updates download the installer again.",
    ]
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--all", action="store_true", help="list every release")
    ap.add_argument("--json", action="store_true", help="print JSON instead of a table")
    ap.add_argument(
        "--no-save",
        action="store_true",
        help="don't record this run, so the next one compares against the previous",
    )
    args = ap.parse_args(argv)

    try:
        summary = summarize(fetch_releases())
    except Exception as e:  # say what broke — a bare failure here reads as "0 downloads"
        print(f"error: could not read releases from GitHub: {e}", file=sys.stderr)
        return 1

    before = last_snapshot()
    if args.json:
        print(json.dumps({**summary, "previous": before}, indent=2))
    else:
        print(render(summary, before, args.all))
    if not args.no_save:
        save_snapshot(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
