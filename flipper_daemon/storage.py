import json
import time
from pathlib import Path

_DATA_DIR  = Path.home() / ".config" / "language-flipper"
_DATA_FILE = _DATA_DIR / "data.json"


def _load() -> dict:
    try:
        return json.loads(_DATA_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(data: dict):
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    _DATA_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Flip counter
# ---------------------------------------------------------------------------

def get_lifetime_flips() -> int:
    return int(_load().get("lifetime_flips", 0))


def increment_lifetime_flips() -> int:
    data = _load()
    data["lifetime_flips"] = int(data.get("lifetime_flips", 0)) + 1
    _save(data)
    return data["lifetime_flips"]


def mark_nag_shown(threshold: int):
    data = _load()
    shown = set(data.get("nags_shown", []))
    shown.add(threshold)
    data["nags_shown"] = list(shown)
    _save(data)


def nag_already_shown(threshold: int) -> bool:
    return threshold in _load().get("nags_shown", [])


# ---------------------------------------------------------------------------
# License
# ---------------------------------------------------------------------------

def get_license_info() -> dict | None:
    return _load().get("license_info")


def set_license_info(info: dict):
    data = _load()
    data["license_info"] = info
    _save(data)


def clear_license():
    data = _load()
    data.pop("license_info", None)
    _save(data)
