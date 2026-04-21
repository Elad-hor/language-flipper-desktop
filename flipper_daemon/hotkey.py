"""
Global hotkey registration.

Strategy:
  1. xdg-desktop-portal GlobalShortcuts  — Wayland-native, GNOME 44+ / KDE 5.27+
  2. pynput                               — X11 / XWayland fallback

Only one backend is activated at runtime.
"""

import threading
from typing import Callable

# Default hotkey expressed per-backend
_XDG_SHORTCUT_ID = "flip"
_XDG_SHORTCUT_DESC = "Flip keyboard layout"
_XDG_SHORTCUT_TRIGGER = "<Control><Shift>space"   # Wayland portal format
_PYNPUT_HOTKEY = "<ctrl>+<shift>+space"            # pynput format


# ---------------------------------------------------------------------------
# pynput backend (X11 / XWayland)
# ---------------------------------------------------------------------------

def _start_pynput(callback: Callable):
    from pynput import keyboard

    hotkey = keyboard.HotKey(
        keyboard.HotKey.parse(_PYNPUT_HOTKEY),
        callback,
    )

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
    return listener


# ---------------------------------------------------------------------------
# xdg-desktop-portal backend (Wayland)
# ---------------------------------------------------------------------------

def _start_xdg_portal(callback: Callable):
    """
    Register a global shortcut via xdg-desktop-portal GlobalShortcuts interface.
    Requires: portal version ≥ 1, GNOME 44+ or KDE Plasma 5.27+.
    Returns a handle object or None if unavailable.
    """
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
        shortcuts_iface = dbus.Interface(
            portal, "org.freedesktop.portal.GlobalShortcuts"
        )

        # Request token
        token = "language_flipper_1"
        request_path = shortcuts_iface.CreateSession(
            {"handle_token": dbus.String(token, variant_level=1)}
        )

        shortcuts = [
            (
                _XDG_SHORTCUT_ID,
                {
                    "description": dbus.String(_XDG_SHORTCUT_DESC, variant_level=1),
                    "preferred-trigger": dbus.String(_XDG_SHORTCUT_TRIGGER, variant_level=1),
                },
            )
        ]

        def on_activated(session_handle, shortcut_id, timestamp, options):
            if shortcut_id == _XDG_SHORTCUT_ID:
                callback()

        bus.add_signal_receiver(
            on_activated,
            signal_name="Activated",
            dbus_interface="org.freedesktop.portal.GlobalShortcuts",
        )

        shortcuts_iface.BindShortcuts(request_path, shortcuts, "", {})

        loop = GLib.MainLoop()
        t = threading.Thread(target=loop.run, daemon=True)
        t.start()
        return loop

    except Exception:
        return None


# ---------------------------------------------------------------------------
# Public
# ---------------------------------------------------------------------------

def register(callback: Callable, prefer_portal: bool = True):
    """
    Register the global hotkey. Tries xdg-portal first, falls back to pynput.
    Returns the backend handle (keep alive for the process lifetime).
    """
    if prefer_portal:
        handle = _start_xdg_portal(callback)
        if handle is not None:
            print("[hotkey] using xdg-desktop-portal (Wayland)")
            return handle

    handle = _start_pynput(callback)
    print("[hotkey] using pynput (X11)")
    return handle
