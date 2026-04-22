import threading
from pathlib import Path

import pystray
from PIL import Image, ImageDraw

from .flipper import flip_text
from .text_bridge import read_and_replace
from . import hotkey as hotkey_mod
from . import storage, gumroad, paywall

_in_flight = False
_in_flight_lock = threading.Lock()
_tray_icon = None  # set in run(), used by _refresh_tray_menu


def _on_flip():
    global _in_flight
    with _in_flight_lock:
        if _in_flight:
            return
        _in_flight = True
    try:
        if not paywall.check_and_maybe_block():
            return

        replaced = read_and_replace(flip_text)

        if replaced:
            storage.increment_lifetime_flips()
            _refresh_tray_menu()

    finally:
        with _in_flight_lock:
            _in_flight = False


# ---------------------------------------------------------------------------
# Tray
# ---------------------------------------------------------------------------

def _make_icon() -> Image.Image:
    icon_path = Path(__file__).parent.parent / "assets" / "icon.png"
    if icon_path.exists():
        return Image.open(icon_path)
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([4, 4, 60, 60], fill="#2563eb")
    draw.text((18, 18), "LF", fill="white")
    return img


def _status_label() -> str:
    if gumroad.get_premium_status():
        return "Language Flipper — Premium ✓"
    flips = storage.get_lifetime_flips()
    remaining = max(0, paywall.HARD_LIMIT - flips)
    return f"Language Flipper — {remaining} free flips left"


def _build_menu() -> pystray.Menu:
    is_premium = gumroad.get_premium_status()
    items = [
        pystray.MenuItem(_status_label(), None, enabled=False),
        pystray.Menu.SEPARATOR,
    ]
    if not is_premium:
        items += [
            pystray.MenuItem("Buy Premium ($9.99/year)", lambda: paywall.open_purchase_page()),
            pystray.MenuItem("Activate License", lambda: paywall.show_activate_dialog()),
            pystray.Menu.SEPARATOR,
        ]
    else:
        items += [
            pystray.MenuItem("Deactivate License", _deactivate),
            pystray.Menu.SEPARATOR,
        ]
    items.append(pystray.MenuItem("Quit", lambda icon, _: icon.stop()))
    return pystray.Menu(*items)


def _refresh_tray_menu():
    if _tray_icon:
        _tray_icon.menu = _build_menu()


def _deactivate(_icon=None, _item=None):
    gumroad.deactivate()
    _refresh_tray_menu()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run():
    global _tray_icon

    icon = pystray.Icon(
        "language-flipper",
        _make_icon(),
        "Language Flipper",
        menu=_build_menu(),
    )
    _tray_icon = icon

    _hotkey_handle = hotkey_mod.register(_on_flip)  # noqa: F841

    print("[language-flipper] running. Press Cmd+Shift+Y to flip.")
    icon.run()


if __name__ == "__main__":
    run()
