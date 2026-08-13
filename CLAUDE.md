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

**The website updates itself on release — do NOT hand-edit download URLs.** `DownloadRow.astro`
gets its hrefs from `site/src/lib/releases.ts`, which resolves them from the releases API at
build time, and `deploy.yml` triggers on `release: published`. Verified 2026-08-12: publishing
`v0.1.105-mac` had the live button updated ~20s later with no manual step. Do not reintroduce a
hardcoded `macHref`/`winHref`, and do not use GitHub's `/releases/latest/download/<asset>`
shortcut — `latest` is one pointer across all releases and the `-mac`/`-windows` tags interleave,
so it 404s (same trap as Key Past Bug #5).

`build_mac.sh` retries `create-dmg` up to 3× with a force-detach between attempts: its final
unmount fails with "resource busy" when Finder/Spotlight holds the volume, and **no DMG is
produced** when that happens. It also runs PyInstaller with `--clean --noconfirm`, matching
Windows.

### Release tag format
- Mac: `v0.1.70-mac` (asset: `Language.Flipper.dmg`)
- Windows: `v0.1.70-windows` (asset: `Language-Flipper-Setup.exe`)

The updater searches ALL releases (not just latest) so Mac and Windows tags coexist without interfering.

---

## Auto-Updater Flow

**Check cadence:** `updater.start()` runs a background loop that checks immediately and then
every `_CHECK_INTERVAL_SECONDS` (6h) — not once at startup, which left users who never reboot
stranded on old versions. It only fires `on_available` when the answer *changes*, so the tray
isn't rebuilt every interval for an update the user already declined. `updater.stop()` (called
after `icon.run()` returns) wakes the sleeping thread so it exits cleanly.

