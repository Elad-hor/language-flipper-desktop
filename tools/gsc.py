#!/usr/bin/env python3
"""
Google Search Console client for languageflipper.com.

Run it with the venv that carries the Google libraries:

    ~/.venvs/lf-seo/bin/python tools/gsc.py sites
    ~/.venvs/lf-seo/bin/python tools/gsc.py queries --days 90
    ~/.venvs/lf-seo/bin/python tools/gsc.py queries --days 90 --json out.json
    ~/.venvs/lf-seo/bin/python tools/gsc.py pages --days 28
    ~/.venvs/lf-seo/bin/python tools/gsc.py opportunities --days 90

Auth is a service account, not OAuth, so it needs no browser and no refresh
token — which is the point: the SEO agent has to be able to run this
unattended. Two things must both be true or the API returns an empty list of
sites rather than an error, which is the single most confusing failure here:

  1. The JSON key exists (GSC_CREDENTIALS, or ~/.config/gsc/language-flipper.json).
  2. The service account's own email has been added as a user IN Search
     Console (Settings -> Users and permissions -> Add user). Creating the
     key grants nothing by itself.

`sites` exists to tell those two apart, so run it first.

The key is a secret. Keep it outside the repo — .gitignore covers the usual
spots, but the default path is under ~/.config for a reason.
"""

import argparse
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]

# Checked in order. The ~/.gcp one is where the key already lived — found
# 2026-09-14, set up about a month earlier. Note that ~/.gcp/keywords/*.json
# are NOT credentials despite sitting next door; they are saved GSC query
# snapshots, and pointing the loader at one gives a confusing MalformedError.
CRED_CANDIDATES = [
    Path.home() / ".config" / "gsc" / "language-flipper.json",
    Path.home() / ".gcp" / "claude-reporter.json",
]

# A GSC property is either a URL prefix or a domain property, and they are
# different strings. We try the domain form first because that is what covers
# http/https and www in one, which is how this site is set up.
SITE_CANDIDATES = [
    "sc-domain:languageflipper.com",
    "https://languageflipper.com/",
    "https://www.languageflipper.com/",
]


def _die(msg, code=1):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def key_path():
    """The service-account key file. The same key is admin on GA4 too, so
    tools/downloads.py uses this as well. Raises FileNotFoundError with the
    places it looked."""
    env = os.environ.get("GSC_CREDENTIALS")
    if env:
        path = Path(env).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"GSC_CREDENTIALS points at {path}, which does not exist")
        return path
    path = next((p for p in CRED_CANDIDATES if p.exists()), None)
    if path is None:
        raise FileNotFoundError(
            "no service-account key found. Looked in:\n       "
            + "\n       ".join(str(p) for p in CRED_CANDIDATES)
            + "\n       Set GSC_CREDENTIALS=/path/to/key.json to override."
        )
    return path


def _service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    try:
        path = key_path()
    except FileNotFoundError as exc:
        _die(str(exc))
    try:
        creds = service_account.Credentials.from_service_account_file(str(path), scopes=SCOPES)
    except Exception as exc:
        _die(f"could not read the key at {path}: {type(exc).__name__}: {exc}")
    # cache_discovery=False: the default file cache warns noisily and is
    # useless for a one-shot CLI.
    return build("searchconsole", "v1", credentials=creds, cache_discovery=False), creds


def _resolve_site(svc, explicit=None):
    """Return the property string this account can actually read."""
    if explicit:
        return explicit
    entries = svc.sites().list().execute().get("siteEntry", [])
    owned = {e["siteUrl"] for e in entries}
    for cand in SITE_CANDIDATES:
        if cand in owned:
            return cand
    if owned:
        return sorted(owned)[0]
    _die(
        "the service account can see NO properties.\n"
        "       The key works — Search Console just hasn't granted it anything.\n"
        "       Fix: Search Console -> Settings -> Users and permissions ->\n"
        "       Add user -> paste the service account's client_email -> Full."
    )


def cmd_sites(args):
    svc, creds = _service()
    print(f"service account: {creds.service_account_email}")
    entries = svc.sites().list().execute().get("siteEntry", [])
    if not entries:
        print("\nproperties visible: NONE")
        print("\nThe key is valid, but it has not been added as a user in Search Console.")
        print("Search Console -> Settings -> Users and permissions -> Add user")
        print(f"  -> paste:  {creds.service_account_email}")
        print("  -> permission: Full")
        return 1
    print(f"\nproperties visible: {len(entries)}")
    for e in entries:
        print(f"  {e['permissionLevel']:<16} {e['siteUrl']}")
    return 0


