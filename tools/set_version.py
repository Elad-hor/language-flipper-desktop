"""
Set the release version everywhere it is recorded.

    python3 tools/set_version.py 0.1.112

Three files carry it and they must move together:

  flipper_daemon/version.py     the source of truth; what the app reports and
                                what updater._find_update compares against
  language_flipper.spec         CFBundleShortVersionString, what macOS shows
  language_flipper_setup.iss    AppVersion, what Windows records

Key Past Bug #6 was release_mac.sh bumping the plist but not version.py, so the
app kept reporting the old number and every client re-offered the same update.

The local release scripts each do this with their own text surgery — GNU sed,
BSD sed, PowerShell regex (Key Past Bug #4) — which is fine when a human is
watching the output. CI is not watching, so this fails loudly instead: a
pattern that stops matching raises rather than leaving that file behind.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")

# (path, pattern to find, replacement template)
_TARGETS = (
    (
        "flipper_daemon/version.py",
        re.compile(r'VERSION = "[^"]*"'),
        'VERSION = "{version}"',
    ),
    (
        "language_flipper.spec",
        re.compile(r'"CFBundleShortVersionString": "[^"]*"'),
        '"CFBundleShortVersionString": "{version}"',
    ),
    (
        "language_flipper_setup.iss",
        # [^\r\n]* rather than .*$ — `.` matches \r, so the $ form would eat
        # the carriage return and quietly convert that one line to LF.
        re.compile(r"^AppVersion=[^\r\n]*", re.MULTILINE),
        "AppVersion={version}",
    ),
)


def set_version(version: str, root: Path = ROOT) -> list:
    """
    Rewrite every version-carrying file. Returns the paths that changed.

    Raises ValueError for a version that is not x.y.z (the tags carry suffixes
    like -mac, but the files must not), FileNotFoundError for a missing file,
    and LookupError when a pattern no longer matches — that last one means a
    file was restructured and this needs updating, which must stop a release
    rather than ship a half-bumped build.
    """
    if not _VERSION_RE.match(version or ""):
        raise ValueError(f"version must be x.y.z, got {version!r}")

    root = Path(root)
    changed = []

    for relative, pattern, template in _TARGETS:
        path = root / relative
        if not path.exists():
            raise FileNotFoundError(f"{relative} is missing")

        # newline="" keeps whatever line endings the file already uses, so a
        # bump made on Linux doesn't rewrite a CRLF file end to end.
        with open(path, "r", encoding="utf-8", newline="") as f:
            original = f.read()

        if not pattern.search(original):
            raise LookupError(f"{relative}: no {pattern.pattern!r} to replace")

        updated = pattern.sub(template.format(version=version), original)
        if updated == original:
            continue

        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(updated)
        changed.append(relative)

    return changed


def main(argv):
    if len(argv) != 2:
        print(__doc__.strip().splitlines()[2].strip())
        return 1

    try:
        changed = set_version(argv[1])
    except (ValueError, FileNotFoundError, LookupError) as e:
        print(f"ERROR: {e}")
        return 1

    print(f"version set to {argv[1]}")
    for path in changed:
        print(f"  updated {path}")
    if not changed:
        print("  (already at this version — nothing to change)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
