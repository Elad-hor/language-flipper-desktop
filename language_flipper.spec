# -*- mode: python -*-
# PyInstaller spec — builds Language Flipper as a macOS .app bundle.
# Run: pyinstaller language_flipper.spec

from PyInstaller.utils.hooks import collect_data_files
import sys

a = Analysis(
    ["run.py"],
    pathex=["."],
    binaries=[],
    datas=[
        ("flipper_daemon/layouts/en_he_map.json", "flipper_daemon/layouts"),
        ("assets/icon.png",   "assets"),
        ("assets/icon_32.png","assets"),
        ("assets/icon_16.png","assets"),
    ],
    hiddenimports=[
        "pynput.keyboard._darwin",
        "pynput.mouse._darwin",
        "pystray._darwin",
        "PIL._imaging",
        "AppKit",
        "ApplicationServices",
        "Quartz",
        "CoreFoundation",
    ],
    hookspath=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Language Flipper",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # no terminal window
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="Language Flipper",
)

app = BUNDLE(
    coll,
    name="Language Flipper.app",
    icon=None,          # set to "assets/icon.icns" once you convert the PNG
    bundle_identifier="com.languageflipper.desktop",
    info_plist={
        "CFBundleShortVersionString": "0.1.0",
        "CFBundleVersion":            "1",
        "NSHighResolutionCapable":    True,
        # Accessibility permission description shown in System Settings
        "NSAccessibilityUsageDescription":
            "Language Flipper needs Accessibility access to read and replace text in other apps.",
        # Input monitoring permission description
        "NSInputMonitoringUsageDescription":
            "Language Flipper needs Input Monitoring access to detect the global flip hotkey.",
        "LSUIElement": True,   # hides from Dock — tray-only app
        "LSBackgroundOnly": False,
    },
)
