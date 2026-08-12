"""
SSL context that actually works inside a PyInstaller bundle.

`certifi.where()` returns a path inside a site-packages directory that does not
exist in a frozen build, so the bundled cacert.pem has to be located by hand —
and the location differs per platform. This is Key Past Bug #2.

This lived only in gumroad.py. updater.py used plain urllib with no context, so
inside the Mac app bundle it had no CA certificates at all and every update
check failed with:

    [SSL: CERTIFICATE_VERIFY_FAILED] unable to get local issuer certificate

…silently, behind a bare `except Exception: pass`, from the day it was written.
Confirmed from a user log on 2026-08-12. Hence one shared implementation: any
new caller gets the working behaviour by default, and a future fix lands in one
place.

Both .spec files already bundle certifi — keep it that way.
"""

import ssl
import sys
from pathlib import Path


def make_ssl_context():
    """
    An SSLContext trusting the bundled CA list, or None if it can't be built
    (callers then fall back to urllib's default, which is right when running
    from source).
    """
    if getattr(sys, "frozen", False):
        import platform

        if platform.system() == "Darwin":
            # Mac .app: executable is in Contents/MacOS/, datas in Contents/Resources/
            pem = Path(sys.executable).parent.parent / "Resources" / "certifi" / "cacert.pem"
        else:
            # Windows one-file exe: PyInstaller extracts datas to sys._MEIPASS
            base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
            pem = base / "certifi" / "cacert.pem"
        if pem.exists():
            return ssl.create_default_context(cafile=str(pem))

    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return None


# Built once at import; the CA list doesn't change while the app runs.
SSL_CONTEXT = make_ssl_context()
