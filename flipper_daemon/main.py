"""
Language Flipper Desktop — entry point.

Starts the system tray icon and registers the global hotkey.
On hotkey: read focused text via AT-SPI, flip EN↔HE, write back.
"""

import threading
import time
from pathlib import Path

import pystray
from PIL import Image, ImageDraw

from .flipper import flip_text
from .text_bridge import read_and_replace
from . import hotkey as hotkey_mod

_in_flight = False
_in_flight_lock = threading.Lock()


def _on_flip():
    global _in_flight
    with _in_flight_lock:
        if _in_flight:
            return
        _in_flight = True
    try:
        read_and_replace(flip_text)
    finally:
        with _in_flight_lock:
            _in_flight = False


def _make_icon() -> Image.Image:
    """Generate a simple tray icon. Replace with a real PNG asset later."""
    icon_path = Path(__file__).parent.parent / "assets" / "icon.png"
    if icon_path.exists():
        return Image.open(icon_path)

    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([4, 4, 60, 60], fill="#2563eb")
    draw.text((18, 18), "LF", fill="white")
    return img


def _build_menu(icon):
    return pystray.Menu(
        pystray.MenuItem("Language Flipper", None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", lambda: icon.stop()),
    )


def run():
    icon = pystray.Icon(
        "language-flipper",
        _make_icon(),
        "Language Flipper",
    )
    icon.menu = _build_menu(icon)

    # Register hotkey before showing tray
    _hotkey_handle = hotkey_mod.register(_on_flip)  # noqa: F841 — keep alive

    print("[language-flipper] running. Press Cmd+Shift+Y to flip.")
    icon.run()


if __name__ == "__main__":
    run()
