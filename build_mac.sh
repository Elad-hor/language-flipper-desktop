#!/bin/bash
# Builds Language Flipper.app and packages it into a proper DMG
# with a drag-to-Applications installer UI.
#
# Requirements:
#   brew install create-dmg
#
# Usage:
#   chmod +x build_mac.sh
#   ./build_mac.sh

set -e

APP_NAME="Language Flipper"
DMG_NAME="Language.Flipper.dmg"

echo "==> Building .app with PyInstaller..."
python3 -m PyInstaller language_flipper.spec --noconfirm

echo "==> Removing old DMG if present..."
rm -f "dist/$DMG_NAME"

echo "==> Creating DMG..."
create-dmg \
  --volname "$APP_NAME" \
  --window-pos 200 120 \
  --window-size 600 400 \
  --icon-size 100 \
  --icon "$APP_NAME.app" 175 190 \
  --hide-extension "$APP_NAME.app" \
  --app-drop-link 425 190 \
  "dist/$DMG_NAME" \
  "dist/$APP_NAME.app"

echo "==> Done! Output: dist/$DMG_NAME"
