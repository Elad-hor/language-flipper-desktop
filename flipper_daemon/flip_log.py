"""
Silently logs each successful flip to a local JSONL file.
Used as the training signal for future auto-detect.
Never raises — all failures are swallowed.
"""

import json
import platform
import threading
from datetime import datetime, timezone
from pathlib import Path

_lock = threading.Lock()
_LOG_PATH = Path.home() / ".config" / "language-flipper" / "flip_log.jsonl"


def _active_app() -> str:
    try:
        if platform.system() == "Windows":
            import ctypes
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
            return buf.value
        elif platform.system() == "Darwin":
            from AppKit import NSWorkspace
            app = NSWorkspace.sharedWorkspace().frontmostApplication()
            return str(app.localizedName()) if app else ""
    except Exception:
        pass
    return ""


def log_flip(source_layout: str, char_count: int) -> None:
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "from": source_layout,
        "to": "he_il" if source_layout == "en_us" else "en_us",
        "chars": char_count,
        "app": _active_app(),
    }

    def _write():
        try:
            with _lock:
                _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
                with open(_LOG_PATH, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

    threading.Thread(target=_write, daemon=True).start()
