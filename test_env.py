"""
Run after installing deps to verify the environment.
    python3 test_env.py
"""

import platform
import sys

PLATFORM = platform.system()
OK   = "\033[32m✓\033[0m"
FAIL = "\033[31m✗\033[0m"

def check(label, fn):
    try:
        result = fn()
        print(f"  {OK}  {label}" + (f" — {result}" if result else ""))
        return True
    except Exception as e:
        print(f"  {FAIL}  {label} — {e}")
        return False

print(f"\n=== Language Flipper Desktop — environment check ({PLATFORM}) ===\n")

print("Python packages:")
check("pynput",    lambda: __import__("pynput") and "ok")
check("pystray",   lambda: __import__("pystray") and "ok")
check("pyperclip", lambda: __import__("pyperclip") and "ok")
check("pyautogui", lambda: __import__("pyautogui") and "ok")
check("PIL",       lambda: __import__("PIL") and "ok")

if PLATFORM == "Darwin":
    print("\nmacOS Accessibility:")
    check("ApplicationServices",
          lambda: __import__("ApplicationServices") and "ok")
    def ax_check():
        import ApplicationServices as AS
        system = AS.AXUIElementCreateSystemWide()
        err, focused = AS.AXUIElementCopyAttributeValue(
            system, AS.kAXFocusedUIElementAttribute, None
        )
        return f"focused element: {focused is not None}"
    check("AX focused element", ax_check)

elif PLATFORM == "Linux":
    print("\nLinux AT-SPI:")
    check("pyatspi", lambda: __import__("pyatspi") and "ok")
    def atspi_check():
        import pyatspi
        desktop = pyatspi.Registry.getDesktop(0)
        apps = [a.name for a in desktop if a]
        return f"{len(apps)} apps: {', '.join(apps[:5])}"
    check("AT-SPI desktop", atspi_check)

    import subprocess
    check("xdotool", lambda: subprocess.check_output(
        ["which", "xdotool"]).decode().strip())

print("\nFlip logic:")
sys.path.insert(0, ".")
def flip_check():
    from flipper_daemon.flipper import flip_text, detect_layout
    sample = "slkd"
    layout = detect_layout(sample)
    flipped = flip_text(sample)
    return f"'{sample}' ({layout}) → '{flipped}'"
check("EN→HE", flip_check)

def flip_back_check():
    from flipper_daemon.flipper import flip_text
    return f"'שלד' → '{flip_text('שלד')}'"
check("HE→EN", flip_back_check)

print()
