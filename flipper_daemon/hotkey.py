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

_MAC_VK_Y = 0x10  # kVK_ANSI_Y


def _make_darwin_intercept():
    """
    Swallow Cmd+Shift+Y so it never reaches the frontmost app.

    pynput's listener only *observes* by default, so the combo passed straight
    through to whatever app was focused. Nothing has a Cmd+Shift+Y shortcut, so
    macOS played its unhandled-Command-key alert — an audible click on every
    single flip. Windows never had this because RegisterHotKey consumes the key
    (see this module's docstring).

    Safe with respect to the hotkey itself: pynput calls _handle_message()
    BEFORE the intercept (pynput/_util/darwin.py::_handler, verified against
    1.8.2), so the callback still fires. Returning None only stops the event
    propagating onwards; returning the event passes it through untouched.

    Returns None if Quartz is unavailable, in which case the listener is built
    without an intercept and behaves exactly as before.
    """
    try:
        import Quartz
    except Exception:
        return None

    def intercept(event_type, event):
        try:
            if event_type in (Quartz.kCGEventKeyDown, Quartz.kCGEventKeyUp):
                keycode = Quartz.CGEventGetIntegerValueField(
                    event, Quartz.kCGKeyboardEventKeycode
                )
                if keycode == _MAC_VK_Y:
                    flags = Quartz.CGEventGetFlags(event)
                    if (flags & Quartz.kCGEventFlagMaskCommand) and (
                        flags & Quartz.kCGEventFlagMaskShift
                    ):
                        # Suppress key-up as well as key-down, so the focused
                        # app never sees half a keystroke.
                        return None
        except Exception:
            pass
        return event

    return intercept


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

    kwargs = {"on_press": on_press, "on_release": on_release}
    if _PLATFORM == "Darwin":
        intercept = _make_darwin_intercept()
        if intercept is not None:
            # Providing an intercept also switches pynput's event tap out of
            # listen-only mode, which is what makes suppression possible.
            kwargs["darwin_intercept"] = intercept

    listener = keyboard.Listener(**kwargs)
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
