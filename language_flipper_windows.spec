# -*- mode: python ; coding: utf-8 -*-
import certifi
import sys
import os
import glob

block_cipher = None

# Find python DLL and its siblings — Python 3.14 installs them in a
# non-standard subfolder that PyInstaller's auto-scan misses.
_ver = f"{sys.version_info.major}{sys.version_info.minor}"
_dll_name = f"python{_ver}.dll"
_python_base = os.path.dirname(sys.executable)
if os.path.basename(_python_base).lower() == 'bin':
    _python_base = os.path.dirname(_python_base)
_dll_matches = glob.glob(os.path.join(_python_base, '**', _dll_name), recursive=True)
_python_binaries = []
if _dll_matches:
    _dll_dir = os.path.dirname(_dll_matches[0])
    for _f in glob.glob(os.path.join(_dll_dir, '*.dll')):
        _python_binaries.append((_f, '.'))

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=_python_binaries,
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
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico',
)
