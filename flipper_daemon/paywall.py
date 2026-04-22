"""
Paywall — 40 lifetime free flips, then premium required.
Dialogs: osascript on macOS, tkinter on Windows/Linux.
"""

import platform
import subprocess
import threading
import webbrowser

from . import storage
from . import gumroad

HARD_LIMIT     = 40
NAG_THRESHOLDS = {10, 20, 30, 35, 39}
PRICE_TEXT     = "$9.99/year"
PURCHASE_URL   = "https://languageflipper.gumroad.com/l/languageflipper"

_PLATFORM = platform.system()


# ---------------------------------------------------------------------------
# Public — called before each flip
# ---------------------------------------------------------------------------

def check_and_maybe_block() -> bool:
    if gumroad.get_premium_status():
        return True

    flips = storage.get_lifetime_flips()

    if flips >= HARD_LIMIT:
        threading.Thread(target=_show_block_dialog, daemon=True).start()
        return False

    if flips in NAG_THRESHOLDS and not storage.nag_already_shown(flips):
        storage.mark_nag_shown(flips)
        threading.Thread(
            target=_show_nag_dialog, args=(flips,), daemon=True
        ).start()

    return True


def show_activate_dialog():
    threading.Thread(target=_show_activate_dialog, daemon=True).start()


def open_purchase_page():
    webbrowser.open(PURCHASE_URL)


# ---------------------------------------------------------------------------
# macOS dialogs — osascript (fully native)
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


def _mac_nag(flips_used: int):
    result = _osascript(f'''
        button returned of (display dialog ¬
            "You've used {flips_used} of {HARD_LIMIT} free flips.\\n\\nUpgrade to Language Flipper Premium for unlimited flips — {PRICE_TEXT}" ¬
            buttons {{"Later", "Activate License", "Buy Now"}} ¬
            default button "Buy Now" with title "Language Flipper")
    ''')
    if result == "Buy Now":
        webbrowser.open(PURCHASE_URL)
    elif result == "Activate License":
        _mac_activate()


def _mac_block():
    result = _osascript(f'''
        button returned of (display dialog ¬
            "You've used all {HARD_LIMIT} free flips.\\n\\nUpgrade to Language Flipper Premium to keep flipping — {PRICE_TEXT}" ¬
            buttons {{"Activate License", "Buy Now"}} ¬
            default button "Buy Now" with title "Language Flipper — Upgrade Required")
    ''')
    if result == "Buy Now":
        webbrowser.open(PURCHASE_URL)
    elif result == "Activate License":
        _mac_activate()


def _mac_activate():
    key = _osascript('''
        text returned of (display dialog ¬
            "Enter your Language Flipper license key:" ¬
            default answer "" buttons {"Cancel", "Activate"} ¬
            default button "Activate" with title "Activate Premium")
    ''')
    if not key or key == "Cancel":
        return
    ok, msg = gumroad.verify_license(key)
    status = "Premium activated! Enjoy unlimited flips." if ok else f"Activation failed: {msg}"
    _osascript(f'display dialog "{status}" buttons {{"OK"}} default button "OK" with title "Language Flipper"')


# ---------------------------------------------------------------------------
# Windows / Linux dialogs — tkinter (built-in)
# ---------------------------------------------------------------------------

def _tk_dialog(fn):
    """Run a tkinter dialog function with a hidden root window."""
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        return fn(root)
    finally:
        root.destroy()


def _win_nag(flips_used: int):
    import tkinter as tk
    from tkinter import messagebox

    def run(root):
        msg = (
            f"You've used {flips_used} of {HARD_LIMIT} free flips.\n\n"
            f"Upgrade to Language Flipper Premium for unlimited flips — {PRICE_TEXT}\n\n"
            "Click OK to buy now, or activate via the tray icon."
        )
        if messagebox.askokcancel("Language Flipper", msg, parent=root):
            webbrowser.open(PURCHASE_URL)

    _tk_dialog(run)


def _win_block():
    import tkinter as tk
    from tkinter import messagebox

    def run(root):
        msg = (
            f"You've used all {HARD_LIMIT} free flips.\n\n"
            f"Upgrade to Language Flipper Premium to keep flipping — {PRICE_TEXT}\n\n"
            "Click OK to buy now, or activate a license via the tray icon."
        )
        if messagebox.askokcancel("Language Flipper — Upgrade Required", msg, parent=root):
            webbrowser.open(PURCHASE_URL)

    _tk_dialog(run)


def _win_activate():
    from tkinter import simpledialog, messagebox

    def run(root):
        key = simpledialog.askstring(
            "Activate Premium",
            "Enter your Language Flipper license key:",
            parent=root,
        )
        if not key:
            return
        ok, msg = gumroad.verify_license(key)
        status = "Premium activated! Enjoy unlimited flips." if ok else f"Activation failed: {msg}"
        messagebox.showinfo("Language Flipper", status, parent=root)

    _tk_dialog(run)


# ---------------------------------------------------------------------------
# Router — picks the right dialog backend per platform
# ---------------------------------------------------------------------------

def _show_nag_dialog(flips_used: int):
    if _PLATFORM == "Darwin":
        _mac_nag(flips_used)
    else:
        _win_nag(flips_used)


def _show_block_dialog():
    if _PLATFORM == "Darwin":
        _mac_block()
    else:
        _win_block()


def _show_activate_dialog():
    if _PLATFORM == "Darwin":
        _mac_activate()
    else:
        _win_activate()
