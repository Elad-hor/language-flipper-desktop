import threading
from pathlib import Path

import pystray
from PIL import Image, ImageDraw

import platform as _platform_mod

from .flip_engine import FlipEngine
from .text_bridge import read_and_replace
from . import hotkey as hotkey_mod
from . import storage, gumroad, paywall, updater, layout_switch, flip_log, installed_layouts

if _platform_mod.system() == "Darwin":
    from . import login_item, onboarding
elif _platform_mod.system() == "Windows":
    from . import win_login_item

_in_flight = False
_in_flight_lock = threading.Lock()
_tray_icon = None
_pending_update = None  # (version_str, download_url) when an update is available
# None, "downloading" or "failed" — shown in the tray. Clicking the update used
# to give no sign of life for the whole 19 MB download and swallowed any
# failure, so a broken update looked exactly like a dead menu item.
_update_state = None
_DOWNLOAD_PAGE = "https://languageflipper.com/"

_engine = FlipEngine(installed_layouts.get)

# flip_log and layout_switch still speak the pre-Russian layout names.
_SWITCH_ID = {"en": "en_us", "he": "he_il", "ru": "ru_ru"}


def _on_flip():
    global _in_flight
    with _in_flight_lock:
        if _in_flight:
            return
        _in_flight = True
    try:
        if not paywall.check_and_maybe_block():
            return

        caps_on = layout_switch.caps_lock_is_on()
        result = {}

        def flipped_fn(text: str) -> str:
            r = _engine.flip(text, caps_on)
            result["flip"], result["chars"] = r, len(text)
            return r.text if r else text

        replaced = read_and_replace(flipped_fn)
        flip = result.get("flip")

        if replaced and flip:
            _engine.commit()
            # A press that only moves to the next guess fixes our mistake, not
            # the user's — it doesn't cost a free flip.
            if not flip.is_cycle:
                storage.increment_lifetime_flips()
            if caps_on:
                # Caps Lock ON at hotkey time: the capitals were an accident in
                # whatever layout. Turn it off; the text can't tell us which
                # layout the user was in, so don't switch (Key Past Bug #13).
                layout_switch.turn_off_caps_lock()
            else:
                layout_switch.switch_to(_SWITCH_ID[flip.target])
            flip_log.log_flip(_SWITCH_ID[flip.source], result.get("chars", 0))
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
    from .version import VERSION
    if gumroad.get_premium_status():
        return f"Language Flipper v{VERSION} — Premium ✓"
    flips = storage.get_lifetime_flips()
    remaining = max(0, paywall.HARD_LIMIT - flips)
    return f"Language Flipper v{VERSION} — {remaining} free flips left"


def _build_menu() -> pystray.Menu:
    is_premium = gumroad.get_premium_status()
    items = [
        pystray.MenuItem(_status_label(), None, enabled=False),
        pystray.Menu.SEPARATOR,
    ]

    if _pending_update:
        version, _ = _pending_update
        if _update_state == "downloading":
            item = pystray.MenuItem(f"⬇ Downloading update (v{version})…", None, enabled=False)
        elif _update_state == "failed":
            item = pystray.MenuItem("Update failed — click to download from the website", _open_download_page)
        else:
            item = pystray.MenuItem(f"⬆ Update available (v{version}) — click to install", _do_update)
        items += [item, pystray.Menu.SEPARATOR]

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
    if not _tray_icon:
        return

    def _do():
        try:
            _tray_icon.menu = _build_menu()
        except Exception:
            pass

    # Assigning .menu makes pystray call update_menu(), and its macOS backend
    # implements that as AppKit's setMenu_ (pystray/_darwin.py::_update_menu).
    # AppKit must only be touched from the main thread, but this function is
    # called from background threads — the update checker and the hotkey
    # handler — where the update silently did nothing. That is why the
    # "Update available" item never appeared on macOS, and why the free-flip
    # count never moved. Same trap as the TIS layout switch; see
    # layout_switch._switch_mac and Key Past Bug #7.
    if _platform_mod.system() == "Darwin":
        try:
            from Foundation import NSOperationQueue
            NSOperationQueue.mainQueue().addOperationWithBlock_(_do)
            return
        except Exception:
            pass  # fall through to a direct call rather than skipping the update

    _do()


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
    global _pending_update, _update_state
    _pending_update = (version, url)
    _update_state = None  # a new version gets a fresh try after a failure
    _refresh_tray_menu()


def _open_download_page(_icon=None, _item=None):
    import webbrowser
    webbrowser.open(_DOWNLOAD_PAGE)


def _do_update(_icon=None, _item=None):
    global _update_state
    if _update_state == "downloading":
        return
    _update_state = "downloading"
    _refresh_tray_menu()

    def _run():
        global _update_state
        try:
            _, url = _pending_update
            updater.download_and_run(url)
            # Stop the tray on all platforms.
            # On Windows this releases the file lock so the installer can overwrite the exe.
            # The installer + relaunch are scheduled via a background cmd (see updater.py).
            if _tray_icon:
                _tray_icon.stop()
        except Exception as e:
            # download_and_run has already logged the cause to lf-update.log.
            print(f"[update] failed: {e}")
            _update_state = "failed"
            _refresh_tray_menu()
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
    installed_layouts.warm_up()

    hotkey_handle = hotkey_mod.register(_on_flip)

    hotkey = "Cmd+Shift+Y" if _platform_mod.system() == "Darwin" else "Ctrl+Shift+Y"
    print(f"[language-flipper] running. Press {hotkey} to flip.")
    icon.run()

    # icon.run() blocks until Quit (or _do_update stopping the tray). Wake the
    # update checker so it exits its sleep instead of being killed mid-request.
    updater.stop()

    # Stop the macOS hotkey supervisor too, so it cannot rebuild a listener
    # while the app is on its way out.
    if hasattr(hotkey_handle, "stop"):
        try:
            hotkey_handle.stop()
        except Exception:
            pass


if __name__ == "__main__":
    run()
