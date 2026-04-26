#!/bin/bash
# Usage: ./release_mac.sh 0.1.64 "Fix: description of what changed"
set -e

VERSION="$1"
NOTES="$2"

if [ -z "$VERSION" ]; then
  echo "Usage: ./release_mac.sh <version> \"<release notes>\""
  exit 1
fi

# 1. Update version in spec
sed -i '' "s/\"CFBundleShortVersionString\": \".*\"/\"CFBundleShortVersionString\": \"$VERSION\"/" language_flipper.spec

echo "→ Version set to $VERSION"

# 2. Build
./build_mac.sh

# 3. Release to GitHub
NOTES_TEXT="${NOTES:-Language Flipper $VERSION — macOS}"
gh release create "v${VERSION}-mac" "dist/Language.Flipper.dmg" \
  --title "Language Flipper $VERSION — macOS" \
  --notes "$NOTES_TEXT"

echo ""
echo "Released v${VERSION}-mac"
echo "Install: open the DMG, drag to Applications, then:"
echo "  xattr -cr \"/Applications/Language Flipper.app\""