**macOS install is now in-place** (`updater._install_macos`), matching Windows. It writes a
detached shell script that waits for the app to quit, mounts the DMG on a private mountpoint
(`-nobrowse` + explicit `-mountpoint`, so it can't collide with a leftover volume), replaces the
bundle, strips `com.apple.quarantine` (required — the DMG is an internet download and the app is
unsigned, so Gatekeeper would block the copy), and relaunches. **Invariant: the old bundle is
moved aside, not deleted, and restored if the copy fails; every failure path falls back to
opening the DMG.** A failed update must never leave the user with no app. Log:
`$TMPDIR/lf-update.log`.

1. On startup, `updater.start()` spawns a background thread
2. Hits `https://api.github.com/repos/Elad-hor/language-flipper-desktop/releases`
3. Scans all non-draft/non-prerelease releases for the platform's asset (`Language-Flipper-Setup.exe` on Windows, `Language.Flipper.dmg` on Mac)
4. If a newer version is found → shows `⬆ Update available (vX.X.X) — click to install` in tray menu
5. Click → downloads installer to temp → app stops (releases file lock) → cmd chain runs:
   - `ping -n 2` (wait for app to fully exit)
   - installer `/VERYSILENT`
   - `ping -n 15` (buffer after install)
   - `wscript /B launch.vbs` — VBScript uses `Shell.Run` to relaunch, identical to double-clicking
6. On Mac: opens DMG for manual drag

**Why VBScript for relaunch (Windows):** `start ""` and `explorer` from a cmd chain inherit a stripped environment that causes PyInstaller's `LoadLibrary` to fail finding python313.dll. `Shell.Run` via wscript launches in the full user desktop context — same as double-clicking — bypassing the DLL search path issue entirely. Do NOT replace this with `start`, `explorer`, PowerShell `Start-Process`, Task Scheduler, or any other mechanism — VBScript Shell.Run is confirmed working (verified v0.1.105).

---

## Flip Logic & Character Mapping

### en_he_map.json — design rules
Each entry maps one English character to one Hebrew character. The mapping is used in both directions:
- `_EN2HE` — built from the `en` field (en→he flip)
- `_HE2EN` — built from the `he` field (he→en flip). **Last write wins** — if two entries share the same `he` value, the second overwrites the first.

**Why `<` and `>` are NOT in the map:**
`<` (Shift+`,`) and `>` (Shift+`.`) produce the same character in **both** Hebrew and English layouts. They are layout-invariant — there is no mistyping scenario where a user typed `>` and meant something else. Having them in the map caused a last-write-wins collision: ץ→`>` and ת→`<` instead of the correct ץ→`.` and ת→`,`. They were removed in v0.1.99.

### Layout switch after flip (`main.py: _on_flip`)
After a successful flip, the app switches the OS keyboard layout to match the flipped text. The source layout is inferred from text content by `detect_layout()` (Hebrew chars vs Latin chars score).

**Caps Lock special case — full reasoning:**

Israeli users use Alt+Shift to switch layouts. The hotkey (Ctrl+Shift+Y) is only pressed to flip mistyped text — never as a layout switcher.

When Caps Lock is ON at hotkey time, there is exactly one scenario: the user typed in the wrong layout while Caps Lock was on. In both cases below, the correct action is identical:
- Hebrew layout + Caps Lock on → produces English capitals (Caps Lock is layout-invariant: it always outputs the Latin alphabet layer regardless of layout)
- English layout + Caps Lock on → produces English capitals

After flip in both cases:
1. Text is correctly flipped ✓
2. **Turn off Caps Lock** — always correct; the flip corrected the text, Caps Lock is no longer needed
3. **Skip layout switch** — we cannot reliably infer from text content whether the user was in Hebrew or English layout (both produce English capitals with Caps Lock on). Auto-switching risks putting them in the wrong layout. Skipping is safe: worst case they need one Alt+Shift. This is implemented in `layout_switch.py`: `caps_lock_is_on()` + `turn_off_caps_lock()`.

When Caps Lock is OFF, layout switch fires normally.

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

**Granting permission mid-run is the normal case, and three things make it work:**

1. `hotkey._supervise` (macOS only) rebuilds the pynput listener whenever it is
   not alive. A listener is a one-shot — `CGEventTapCreate` returns NULL when
   untrusted and pynput returns straight out of its run-loop thread with
   `start()` reporting no error — so without supervision the app runs deaf for
   its whole lifetime. **Never go back to a single fire-and-forget
   `register()` on macOS.**
2. `onboarding._clear_stale_tcc_entry()` runs `tccutil reset` for
   `Accessibility` and `ListenEvent` before re-prompting. TCC ties an unsigned
   app's grant to the binary, so after an in-place update the old row keeps the
   app's name and its tick while no longer matching — the user re-ticks a box
   that is already ticked and nothing changes. It is only ever called after
   `AXIsProcessTrusted()` returned False, so no working grant is at risk.
3. `onboarding._finish()` checks `AXIsProcessTrusted()` before claiming
   success, and does **not** set `onboarding_done` without it.

`_finish()` no longer exits the app or asks the user to quit and reopen — the
supervisor picks up the grant within `_SUPERVISOR_POLL_SECONDS` (5s).

Tests: `python3 tests/test_hotkey_supervisor.py`, `python3 tests/test_onboarding_recheck.py`
(stdlib `unittest`, no deps, runs anywhere).

---

## Memory System

Persistent memory files live at:
`~/.claude/projects/-home-elad-horenshtine-projects-language-flipper-desktop/memory/`

Index: `MEMORY.md` (read this first in new sessions)

---

## Marketing Site (languageflipper.com)

The marketing site is a **static [Astro](https://astro.build) site in `site/`**, replacing the original
WordPress + Elementor build. It is **live and prompt-editable**: change a component/page, push to `main`,
and it deploys automatically.

**Hosting moved off Hostinger to a Cloudflare Worker on 2026-08-13.** Migration notes and the rollback
path are in `site/MIGRATION.md`.

- **Stack:** Astro (static output), CSS tokens (`site/src/styles/tokens.css` — brand palette + Poppins),
  i18n via `site/src/i18n/` (`en.json`/`he.json` + `ui.ts`'s `t(lang,key)`/`dir(lang)`).
- **Pages (13):** 7 English + a 6-page Hebrew RTL mirror under `/he/…` (literal Hebrew dir names, e.g.
  `site/src/pages/he/בית/index.astro`). `/solutions/` is **EN-only** and is the **FAQ page** (real Q&A +
  FAQPage schema). **Standing rule: every content/design change goes into BOTH the EN and HE versions.**

### Hosting: Cloudflare Worker (not Pages, not Hostinger)

Cloudflare has put Pages into maintenance and routes new Git-connected projects through **Workers**, so
the site is a Worker serving **Static Assets**, configured by `site/wrangler.jsonc`.

- `site/worker/index.ts` — serves `/contact` and `/contact.php`, delegates everything else to `ASSETS`.
- **Deploy = Workers Builds on push to `main`.** Dashboard settings that must match the config:
  **Path `/site`** (the root-directory field — it is called "Path" and hides under *Advanced settings*),
  build `npm run build`, deploy `npx wrangler deploy`.
- **`compatibility_date` must not exceed the workerd build in the installed wrangler**, or `wrangler dev`
  refuses to start.
- The domain is attached by **zone routes** (`languageflipper.com/*`, `www.languageflipper.com/*`), NOT a
  Custom Domain. That is deliberate: the A record still points at Hostinger (`185.224.137.92`, proxied),
  so **rollback is deleting the two routes** — instant, no DNS propagation.

### Two Cloudflare traps that cost hours

1. **Plain-text vars belong in `wrangler.jsonc`, not the dashboard.** `wrangler deploy` treats the config
   as the source of truth and **replaces all plain vars**, so dashboard-set values vanish on the next
   push. Secrets survive. `MAILGUN_DOMAIN` and `CONTACT_FROM` live in the config for this reason.
2. **There are TWO "Variables and Secrets" screens** — one for the *build* job, one for the *Worker
   runtime*. The one reachable from Settings is the **build** one, which the Worker cannot read. Setting
   `MAILGUN_API_KEY` there looks right and does nothing. Use
   `npx wrangler secret put MAILGUN_API_KEY --name language-flipper-desktop` (no folder needed) or the
   API. This wasted two rounds of "the key must be wrong".

### Contact form (no PHP any more)

`site/worker/contact-handler.ts` replaces `contact.php`. Same behaviour: POST-only, honeypot, required
email/company, CR/LF header-injection guard, and a same-site-path-only redirect that returns Hebrew
submissions to the Hebrew page where `ContactForm.astro` reveals the banner on `?sent=1`.

- Sends via **Mailgun** (`mg.languageflipper.com`, US region, SPF+DKIM verified) or **Resend** — whichever
  is configured, Mailgun first. `MAILGUN_API_KEY` is a **runtime secret**.
- **Do not use a Mailgun sandbox domain in production.** Gmail accepts sandbox mail then flags
  `DMARC:Quarantine` — it lands in spam. Verifying `mg.languageflipper.com` fixed it (`2.0.0 OK`).
- Answers on **both** `/contact` and `/contact.php`; the old route stops cached pages 404ing.
- Failures are self-describing (`no mail provider configured (mailgun_key=… )`, `provider rejected
  (Mailgun 401)`). **Don't collapse those back into a generic "Send failed".**
- Tests: `site/capture/scripts/verify-contact.mjs` (30 assertions, `node --experimental-strip-types`).

### Redirects, headers, download links

- `site/public/_redirects` and `site/public/_headers` replace the Apache `.htaccess` (Workers Static
  Assets honours both). **Do not add a `/*` rule to `_headers`:** Cloudflare *combines* matching rules
  rather than letting the specific one win, so `/*` plus `/_astro/*` emitted two `max-age` values and
  browsers took the first — assets were never cached. Cloudflare already defaults to
  `public, max-age=0, must-revalidate`, so only the `/_astro/*` immutable rule is needed.
- **Download URLs are resolved from the GitHub releases API at build time** (`site/src/lib/releases.ts`).
  Never hardcode them again, and never use `/releases/latest/download/<asset>` — `latest` is one pointer
  across all releases and the `-mac`/`-windows` tags interleave, so it 404s (Key Past Bug #5).
  `.github/workflows/rebuild-site-on-release.yml` pushes an empty commit when a release is published,
  because Workers Builds only builds on push and the release scripts push *before* creating the release.

### SEO / analytics

All injected by `BaseLayout` via `site/src/components/Seo.astro`: per-page title/description, canonical,
**hreflang** (EN↔HE pairs in `site/src/i18n/routes.ts`), Open Graph + Twitter, **GA4** (`GT-5D9377V7` →
`G-2CP4BEC4B8`) and **Microsoft Clarity** (`wrfoldcd1d`) (IDs in `site/src/seo-config.ts`), plus
**JSON-LD** built by `site/src/schema.ts`. Also `@astrojs/sitemap` → `/sitemap-index.xml`,
`site/public/robots.txt`, `llms.txt`, `favicon.svg`.

### Components worth knowing

- **Try-It widget:** `site/src/components/TryItWidget.astro` — inlined char map is a copy of
  `flipper_daemon/layouts/en_he_map.json` and can drift.
- **Mobile nav:** `site/src/components/Nav.astro` — animated hamburger.
- See also the install-warning components and responsive audit described above.

### Verification tooling (`site/capture/scripts/`)

- `verify-worker.mjs` — builds, runs the Worker locally, checks pages, the ported 301s, exact cache
  headers and the contact routes (28 assertions).
- `verify-install-help.mjs` — 57 assertions; point it at localhost, workers.dev or the live domain.
- `verify-contact.mjs`, `responsive-audit.mjs`, `verify-reduced-motion.mjs`.
- Scripts spawn servers as **foreground children** — the sandbox reaps backgrounded ones, so never
  background `npm run preview` or `wrangler dev`.

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
2. **certifi path in frozen builds** — `certifi.where()` returns wrong path in PyInstaller. Must locate
   the bundled PEM manually via the platform-specific path. Now lives in **`flipper_daemon/certs.py`**
   (`SSL_CONTEXT`); `gumroad.py` and `updater.py` both import it. **Any new code doing HTTPS must use it.**
   `updater.py` originally used plain `urllib` with no context, so inside the Mac app bundle it had no CA
   certificates and *every* update check failed with `CERTIFICATE_VERIFY_FAILED` — silently, behind a bare
   `except Exception: pass`. The macOS updater therefore never worked at all from the day it was written
   until 2026-08-12. Note `urllib.request.urlretrieve()` **cannot** take an SSL context — use `urlopen` +
   `shutil.copyfileobj`. The updater now logs every check/download outcome to `$TMPDIR/lf-update.log`;
   don't reintroduce silent exception swallowing there.
3. **en_he_map.json path in frozen builds** — same issue as certifi. Platform-specific branches required (see `flipper.py`)
4. **Windows `.bat` version bump** — PowerShell regex escaping in CMD is unreliable. Use `echo VERSION = "x.x.x" > flipper_daemon\version.py` instead
5. **Updater used `/releases/latest`** — breaks when Mac and Windows have separate release tags. Now uses `/releases` list and scans for platform asset
6. **`release_mac.sh` didn't bump `version.py`** — only bumped the plist. Fixed: now bumps both
7. **TIS/InputMethodKit layout switch must run on main thread** — dispatched via `NSOperationQueue.mainQueue()`
8. **Windows PyInstaller + uv = fatal DLL crash** — `uv` uses `python-build-standalone` which keeps `vcruntime140.dll` isolated. PyInstaller's `--onefile` bootloader extracts `python314.dll` to a temp `_MEI` folder but Windows `LoadLibrary` won't find vcruntime there. Symptom: `Failed to load Python DLL ... LoadLibrary: The specified module could not be found`. Fix: build with python.org Python only (see "Windows Build Python" above). Do NOT switch back to uv or directory build to solve this — the directory build installs hundreds of files and takes 2+ minutes which is unacceptable for users.
9. **Windows directory build is too slow** — PyInstaller `--onedir` bundles the entire Python runtime as separate files. Inno Setup with lzma takes 2-5 minutes to install; even zip takes over a minute. Users close the installer thinking it's frozen. Always use `--onefile` for Windows.
10. **Gumroad `_PRODUCT_ID` must be the internal ID** — `"4ibkrpNt-FvgO4QYvaFbog=="` not the permalink slug. Using the permalink causes HTTP 404.
11. **Windows auto-update relaunch — never use `start`/`explorer` from cmd chain** — These inherit a broken DLL search path. Use VBScript `Shell.Run` (see updater.py) — confirmed working in v0.1.105. `RestartApplications=yes` in Inno Setup also causes a premature double-launch — keep it removed from setup.iss. Do NOT switch to Task Scheduler or ShellExecute — VBScript is the proven solution.
12. **`<` and `>` in en_he_map.json caused wrong he→en flips** — Both `<`/`,` and `>`/`.` shared the same Hebrew target (ת and ץ). Last-write-wins in `_HE2EN` meant ץ→`>` and ת→`<` instead of `.` and `,`. Fixed in v0.1.99 by removing the `<` and `>` entries entirely. They are layout-invariant (Shift+key produces the same char in both layouts) so they should never be flipped.
13. **Don't add layout switch logic that reads text content when Caps Lock is on** — Text content alone cannot distinguish "user was in English layout" from "user was in Hebrew layout with Caps Lock on" (both produce English capitals). When Caps Lock is on at hotkey time, skip the layout switch entirely and just turn off Caps Lock. See "Caps Lock special case" in the Flip Logic section above.
14. **macOS tray menu must be refreshed on the main thread** — `_refresh_tray_menu()` assigns
    `_tray_icon.menu`; pystray's setter calls `update_menu()`, and its macOS backend implements that as
    AppKit's `setMenu_`. AppKit is main-thread-only, but that function is called from background threads
    (the update checker, the hotkey handler), so on macOS the refresh silently did nothing — no update
    item, and a frozen flip counter. Dispatch via `NSOperationQueue.mainQueue()`, same as #7.
15. **macOS hotkey must be suppressed or every flip beeps** — pynput's listener only observes, so
    `Cmd+Shift+Y` reached the focused app, which has no such shortcut, and macOS played its
    unhandled-Command-key alert. Fixed with `darwin_intercept` in `hotkey.py`. It must keep failing
    *open* (pass the event through on any error) — over-suppressing silently eats real keystrokes.
16. **macOS hotkey was dead after every auto-update, silently** — the update swaps the
    binary → macOS revokes Accessibility → `CGEventTapCreate` returns NULL → pynput returns
    out of its listener thread immediately (`_util/darwin.py::ListenerMixin._run`) while
    `Listener.start()` still looks successful. `main.run()` registers the hotkey *in parallel*
    with onboarding, so the tap was already gone by the time the user granted permission, and
    nothing ever rebuilt it. Onboarding then announced "Permissions granted! Ready to use" —
    which `_finish()` printed unconditionally, since `_check_accessibility()` gives up waiting
    after 60s and calls through either way. Two compounding lies: a dead hotkey and a wizard
    claiming success. Fixed with the supervisor + `tccutil reset` + honest `_finish()` above.
    Symptom to recognise: hotkey does nothing at all, and the security wizard re-runs on every
    launch (that re-run *is* `AXIsProcessTrusted()` reporting False at startup).
17. **The flip must never run inside the macOS event-tap callback** — pynput calls the
    hotkey callback from `_handle_message`, i.e. *inside* the tap callback, and since the
    `darwin_intercept` was added that tap is **active** (`kCGEventTapOptionDefault`). macOS
    therefore holds every keystroke in the system until the callback returns, and a flip takes
    ~0.7s of sleeps plus `pbcopy`/`pbpaste` spawns — plus a blocking HTTPS licence check when
    `gumroad.get_premium_status()`'s 24h cache expires. Two consequences: the keyboard froze
    during every flip, and once the callback overran the tap timeout macOS switched the tap
    off. pynput has exactly one `CGEventTapEnable`, at setup, so it never came back. Fixed by
    `hotkey._dispatch_off_thread` (flip runs on a worker; `main._on_flip`'s `_in_flight` guard
    collapses repeats) plus re-enabling the tap from the intercept on
    `kCGEventTapDisabledByTimeout`/`ByUserInput` — which needs `_tap_keeping_listener`, since
    pynput keeps the tap only in a local. **Don't call the flip synchronously from the hotkey
    callback on macOS, and don't add blocking work to `_on_flip` assuming a thread is free.**
18. **Don't relaunch the app from `build_mac.sh` during a release** — the build finishes before
    `gh release create`, so the app's startup update check runs while the new version doesn't exist yet
    and then sleeps for the full interval. `release_mac.sh` sets `LF_SKIP_RELAUNCH=1` and relaunches after
    publishing instead.
