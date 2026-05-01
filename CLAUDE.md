# Language Flipper Desktop — Claude Context

## What This App Is

A macOS + Windows system tray app that flips mistyped Hebrew↔English text.
User presses the hotkey → selected text (or current line) is read, characters are mapped through `en_he_map.json`, text is replaced, and the keyboard layout is switched to match.

**Hotkey:** `Cmd+Shift+Y` (Mac) / `Ctrl+Shift+Y` (Windows)
**Paywall:** 40 free lifetime flips, then Gumroad license required ($9.99/year)
**Current version:** see `flipper_daemon/version.py` — this is the single source of truth

---

## File Map

```
run.py                            — dev launcher: python run.py
flipper_daemon/
  main.py                         — entry point: tray icon, menu, flip handler, platform routing
  flipper.py                      — Hebrew↔English character mapping + flip logic (loads en_he_map.json)
  text_bridge.py                  — reads + replaces text (Mac: AX API → clipboard; Windows: clipboard; Linux: AT-SPI → clipboard)
  hotkey.py                       — global hotkey (Windows: RegisterHotKey ctypes; Mac/Linux: pynput)
  layout_switch.py                — switches keyboard layout after flip (Windows: PostMessageW; Mac: TIS/HIToolbox)
  paywall.py                      — flip counter gate + Gumroad dialogs (osascript on Mac, tkinter on Windows)
  gumroad.py                      — license key verification via Gumroad API (SSL-sensitive in frozen builds)
  storage.py                      — JSON storage at ~/.config/language-flipper/data.json
  updater.py                      — checks GitHub releases on startup, shows update in tray, downloads + installs
  onboarding.py                   — macOS ONLY: guides user through Accessibility + Input Monitoring permissions on first launch; re-prompts if permissions revoked after new binary install
  login_item.py                   — macOS ONLY: launchd plist auto-start (uses launchctl bootstrap/bootout — NOT the deprecated load/unload)
  win_login_item.py               — Windows ONLY: HKCU registry run key; self-installs exe to %LOCALAPPDATA%\Programs\Language Flipper\
  flip_log.py                     — logs every flip to ~/.config/language-flipper/flip_log.jsonl (future training data)
  version.py                      — VERSION = "x.x.x" — single source of truth, updated by release scripts
  layouts/en_he_map.json          — character mapping table

language_flipper.spec             — PyInstaller spec for Mac (.app bundle, directory build)
language_flipper_windows.spec     — PyInstaller spec for Windows (single-file exe)
language_flipper_setup.iss        — Inno Setup script → produces Language-Flipper-Setup.exe
build_mac.sh                      — builds the Mac .app and packages into a DMG
release_mac.sh                    — one command: git pull → bump version → build → gh release create
release_windows.bat               — one command (Command Prompt on Windows): git pull → bump version → PyInstaller → Inno Setup → gh release create
release_windows.sh                — same as above but for Git Bash
assets/                           — icon files (icon.png, icon.ico, icon_32.png, icon_16.png)
```

---

## Platform Differences

| Thing | macOS | Windows |
|---|---|---|
| Text read/replace | AX Accessibility API → clipboard fallback | Clipboard only (Ctrl+C/V via ctypes) |
| Hotkey | pynput | RegisterHotKey (ctypes) |
| Layout switch | TIS/HIToolbox via PyObjC | PostMessageW WM_INPUTLANGCHANGEREQUEST |
| Auto-start | launchd plist (login_item.py) | HKCU registry run key (win_login_item.py) |
| Onboarding | Full permission flow (onboarding.py) | None needed (no special permissions) |
| Dialogs | osascript | tkinter |
| Build output | Language Flipper.app → Language.Flipper.dmg | Language Flipper.exe → Language-Flipper-Setup.exe |

---

## PyInstaller Frozen Build — Path Conventions

This is a common source of bugs. Files land in different places per platform:

**Mac app bundle** (directory build):
- `sys.executable` = `Language Flipper.app/Contents/MacOS/Language Flipper`
- All datas land in `Contents/Resources/`
- So: `Path(sys.executable).parent.parent / "Resources" / "..."`

**Windows single-file exe**:
- `sys.executable` = the `.exe` file itself
- PyInstaller extracts datas to `sys._MEIPASS` at runtime
- So: `Path(sys._MEIPASS) / "..."`

Both `flipper.py` (en_he_map.json path) and `gumroad.py` (certifi SSL cert path) have platform branches for this. If you add new data files, mirror them in both `.spec` files and add path handling in the code.

**certifi** must be explicitly bundled in both specs:
```python
import certifi
datas=[(certifi.where(), "certifi")]
```

---

## Build & Release

### Mac (run on a Mac)
```bash
./release_mac.sh 0.1.70 "Fix: description"
```
Does: git pull → bumps `version.py` + `.spec` plist → `build_mac.sh` (PyInstaller + DMG) → `gh release create v0.1.70-mac`

