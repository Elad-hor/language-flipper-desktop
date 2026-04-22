"""
Paywall logic — 40 lifetime free flips, then premium required.
Mirrors the Chrome extension's Phase 1 model (no daily phase).
"""

import subprocess
import threading
import webbrowser

from . import storage
from . import gumroad

HARD_LIMIT      = 40
NAG_THRESHOLDS  = {10, 20, 30, 35, 39}
PRICE_TEXT      = "$9.99/year"
PURCHASE_URL    = "https://languageflipper.gumroad.com/l/languageflipper"


# ---------------------------------------------------------------------------
# Check — call this BEFORE each flip
# ---------------------------------------------------------------------------

def check_and_maybe_block() -> bool:
    """
    Returns True if the flip should proceed, False if hard-blocked.
    Shows nag dialogs as a side effect (in a background thread so the
    hotkey thread is not stalled waiting for the user to dismiss).
    """
    if gumroad.get_premium_status():
        return True

    flips = storage.get_lifetime_flips()

    if flips >= HARD_LIMIT:
        threading.Thread(target=_show_block_dialog, daemon=True).start()
        return False

    if flips in NAG_THRESHOLDS and not storage.nag_already_shown(flips):
        storage.mark_nag_shown(flips)
        remaining = HARD_LIMIT - flips
        threading.Thread(
            target=_show_nag_dialog, args=(flips, remaining), daemon=True
        ).start()

    return True


# ---------------------------------------------------------------------------
# Dialogs (macOS osascript — fully native, zero extra deps)
# ---------------------------------------------------------------------------

def _osascript(script: str) -> str:
    try:
        r = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=120
        )
        return r.stdout.strip()
    except Exception:
        return ""


def _show_nag_dialog(flips_used: int, remaining: int):
    script = f'''
        set btn to button returned of (display dialog ¬
            "You've used {flips_used} of {HARD_LIMIT} free flips.\\n\\nUpgrade to Language Flipper Premium for unlimited flips — {PRICE_TEXT}" ¬
            buttons {{"Later", "Activate License", "Buy Now"}} ¬
            default button "Buy Now" ¬
            with title "Language Flipper")
        btn
    '''
    result = _osascript(script)
    if result == "Buy Now":
        webbrowser.open(PURCHASE_URL)
    elif result == "Activate License":
        _show_activate_dialog()


def _show_block_dialog():
    script = f'''
        set btn to button returned of (display dialog ¬
            "You've used all {HARD_LIMIT} free flips.\\n\\nUpgrade to Language Flipper Premium to keep flipping — {PRICE_TEXT}" ¬
            buttons {{"Activate License", "Buy Now"}} ¬
            default button "Buy Now" ¬
            with title "Language Flipper — Upgrade Required")
        btn
    '''
    result = _osascript(script)
    if result == "Buy Now":
        webbrowser.open(PURCHASE_URL)
    elif result == "Activate License":
        _show_activate_dialog()


def _show_activate_dialog():
    script = '''
        set k to text returned of (display dialog ¬
            "Enter your License Flipper license key:" ¬
            default answer "" ¬
            buttons {"Cancel", "Activate"} ¬
            default button "Activate" ¬
            with title "Activate Premium")
        k
    '''
    key = _osascript(script)
    if not key or key == "Cancel":
        return

    ok, msg = gumroad.verify_license(key)
    status = "Premium activated! Enjoy unlimited flips." if ok else f"Activation failed: {msg}"
    _osascript(f'''
        display dialog "{status}" ¬
            buttons {{"OK"}} default button "OK" ¬
            with title "Language Flipper"
    ''')


# ---------------------------------------------------------------------------
# Called from tray menu
# ---------------------------------------------------------------------------

def show_activate_dialog():
    threading.Thread(target=_show_activate_dialog, daemon=True).start()


def open_purchase_page():
    webbrowser.open(PURCHASE_URL)
