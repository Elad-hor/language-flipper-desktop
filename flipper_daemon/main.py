import threading
from pathlib import Path

import pystray
from PIL import Image, ImageDraw

import platform as _platform_mod

from .flipper import flip_text, detect_layout
from .text_bridge import read_and_replace
from . import hotkey as hotkey_mod
from . import storage, gumroad, paywall, updater, layout_switch, flip_log

if _platform_mod.system() == "Darwin":
    from . import login_item, onboarding
elif _platform_mod.system() == "Windows":
    from . import win_login_item

_in_flight = False
_in_flight_lock = threading.Lock()
_tray_icon = None
_pending_update = None  # (version_str, download_url) when an update is available

# Captures flip direction inside the flipped_fn closure so main can act on it
_last_flip_info: dict = {"source": None, "chars": 0}


def _flip_and_track(text: str) -> str:
    _last_flip_info["source"] = detect_layout(text)
    _last_flip_info["chars"] = len(text)
    return flip_text(text)


def _on_flip():
    global _in_flight
    with _in_flight_lock:
        if _in_flight:
            return
        _in_flight = True
    try:
        if not paywall.check_and_maybe_block():
            return

        replaced = read_and_replace(_flip_and_track)

        if replaced:
            storage.increment_lifetime_flips()
            source = _last_flip_info.get("source")
            if source:
                target = "he_il" if source == "en_us" else "en_us"
                layout_switch.switch_to(target)
                flip_log.log_flip(source, _last_flip_info.get("chars", 0))
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

    if _pending_update:
        version, _ = _pending_update
        items += [
            pystray.MenuItem(f"⬆ Update available (v{version}) — click to install", _do_update),
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

    if _platform_mod.system() == "Darwin":
        auto = login_item.is_enabled()
        items.append(pystray.MenuItem(
            "✓ Start at Login" if auto else "Start at Login",
            _toggle_login_item,
        ))
    elif _platform_mod.system() == "Windows":
        auto = win_login_item.is_enabled()
        items.append(pystray.MenuItem(
            "✓ Start at Login" if auto else "Start at Login",
            _toggle_login_item,
        ))

    items.append(pystray.MenuItem("Quit", lambda icon, _: icon.stop()))
    return pystray.Menu(*items)


def _refresh_tray_menu():
    if _tray_icon:
        _tray_icon.menu = _build_menu()


def _deactivate(_icon=None, _item=None):
    gumroad.deactivate()
    _refresh_tray_menu()


def _toggle_login_item(_icon=None, _item=None):
    if _platform_mod.system() == "Darwin":
        if login_item.is_enabled():
            login_item.disable()
        else:
            login_item.enable()
    elif _platform_mod.system() == "Windows":
        if win_login_item.is_enabled():
            win_login_item.disable()
        else:
            win_login_item.enable()
    _refresh_tray_menu()


def _on_update_available(version: str, url: str):
    global _pending_update
    _pending_update = (version, url)
    _refresh_tray_menu()


def _do_update(_icon=None, _item=None):
    import subprocess

    def _run():
        try:
            _, url = _pending_update
            updater.download_and_run(url)
            if _tray_icon:
                _tray_icon.stop()
        except Exception:
            pass
    threading.Thread(target=_run, daemon=True).start()


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

    if _platform_mod.system() == "Darwin":
        import threading as _t
        _t.Thread(target=onboarding.run_if_needed, daemon=True).start()

    updater.start(_on_update_available)

    _hotkey_handle = hotkey_mod.register(_on_flip)  # noqa: F841

    hotkey = "Cmd+Shift+Y" if _platform_mod.system() == "Darwin" else "Ctrl+Shift+Y"
    print(f"[language-flipper] running. Press {hotkey} to flip.")
    icon.run()


if __name__ == "__main__":
    run()
