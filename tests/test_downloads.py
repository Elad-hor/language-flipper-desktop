"""
The download counter.

    python3 tests/test_downloads.py

GitHub reports one running total per release asset. The tool has to split
those by platform even for the early releases that carried both installers
under one tag, pick the current version numerically (as strings 0.1.67 sorts
above 0.1.111 — the same trap as Key Past Bug #20's stale link), and leave out
-rc prereleases, which reach no user.
"""

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.downloads import (  # noqa: E402
    GITHUB_AT_TRACKING_START,
    compare,
    last_snapshot,
    parse_ga4,
    save_snapshot,
    summarize,
)


def _rel(tag, published, assets, prerelease=False, draft=False):
    return {
        "tag_name": tag,
        "published_at": f"{published}T00:00:00Z",
        "prerelease": prerelease,
        "draft": draft,
        "assets": [{"name": n, "download_count": c} for n, c in assets],
    }


RELEASES = [
    _rel("v0.1.111-mac", "2026-08-13", [("Language.Flipper.dmg", 8)]),
    _rel("v0.1.105-windows", "2026-05-09", [("Language-Flipper-Setup.exe", 50)]),
    _rel("v0.1.67-mac", "2026-04-26", [("Language.Flipper.dmg", 27)]),
    # Early releases carried both installers and no platform suffix.
    _rel(
        "v0.1.59",
        "2026-04-23",
        [("Language.Flipper.dmg", 12), ("Language-Flipper-Setup.exe", 7)],
    ),
    _rel("v0.1.20", "2026-04-22", [("Language-Flipper-Windows.zip", 3)]),
    _rel("v0.1.112-windows-rc", "2026-08-16", [("Language-Flipper-Setup.exe", 4)], prerelease=True),
    _rel("v0.1.113-mac", "2026-09-01", [("Language.Flipper.dmg", 9)], draft=True),
]


class SummarizeTest(unittest.TestCase):
    def setUp(self):
        self.s = summarize(RELEASES)

    def test_splits_by_file_type_not_tag(self):
        self.assertEqual(self.s["totals"], {"mac": 47, "windows": 60})
        self.assertEqual(self.s["total"], 107)

    def test_current_version_compares_numerically(self):
        self.assertEqual(self.s["current"]["mac"]["tag"], "v0.1.111-mac")
        self.assertEqual(self.s["current"]["windows"]["tag"], "v0.1.105-windows")

    def test_prereleases_and_drafts_are_left_out(self):
        tags = {r["tag"] for r in self.s["releases"]}
        self.assertNotIn("v0.1.112-windows-rc", tags)
        self.assertNotIn("v0.1.113-mac", tags)

    def test_unknown_assets_are_ignored(self):
        s = summarize([_rel("v0.1.1", "2026-04-22", [("checksums.txt", 99)])])
        self.assertEqual(s["total"], 0)


def _ga_row(event, rng, count):
    return {"dimensionValues": [{"value": event}, {"value": rng}], "metricValues": [{"value": str(count)}]}


class Ga4Test(unittest.TestCase):
    # Shape confirmed against the live Data API: two named date ranges make
    # GA4 append a dateRange dimension carrying each range's name.
    RESP = {"rows": [
        _ga_row("download_mac", "since_start", 5),
        _ga_row("download_windows", "since_start", 9),
        _ga_row("download_windows", "last_7_days", 2),
        _ga_row("page_view", "since_start", 400),
    ]}

    def test_parse_maps_events_to_platforms_per_range(self):
        got = parse_ga4(self.RESP)
        self.assertEqual(got["since_start"], {"mac": 5, "windows": 9})
        self.assertEqual(got["last_7_days"], {"mac": 0, "windows": 2})

    def test_no_rows_means_zero_not_missing(self):
        # GA4 omits rows entirely for events that never fired.
        self.assertEqual(parse_ga4({})["since_start"], {"mac": 0, "windows": 0})

    def test_compare_uses_github_growth_since_tracking_began(self):
        totals = {p: n + 10 for p, n in GITHUB_AT_TRACKING_START.items()}
        c = compare(totals, parse_ga4(self.RESP))
        self.assertEqual(c["github_since_start"], {"mac": 10, "windows": 10})
        self.assertEqual(c["other"], {"mac": 5, "windows": 1})


class HistoryTest(unittest.TestCase):
    def test_round_trip_returns_the_latest_snapshot(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "sub" / "history.jsonl"
            self.assertIsNone(last_snapshot(path))
            save_snapshot({"totals": {"mac": 1, "windows": 2}}, path)
            save_snapshot({"totals": {"mac": 3, "windows": 4}}, path)
            self.assertEqual(last_snapshot(path)["totals"], {"mac": 3, "windows": 4})


if __name__ == "__main__":
    unittest.main()
