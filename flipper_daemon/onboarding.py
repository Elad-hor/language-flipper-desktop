"""
First-launch onboarding for macOS.
Checks Accessibility + Input Monitoring permissions and guides the user
to grant them if missing. Runs once; marks completion in storage.
"""

import subprocess
import time
from . import storage

# Must match bundle_identifier in language_flipper.spec — tccutil addresses
# the app's privacy grants by this id.
_BUNDLE_ID = "com.languageflipper.desktop"


def _osascript(script: str) -> str:
    try:
        r = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=60
        )
        return r.stdout.strip()
    except Exception:
        return ""


def _run_command(argv: list):
    subprocess.run(argv, capture_output=True, check=False)


def _open_privacy_pane(pane: str):
    """Open a specific Privacy & Security pane in System Settings."""
    _run_command([
        "open",
        f"x-apple.systempreferences:com.apple.preference.security?Privacy_{pane}"
    ])


def _ax_trusted(prompt: bool = False) -> bool:
    """
    Whether the app holds Accessibility rights.

    With prompt=True macOS puts up its own "would like to control this
    computer" sheet, which is the only way to get the app added to the list
    without the user hunting for the "+" button themselves.
    """
    try:
        import ApplicationServices as AS
        if prompt:
            try:
                return bool(AS.AXIsProcessTrustedWithOptions(
                    {AS.kAXTrustedCheckOptionPrompt: True}
                ))
            except Exception:
                pass  # older PyObjC — fall back to the silent check
        return bool(AS.AXIsProcessTrusted())
    except Exception:
        return False


def _clear_stale_tcc_entry():
    """
    Drop the dead privacy grants left behind by an in-place update.

    TCC ties an unsigned app's approval to the binary itself, so when the
    updater swaps the bundle the old row survives with the app's name and its
    tick intact while no longer matching. The user then "re-grants" permission
    by ticking a box that is already ticked, nothing changes, and the hotkey
    stays dead. Resetting removes the row so the prompt below can add the new
    binary for real.

    Only reached once _ax_trusted() has already returned False, so there is no
    working grant here to lose.
    """
    for service in ("Accessibility", "ListenEvent"):
        _run_command(["tccutil", "reset", service, _BUNDLE_ID])


def run_if_needed():
    """Call on startup. Shows full onboarding on first launch; re-prompts for
    permissions if they were revoked (e.g. after installing a new version)."""
    if storage._load().get("onboarding_done"):
        if not _ax_trusted():
            _show_recheck()
        return

    _show_welcome()


def _show_recheck():
    """Permissions were revoked (new binary installed). Re-guide the user."""
    result = _osascript('''
        button returned of (display dialog \
            "Language Flipper needs permissions" & return & return & \
            "A new version was installed and macOS revoked the permissions." & return & \
            "Click Continue to re-grant them." \
            buttons {"Quit", "Continue"} default button "Continue" \
            with title "Language Flipper")
    ''')
    if result != "Continue":
        import sys; sys.exit(0)
    _check_accessibility()


def _show_welcome():
    result = _osascript('''
        button returned of (display dialog ¬
            "Welcome to Language Flipper!\\n\\n" & ¬
            "To flip text anywhere on your Mac, Language Flipper needs two permissions:\\n\\n" & ¬
            "  • Accessibility — to read and replace text\\n" & ¬
            "  • Input Monitoring — to detect the hotkey\\n\\n" & ¬
            "Click Continue to grant them now." ¬
            buttons {"Quit", "Continue"} default button "Continue" ¬
            with title "Language Flipper Setup")
    ''')

    if result != "Continue":
        import sys; sys.exit(0)

    _check_accessibility()


def _check_accessibility():
    if _ax_trusted():
        _check_input_monitoring()
        return

    # A stale row must go before the prompt, or macOS sees an existing entry
    # and never asks.
    _clear_stale_tcc_entry()
    _ax_trusted(prompt=True)

    _osascript('''
        display dialog ¬
            "Step 1 of 2 — Accessibility\\n\\n" & ¬
            "System Settings will open. Add Language Flipper (or Terminal) \\n" & ¬
            "to the Accessibility list, then come back here." ¬
            buttons {"OK"} default button "OK" ¬
            with title "Language Flipper Setup"
    ''')
    _open_privacy_pane("Accessibility")

    # Wait up to 60s for the user to grant it
    for _ in range(30):
        time.sleep(2)
        if _ax_trusted():
            break

    _check_input_monitoring()


def _check_input_monitoring():
    # We can't programmatically detect Input Monitoring status — just prompt.
    _osascript('''
        display dialog ¬
            "Step 2 of 2 — Input Monitoring\\n\\n" & ¬
            "System Settings will open. Add Language Flipper (or Terminal) \\n" & ¬
            "to the Input Monitoring list, then come back here." ¬
            buttons {"OK"} default button "OK" ¬
            with title "Language Flipper Setup"
    ''')
    _open_privacy_pane("ListenEvent")

    time.sleep(3)
    _finish()


def _finish():
    """
    Report what actually happened.

    This used to mark onboarding complete and announce "Permissions granted!"
    unconditionally — _check_accessibility() gives up waiting after 60s and
    calls through either way, so the app cheerfully declared itself ready while
    holding no permissions at all and doing nothing on every hotkey press.
    """
    if not _ax_trusted():
        _osascript('''
            display dialog \
                "Accessibility is still off" & return & return & \
                "Language Flipper cannot see the hotkey without it." & return & \
                "Open System Settings > Privacy & Security > Accessibility " & \
                "and switch Language Flipper on — the hotkey starts working " & \
                "a few seconds later, with no restart needed." \
                buttons {"OK"} default button "OK" \
                with title "Language Flipper"
        ''')
        return

    data = storage._load()
    data["onboarding_done"] = True
    storage._save(data)

    # No quit-and-reopen instruction any more, and no self-exit: the hotkey
    # supervisor (hotkey._supervise) builds the event tap within seconds of the
    # grant landing. The old first-run path killed the app here, which is also
    # why a user who granted permission late was left with a dead hotkey.
    _osascript('''
        display dialog \
            "Permissions granted!" & return & return & \
            "Language Flipper is ready — press Cmd+Shift+Y to flip." \
            buttons {"OK"} default button "OK" \
            with title "Language Flipper"
    ''')