### Windows (run in Command Prompt on Windows)
```cmd
release_windows.bat 0.1.70 "Fix: description"
```
Does: git pull → clears `build\` + `dist\` cache → bumps `version.py` + `setup.iss` → PyInstaller → Inno Setup → git commit/push → `gh release create v0.1.70-windows`

**Requires on Windows:**
- **Python 3.13 from python.org** at `C:\Users\user\AppData\Local\Programs\Python\Python313\` — MUST be the official installer, NOT uv. See "Windows Build Python" note below.
- All pip packages installed to that Python: `pip install pyinstaller pynput pystray pillow certifi pyperclip`
- Inno Setup 6, `gh` CLI (logged in), git

**CRITICAL — Windows Build Python:**
The build machine uses `uv` for development but PyInstaller MUST be run with the official python.org Python 3.13. Reason: `uv` installs a "portable" Python (`python-build-standalone`) that keeps `vcruntime140.dll` isolated in its own folder. Windows `LoadLibrary` will not find it in PyInstaller's temp `_MEI` extraction folder, causing a fatal crash on every launch. The official python.org installer registers vcruntime globally in System32, which fixes this permanently. The `release_windows.bat` hardcodes the path: `C:\Users\user\AppData\Local\Programs\Python\Python313\python.exe`.

### Release tag format
- Mac: `v0.1.70-mac` (asset: `Language.Flipper.dmg`)
- Windows: `v0.1.70-windows` (asset: `Language-Flipper-Setup.exe`)

The updater searches ALL releases (not just latest) so Mac and Windows tags coexist without interfering.

---

## Auto-Updater Flow

1. On startup, `updater.start()` spawns a background thread
2. Hits `https://api.github.com/repos/Elad-hor/language-flipper-desktop/releases`
3. Scans all non-draft/non-prerelease releases for the platform's asset (`Language-Flipper-Setup.exe` on Windows, `Language.Flipper.dmg` on Mac)
4. If a newer version is found → shows `⬆ Update available (vX.X.X) — click to install` in tray menu
5. Click → downloads to temp file → on Windows: runs installer with `/VERYSILENT /RESTARTAPPLICATIONS` (Inno Setup closes old app and restarts new one); on Mac: opens DMG for manual drag

---

## Storage

All persistent data in `~/.config/language-flipper/data.json`:
- `lifetime_flips` — flip counter for paywall
- `nags_shown` — which nag thresholds have been shown
- `license_info` — Gumroad license key + verified_at timestamp
- `onboarding_done` — whether first-launch flow completed (Mac)

---

## Gumroad License Verification

Product ID: `4ibkrpNt-FvgO4QYvaFbog==`  
Master key hash stored in `gumroad.py` (`_MASTER_HASH`) — plaintext known only to developer.  
Cache TTL: 24h. Fails open if offline and cache says premium.

---

## Mac-Specific: Onboarding & Permissions

`onboarding.run_if_needed()` is called on every startup (Darwin only).
- First launch: full wizard (Accessibility + Input Monitoring steps)
- Subsequent launches: if `onboarding_done` is set but `AXIsProcessTrusted()` returns False → permissions were revoked (new binary installed) → shows re-prompt dialog and guides through Accessibility grant only

macOS revokes Accessibility permission when the binary hash changes (i.e. on every new install). This is expected and handled.

---

## Memory System

Persistent memory files live at:
`~/.claude/projects/-home-elad-horenshtine-projects-language-flipper-desktop/memory/`

Index: `MEMORY.md` (read this first in new sessions)

---

## MCP Servers Available

- **context7** — fetch up-to-date library docs (use before assuming API syntax)
- **memory** — knowledge graph memory (entity/relation store)
- **github** — GitHub API (issues, PRs, releases, file contents)
- **playwright** — browser automation for UI testing
- **mongodb** — database queries
- **cloudflare** — Workers, KV, R2, D1, etc.

---

## Key Past Bugs (Don't Repeat)

1. **`launchctl load/unload` is deprecated on modern macOS** — always use `bootstrap`/`bootout` with `gui/<uid>` (see `login_item.py`)
2. **certifi path in frozen builds** — `certifi.where()` returns wrong path in PyInstaller. Must locate the bundled PEM manually via the platform-specific path (see `gumroad.py:_make_ssl_context`)
3. **en_he_map.json path in frozen builds** — same issue as certifi. Platform-specific branches required (see `flipper.py`)
4. **Windows `.bat` version bump** — PowerShell regex escaping in CMD is unreliable. Use `echo VERSION = "x.x.x" > flipper_daemon\version.py` instead
5. **Updater used `/releases/latest`** — breaks when Mac and Windows have separate release tags. Now uses `/releases` list and scans for platform asset
6. **`release_mac.sh` didn't bump `version.py`** — only bumped the plist. Fixed: now bumps both
7. **TIS/InputMethodKit layout switch must run on main thread** — dispatched via `NSOperationQueue.mainQueue()`
8. **Windows PyInstaller + uv = fatal DLL crash** — `uv` uses `python-build-standalone` which keeps `vcruntime140.dll` isolated. PyInstaller's `--onefile` bootloader extracts `python314.dll` to a temp `_MEI` folder but Windows `LoadLibrary` won't find vcruntime there. Symptom: `Failed to load Python DLL ... LoadLibrary: The specified module could not be found`. Fix: build with python.org Python only (see "Windows Build Python" above). Do NOT switch back to uv or directory build to solve this — the directory build installs hundreds of files and takes 2+ minutes which is unacceptable for users.
9. **Windows directory build is too slow** — PyInstaller `--onedir` bundles the entire Python runtime as separate files. Inno Setup with lzma takes 2-5 minutes to install; even zip takes over a minute. Users close the installer thinking it's frozen. Always use `--onefile` for Windows.
10. **Gumroad `_PRODUCT_ID` must be the internal ID** — `"4ibkrpNt-FvgO4QYvaFbog=="` not the permalink slug. Using the permalink causes HTTP 404.
