#!/bin/bash
set -e

# 1. Kill any running instance
pkill -x "Language Flipper" 2>/dev/null || true

# 2. Build .app with PyInstaller
python3 -m PyInstaller language_flipper.spec

# 3. Strip quarantine flags (avoids Gatekeeper blocking the DMG contents)
xattr -cr "dist/Language Flipper.app"

# 4. Remove old DMG if it exists
rm -f "dist/Language.Flipper.dmg"

# 5. Package into a drag-to-Applications DMG
create-dmg \
  --volname "Language Flipper" \
  --window-pos 200 120 \
  --window-size 600 400 \
  --icon-size 100 \
  --icon "Language Flipper.app" 175 190 \
  --hide-extension "Language Flipper.app" \
  --app-drop-link 425 190 \
  "dist/Language.Flipper.dmg" \
  "dist/Language Flipper.app"

echo "Done — dist/Language.Flipper.dmg is ready"
