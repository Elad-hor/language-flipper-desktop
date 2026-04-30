#!/bin/bash
# Usage: ./release_windows.sh 0.1.68 "Fix: description of what changed"
# Run this in Git Bash on Windows.
# Requirements: pyinstaller, Inno Setup (iscc in PATH), gh CLI, git
set -e

VERSION="$1"
NOTES="$2"

if [ -z "$VERSION" ]; then
  echo "Usage: ./release_windows.sh <version> \"<release notes>\""
  exit 1
fi

# 1. Pull latest code
git pull

# 2. Update version everywhere
sed -i "s/VERSION = \".*\"/VERSION = \"$VERSION\"/" flipper_daemon/version.py
sed -i "s/AppVersion=.*/AppVersion=$VERSION/" language_flipper_setup.iss

echo "→ Version set to $VERSION"

# 3. Build exe with PyInstaller
pyinstaller --noconfirm language_flipper_windows.spec
echo "→ PyInstaller build done"

# 4. Package with Inno Setup
if command -v iscc &>/dev/null; then
  iscc language_flipper_setup.iss
else
  # Default Inno Setup install location
  "/c/Program Files (x86)/Inno Setup 6/ISCC.exe" language_flipper_setup.iss
fi
echo "→ Installer built: dist/Language-Flipper-Setup.exe"

# 5. Commit version bump
git add flipper_daemon/version.py language_flipper_setup.iss
git commit -m "bump version to $VERSION (windows)"
git push

# 6. Release to GitHub
NOTES_TEXT="${NOTES:-Language Flipper $VERSION — Windows}"
gh release create "v${VERSION}-windows" "dist/Language-Flipper-Setup.exe" \
  --title "Language Flipper $VERSION — Windows" \
  --notes "$NOTES_TEXT"

echo ""
echo "Released v${VERSION}-windows"