def _query(svc, site, days, dimensions, limit, filters=None):
    end = date.today() - timedelta(days=2)      # GSC data lags ~2 days
    start = end - timedelta(days=days)
    body = {
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "dimensions": dimensions,
        "rowLimit": limit,
    }
    if filters:
        body["dimensionFilterGroups"] = [{"filters": filters}]
    resp = svc.searchanalytics().query(siteUrl=site, body=body).execute()
    return resp.get("rows", []), start, end


def _table(rows, dim_label, top=None):
    if not rows:
        print("  (no rows — the property may have no data for this range)")
        return
    shown = rows[:top] if top else rows
    w = max(len(dim_label), max(len(r["keys"][0]) for r in shown))
    w = min(w, 62)
    print(f"  {dim_label:<{w}}  {'clicks':>7} {'impr':>8} {'ctr':>7} {'pos':>6}")
    print(f"  {'-'*w}  {'-'*7} {'-'*8} {'-'*7} {'-'*6}")
    for r in shown:
        k = r["keys"][0]
        k = k if len(k) <= w else k[: w - 1] + "…"
        print(f"  {k:<{w}}  {r['clicks']:>7.0f} {r['impressions']:>8.0f} "
              f"{r['ctr']*100:>6.1f}% {r['position']:>6.1f}")


def _dump(rows, path, dims):
    out = [dict(zip(dims, r["keys"]), clicks=r["clicks"], impressions=r["impressions"],
                 ctr=r["ctr"], position=r["position"]) for r in rows]
    Path(path).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nwrote {len(out)} rows -> {path}")


def cmd_queries(args):
    svc, _ = _service()
    site = _resolve_site(svc, args.site)
    rows, s, e = _query(svc, site, args.days, ["query"], args.limit)
    print(f"{site}   {s} .. {e}   {len(rows)} queries\n")
    _table(rows, "query", args.top)
    if args.json:
        _dump(rows, args.json, ["query"])
    return 0


def cmd_pages(args):
    svc, _ = _service()
    site = _resolve_site(svc, args.site)
    rows, s, e = _query(svc, site, args.days, ["page"], args.limit)
    print(f"{site}   {s} .. {e}   {len(rows)} pages\n")
    _table(rows, "page", args.top)
    if args.json:
        _dump(rows, args.json, ["page"])
    return 0


def cmd_opportunities(args):
    """
    Queries ranking 5-25: enough impressions to prove demand, close enough to
    page one that a better-targeted page can realistically move them. This is
    where effort pays back fastest, so it gets its own command.
    """
    svc, _ = _service()
    site = _resolve_site(svc, args.site)
    rows, s, e = _query(svc, site, args.days, ["query"], 5000)
    picks = [r for r in rows
             if 5 <= r["position"] <= 25 and r["impressions"] >= args.min_impressions]
    picks.sort(key=lambda r: -r["impressions"])
    print(f"{site}   {s} .. {e}")
    print(f"{len(rows)} queries total -> {len(picks)} ranking 5-25 "
          f"with >= {args.min_impressions} impressions\n")
    _table(picks, "query", args.top)
    if args.json:
        _dump(picks, args.json, ["query"])
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("sites", help="list properties this account can read — run this first")

    for name, fn, helptext in (
        ("queries", cmd_queries, "top search queries"),
        ("pages", cmd_pages, "top pages"),
        ("opportunities", cmd_opportunities, "queries ranking 5-25, best effort-to-reward"),
    ):
        sp = sub.add_parser(name, help=helptext)
        sp.add_argument("--days", type=int, default=90)
        sp.add_argument("--limit", type=int, default=1000)
        sp.add_argument("--top", type=int, default=40, help="rows to print (all still go to --json)")
        sp.add_argument("--json", help="write full results to this file")
        sp.add_argument("--site", help="override the property string")
        if name == "opportunities":
            sp.add_argument("--min-impressions", type=int, default=10)
        sp.set_defaults(func=fn)

    args = p.parse_args()
    if args.cmd == "sites":
        return cmd_sites(args)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
