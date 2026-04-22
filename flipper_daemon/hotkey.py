"""
Global hotkey registration.

macOS + X11  → pynput
Wayland      → xdg-desktop-portal (GNOME 44+ / KDE 5.27+), falls back to pynput
"""

import platform
import threading
from typing import Callable

_PLATFORM = platform.system()

# Hotkey expressed in pynput format
_HOTKEY = "<ctrl>+<shift>+f"


# ---------------------------------------------------------------------------
# pynput backend (macOS + X11)
# ---------------------------------------------------------------------------

def _start_pynput(callback: Callable):
    from pynput import keyboard

    hotkey = keyboard.HotKey(keyboard.HotKey.parse(_HOTKEY), callback)

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
                "preferred-trigger": dbus.String("<Control><Shift>space", variant_level=1),
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
        return loop

    except Exception:
        return None


# ---------------------------------------------------------------------------
# Public
# ---------------------------------------------------------------------------

def register(callback: Callable):
    if _PLATFORM == "Linux":
        handle = _start_xdg_portal(callback)
        if handle:
            print("[hotkey] xdg-desktop-portal (Wayland)")
            return handle

    handle = _start_pynput(callback)
    print(f"[hotkey] pynput ({_PLATFORM})")
    return handle
