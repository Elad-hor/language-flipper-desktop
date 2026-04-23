"""
Gumroad license verification — mirrors the Chrome extension's gumroad.js.

Master key: SHA256 hash stored here; plaintext known only to the developer.
If the entered key matches the hash it is accepted without an API call.
"""

import hashlib
import json
import time
import urllib.parse
import urllib.request

from . import storage

_PRODUCT_PERMALINK = "languageflipper"
_VERIFY_URL        = "https://api.gumroad.com/v2/licenses/verify"
_CACHE_TTL         = 86400  # 24 hours

# SHA256 of the developer master key — plaintext never stored in source.
_MASTER_HASH = "75314de6aec366736e1bd9b695d87b3e85577d05f107b45010d07daaef4e5138"


def _is_master_key(key: str) -> bool:
    h = hashlib.sha256(key.strip().encode()).hexdigest()
    return h == _MASTER_HASH


def _call_api(key: str) -> dict:
    body = urllib.parse.urlencode({
        "product_permalink": _PRODUCT_PERMALINK,
        "license_key": key.strip(),
        "increment_uses_count": "false",
    }).encode()
    req = urllib.request.Request(_VERIFY_URL, data=body, method="POST")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def verify_license(key: str) -> tuple[bool, str]:
    """
    Verify a license key. Returns (success, message).
    Saves result to storage on success.
    """
    key = key.strip()
    if not key:
        return False, "No license key entered."

    if _is_master_key(key):
        storage.set_license_info({
            "key": key,
            "success": True,
            "verified_at": time.time(),
            "master": True,
        })
        return True, "Premium activated."

    try:
        result = _call_api(key)
        success = bool(result.get("success"))
        if success:
            storage.set_license_info({
                "key": key,
                "success": True,
                "verified_at": time.time(),
            })
            return True, "Premium activated."
        else:
            msg = result.get("message", "Invalid license key.")
            return False, msg
    except Exception as e:
        return False, f"Could not reach Gumroad: {e}"


def get_premium_status() -> bool:
    """
    Returns True if the user has a valid premium license.
    Trusts the cache for 24h, then silently re-verifies.
    Fails open (returns True) if offline and cache says premium.
    """
    info = storage.get_license_info()
    if not info or not info.get("success"):
        return False

    if info.get("master"):
        return True

    age = time.time() - info.get("verified_at", 0)
    if age < _CACHE_TTL:
        return True

    # Silent re-verify
    try:
        result = _call_api(info["key"])
        ok = bool(result.get("success"))
        info["success"] = ok
        info["verified_at"] = time.time()
        storage.set_license_info(info)
        return ok
    except Exception:
        return True  # fail open if offline


def deactivate():
    storage.clear_license()
