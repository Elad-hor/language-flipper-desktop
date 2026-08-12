#!/bin/bash
set -e

APP="dist/Language Flipper.app"
DMG="dist/Language.Flipper.dmg"
VOLNAME="Language Flipper"

# 1. Kill any running instance
pkill -x "Language Flipper" 2>/dev/null || true

# 2. Build .app with PyInstaller
#    --clean and --noconfirm match what release_windows.bat does (it wipes
#    build\ and dist\ first). Without --clean a stale PyInstaller cache can be
#    reused; without --noconfirm PyInstaller stops to ask before replacing
#    dist/, which hangs the script when nothing is watching stdin.
python3 -m PyInstaller --clean --noconfirm language_flipper.spec

# 3. Strip quarantine flags (avoids Gatekeeper blocking the DMG contents)
xattr -cr "$APP"

# 4. Remove old DMG if it exists
rm -f "$DMG"

# Detach any copy of our volume left mounted by an earlier run.
#
# create-dmg finishes by unmounting its temp volume, and that unmount fails
# with "resource busy" (hdiutil: couldn't unmount "diskN") whenever Finder or
# Spotlight still has the volume open. When it fails, NO dmg is produced and
# the stale volume stays mounted — which then makes the next attempt fail too.
# Seen on 2026-08-10 during the first Mac release since April.
#
# `hdiutil info` prints the dev node and mount point on the same line, so the
# mounted volume's /dev/diskN can be pulled straight out of it.
detach_stale_volume() {
  if [ -d "/Volumes/$VOLNAME" ] || hdiutil info | grep -q "/Volumes/$VOLNAME"; then
    echo "  → detaching stale volume /Volumes/$VOLNAME"
    diskutil unmount force "/Volumes/$VOLNAME" >/dev/null 2>&1 || true
    hdiutil info | grep "/Volumes/$VOLNAME" | awk '{print $1}' | while read -r dev; do
      [ -n "$dev" ] && hdiutil detach "$dev" -force >/dev/null 2>&1 || true
    done
    sleep 2
  fi
}

# 5. Package into a drag-to-Applications DMG.
#    Retried, because the unmount above is genuinely racy — a Spotlight index
#    pass is enough to lose a build otherwise.
detach_stale_volume

for attempt in 1 2 3; do
  echo "→ create-dmg (attempt $attempt/3)"
  if create-dmg \
      --volname "$VOLNAME" \
      --window-pos 200 120 \
      --window-size 600 400 \
      --icon-size 100 \
      --icon "Language Flipper.app" 175 190 \
      --hide-extension "Language Flipper.app" \
      --app-drop-link 425 190 \
      "$DMG" \
      "$APP"; then
    break
  fi

  echo "  create-dmg attempt $attempt failed"
  detach_stale_volume
  # create-dmg leaves a temp read-write image behind on failure.
  rm -f "$DMG" dist/rw.*.dmg 2>/dev/null || true

  if [ "$attempt" -eq 3 ]; then
    echo "ERROR: create-dmg failed 3 times."
    echo "Something is holding the volume open. Find it with:"
    echo "  lsof +D \"/Volumes/$VOLNAME\""
    echo "Closing any Finder window showing the volume (or 'killall Finder') usually clears it."
    exit 1
  fi
  sleep 5
done

# create-dmg can exit non-zero having still written the image, and can also
# exit zero without one. The file is the only thing worth trusting.
if [ ! -f "$DMG" ]; then
  echo "ERROR: create-dmg reported success but $DMG does not exist."
  exit 1
fi

echo "Done — $DMG is ready ($(du -h "$DMG" | cut -f1))"
