#!/usr/bin/env python3
"""
How many times the app has been downloaded: GitHub's counters, plus the
site's own download clicks from GA4.

    ~/.venvs/lf-seo/bin/python tools/downloads.py         # everything below
    ~/.venvs/lf-seo/bin/python tools/downloads.py --all   # plus every release
    ~/.venvs/lf-seo/bin/python tools/downloads.py --json  # machine-readable

Plain `python3` works too and prints the GitHub half; the GA4 half needs
google-auth, which lives in that venv.

Every installer is a GitHub release asset, so every download goes through
GitHub's per-asset `download_count` — the site's buttons and the app's own
updater alike (updater.py fetches `browser_download_url`, the same link). So:

  * This counts downloads, not people. An existing user who auto-updates
    downloads the installer again and is counted again.
  * GitHub keeps one running total per file and nothing else — no dates, no
    countries. The only way to see change over time is to remember the last
    answer, which is what the history file is for.

Site-originated downloads are counted separately in GA4 as `download_mac` /
`download_windows` (site/src/components/Seo.astro), read here through the
same service-account key tools/gsc.py uses (it is admin on the GA4 property).
GitHub's growth since those events went live, minus GA4's count, is roughly
auto-updates — plus direct links and site visitors whose ad blocker drops
GA4, so treat it as an upper bound on updates, not a measurement.

The GitHub half is stdlib only. GITHUB_TOKEN is used if set; one run is a
single request, well inside the 60/hour unauthenticated limit, so it is
optional.
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

GA4_PROPERTY = "properties/537954027"  # "language flipper", web stream G-2CP4BEC4B8
GA4_EVENTS = {"download_mac": "mac", "download_windows": "windows"}
# The GA4 download events went live 2026-09-22 ~10:05 UTC (86dc039). GitHub's
# running totals at that moment, so GitHub's growth since can be set against
# GA4's count — GA4 knows nothing before it.
TRACKING_START = "2026-09-22"
GITHUB_AT_TRACKING_START = {"mac": 67, "windows": 112}

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


def parse_ga4(resp):
    """runReport rows -> {range_name: {platform: count}}. With two named date
    ranges GA4 appends a `dateRange` dimension carrying the range's name."""
    out = {"since_start": {p: 0 for p in PLATFORMS}, "last_7_days": {p: 0 for p in PLATFORMS}}
    for row in resp.get("rows", []):
        event, rng = (d["value"] for d in row["dimensionValues"])
        plat = GA4_EVENTS.get(event)
        if plat and rng in out:
            out[rng][plat] += int(row["metricValues"][0]["value"])
    return out


def fetch_site_downloads():
    """GA4 download events since tracking began and over the last 7 days.
    Raises if google-auth or the key is missing — the caller reports it and
    still prints the GitHub half."""
    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2 import service_account

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from tools.gsc import key_path

    creds = service_account.Credentials.from_service_account_file(
        str(key_path()), scopes=["https://www.googleapis.com/auth/analytics.readonly"]
    )
    body = {
        "dateRanges": [
            {"startDate": TRACKING_START, "endDate": "today", "name": "since_start"},
            {"startDate": "7daysAgo", "endDate": "today", "name": "last_7_days"},
        ],
        "dimensions": [{"name": "eventName"}],
        "metrics": [{"name": "eventCount"}],
        "dimensionFilter": {
            "filter": {"fieldName": "eventName", "inListFilter": {"values": list(GA4_EVENTS)}}
        },
    }
    r = AuthorizedSession(creds).post(
        f"https://analyticsdata.googleapis.com/v1beta/{GA4_PROPERTY}:runReport",
        json=body,
        timeout=20,
    )
    if r.status_code != 200:
        raise RuntimeError(f"GA4 answered {r.status_code}: {r.text[:200]}")
    return parse_ga4(r.json())


def compare(totals, site):
    """GitHub growth since GA4 tracking began vs. GA4's site count."""
    github = {p: totals[p] - GITHUB_AT_TRACKING_START[p] for p in PLATFORMS}
    via_site = site["since_start"]
    return {
        "github_since_start": github,
        "site_since_start": via_site,
        "other": {p: github[p] - via_site[p] for p in PLATFORMS},
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


def render_site(summary, site):
    if isinstance(site, Exception):
        return [
            "",
            f"Site downloads (GA4): unavailable — {type(site).__name__}: {site}",
            "  Run with ~/.venvs/lf-seo/bin/python for this half.",
        ]
    c = compare(summary["totals"], site)
    week = site["last_7_days"]
    out = ["", f"Site downloads (GA4 button clicks, since {TRACKING_START}; GA4 runs a few hours behind)"]
    for plat, label in (("mac", "Mac"), ("windows", "Windows")):
        out.append(f"  {label:<8} {c['site_since_start'][plat]:>6}   last 7 days: {week[plat]}")
    gh, other = c["github_since_start"], c["other"]
    out += [
        "",
        f"Since {TRACKING_START}: GitHub +{sum(gh.values())}, site {sum(c['site_since_start'].values())}"
        f"  ->  {sum(other.values())} came some other way",
        "  (auto-updates, direct links, or site visitors with an ad blocker)",
    ]
    return out


def render(summary, before, show_all, site=None):
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
    if site is not None:
        out += render_site(summary, site)
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

    try:
        site = fetch_site_downloads()
    except Exception as e:  # GitHub numbers are still worth printing
        site = e

    before = last_snapshot()
    if args.json:
        extra = {"error": f"{type(site).__name__}: {site}"} if isinstance(site, Exception) else {
            **site, **compare(summary["totals"], site)}
        print(json.dumps({**summary, "previous": before, "site": extra}, indent=2))
    else:
        print(render(summary, before, args.all, site))
    if not args.no_save:
        save_snapshot(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
