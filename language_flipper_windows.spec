# -*- mode: python ; coding: utf-8 -*-
import certifi
import sys
import os

block_cipher = None

# Explicitly bundle the Python DLL — required for single-file builds on some
# Python versions (e.g. 3.14) where PyInstaller doesn't include it automatically.
_dll_name = f'python{sys.version_info.major}{sys.version_info.minor}.dll'
_dll_path = None
for _d in [os.path.dirname(sys.executable), sys.prefix, os.path.join(sys.prefix, 'DLLs')]:
    _candidate = os.path.join(_d, _dll_name)
    if os.path.exists(_candidate):
        _dll_path = _candidate
        break
_extra_binaries = [(_dll_path, '.')] if _dll_path else []

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=_extra_binaries,
    datas=[
        ('assets', 'assets'),
        ('flipper_daemon/layouts', 'layouts'),
        (certifi.where(), 'certifi'),
    ],
    hiddenimports=[
        'pynput.keyboard._win32',
        'pynput.mouse._win32',
        'pystray._win32',
        'PIL._tkinter_finder',
        'pyperclip',
        'winreg',
        'certifi',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Language Flipper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico',  # remove this line if you don't have icon.ico yet
)
