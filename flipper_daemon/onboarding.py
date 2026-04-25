"""
First-launch onboarding for macOS.
Checks Accessibility + Input Monitoring permissions and guides the user
to grant them if missing. Re-runs if permissions are revoked.
"""

import subprocess
import time
from . import storage


def _osascript(script: str) -> str:
    try:
        r = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=60
        )
        return r.stdout.strip()
    except Exception:
        return ""


def _open_privacy_pane(pane: str):
    """Open a specific Privacy & Security pane in System Settings."""
    subprocess.run([
        "open",
        f"x-apple.systempreferences:com.apple.preference.security?Privacy_{pane}"
    ], check=False)


def _ax_trusted() -> bool:
    try:
        import ApplicationServices as AS
        return bool(AS.AXIsProcessTrusted())
    except Exception:
        return False


def run_if_needed():
    """Call on startup. Shows onboarding if permissions are missing."""
    if _ax_trusted() and storage._load().get("onboarding_done"):
        return
    _show_welcome()


def _show_welcome():
    result = _osascript(
        'button returned of (display dialog '
        '"Welcome to Language Flipper!\\n\\n'
        'To flip text anywhere on your Mac, Language Flipper needs two permissions:\\n\\n'
        '  • Accessibility — to read and replace text\\n'
        '  • Input Monitoring — to detect the hotkey\\n\\n'
        'Click Continue to grant them now." '
        'buttons {"Quit", "Continue"} default button "Continue" '
        'with title "Language Flipper Setup")'
    )
    if result != "Continue":
        import sys; sys.exit(0)
    _check_accessibility()


def _check_accessibility():
    if _ax_trusted():
        _check_input_monitoring()
        return

    _osascript(
        'display dialog '
        '"Step 1 of 2 — Accessibility\\n\\n'
        'System Settings will open. Find Language Flipper in the list,\\n'
        'enable it, then come back here and click OK." '
        'buttons {"OK"} default button "OK" '
        'with title "Language Flipper Setup"'
    )
    _open_privacy_pane("Accessibility")

    for _ in range(30):
        time.sleep(2)
        if _ax_trusted():
            break

    _check_input_monitoring()


def _check_input_monitoring():
    _osascript(
        'display dialog '
        '"Step 2 of 2 — Input Monitoring\\n\\n'
        'System Settings will open. Find Language Flipper in the list,\\n'
        'enable it, then come back here and click OK." '
        'buttons {"OK"} default button "OK" '
        'with title "Language Flipper Setup"'
    )
    _open_privacy_pane("ListenEvent")
    time.sleep(3)
    _finish()


def _finish():
    data = storage._load()
    data["onboarding_done"] = True
    storage._save(data)

    _osascript(
        'display dialog '
        '"You\'re all set!\\n\\n'
        'Language Flipper is running in your menu bar.\\n'
        'Select any text and press Cmd+Shift+Y to flip it." '
        'buttons {"Got it!"} default button "Got it!" '
        'with title "Language Flipper"'
    )
