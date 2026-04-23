"""
Global hotkey registration.

Windows  → RegisterHotKey (Win32 via ctypes) — suppresses the key combo
           so it never reaches apps or the language switcher. No extra deps.
macOS    → pynput
Wayland  → xdg-desktop-portal, falls back to pynput
X11      → pynput
"""

import platform
import threading
from typing import Callable

_PLATFORM = platform.system()

# Hotkey in pynput format (macOS + Linux)
_PYNPUT_HOTKEY = "<cmd>+<shift>+y" if _PLATFORM == "Darwin" else "<ctrl>+<shift>+y"


# ---------------------------------------------------------------------------
# Windows — RegisterHotKey (ctypes, no extra deps)
# Suppresses the hotkey before any app or language switcher sees it.
# ---------------------------------------------------------------------------

def _start_windows_hotkey(callback: Callable):
    import ctypes
    import ctypes.wintypes

    _WM_HOTKEY   = 0x0312
    _MOD_CONTROL = 0x0002
    _MOD_SHIFT   = 0x0004
    _MOD_NOREPEAT= 0x4000   # don't fire repeatedly while held
    _HOTKEY_ID   = 9001
    _VK_Y        = ord('Y')

    def loop():
        ok = ctypes.windll.user32.RegisterHotKey(
            None,
            _HOTKEY_ID,
            _MOD_CONTROL | _MOD_SHIFT | _MOD_NOREPEAT,
            _VK_Y,
        )
        if not ok:
            print("[hotkey] RegisterHotKey failed — falling back to pynput")
            _start_pynput(callback)
            return

        print("[hotkey] RegisterHotKey (Windows) — Ctrl+Shift+Y")

        msg = ctypes.wintypes.MSG()
        while ctypes.windll.user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            if msg.message == _WM_HOTKEY and msg.wParam == _HOTKEY_ID:
                callback()
            ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
            ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))

        ctypes.windll.user32.UnregisterHotKey(None, _HOTKEY_ID)

    t = threading.Thread(target=loop, daemon=True)
    t.start()
    return t


# ---------------------------------------------------------------------------
# pynput backend (macOS + X11/Linux)
# ---------------------------------------------------------------------------

def _start_pynput(callback: Callable):
    from pynput import keyboard

    hotkey = keyboard.HotKey(keyboard.HotKey.parse(_PYNPUT_HOTKEY), callback)

    def on_press(key):
        try:
            hotkey.press(listener.canonical(key))
        except Exception:
            pass

    def on_release(key):
        try:
            hotkey.release(listener.canonical(key))
        except Exception:
            pass

    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.daemon = True
    listener.start()
    print(f"[hotkey] pynput ({_PLATFORM})")
    return listener


# ---------------------------------------------------------------------------
# xdg-desktop-portal backend (Wayland only)
# ---------------------------------------------------------------------------

def _start_xdg_portal(callback: Callable):
    try:
        import dbus
        import dbus.mainloop.glib
        from gi.repository import GLib

        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        bus = dbus.SessionBus()
        portal = bus.get_object(
            "org.freedesktop.portal.Desktop",
            "/org/freedesktop/portal/desktop",
        )
        iface = dbus.Interface(portal, "org.freedesktop.portal.GlobalShortcuts")
        token = "language_flipper_1"
        request_path = iface.CreateSession(
            {"handle_token": dbus.String(token, variant_level=1)}
        )
        shortcuts = [(
            "flip",
            {
                "description": dbus.String("Flip keyboard layout", variant_level=1),
                "preferred-trigger": dbus.String("<Control><Shift>y", variant_level=1),
            },
        )]

        def on_activated(session_handle, shortcut_id, timestamp, options):
            if shortcut_id == "flip":
                callback()

        bus.add_signal_receiver(
            on_activated,
            signal_name="Activated",
            dbus_interface="org.freedesktop.portal.GlobalShortcuts",
        )
        iface.BindShortcuts(request_path, shortcuts, "", {})

        loop = GLib.MainLoop()
        t = threading.Thread(target=loop.run, daemon=True)
        t.start()
        print("[hotkey] xdg-desktop-portal (Wayland)")
        return loop

    except Exception:
        return None


# ---------------------------------------------------------------------------
# Public
# ---------------------------------------------------------------------------

def register(callback: Callable):
    if _PLATFORM == "Windows":
        return _start_windows_hotkey(callback)

    if _PLATFORM == "Linux":
        handle = _start_xdg_portal(callback)
        if handle:
            return handle

    return _start_pynput(callback)
