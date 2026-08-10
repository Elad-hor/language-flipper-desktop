#!/bin/bash
# Usage: ./release_mac.sh 0.1.64 "Fix: description of what changed"
set -e

VERSION="$1"
NOTES="$2"

if [ -z "$VERSION" ]; then
  echo "Usage: ./release_mac.sh <version> \"<release notes>\""
  exit 1
fi

# 1. Pull latest code
git pull

# 2. Update version everywhere
sed -i '' "s/VERSION = \".*\"/VERSION = \"$VERSION\"/" flipper_daemon/version.py
sed -i '' "s/\"CFBundleShortVersionString\": \".*\"/\"CFBundleShortVersionString\": \"$VERSION\"/" language_flipper.spec

echo "→ Version set to $VERSION"

# 3. Build
./build_mac.sh

# 4. Commit the version bump — same ordering as release_windows.bat: only after
#    the build succeeds, and before the release is cut. Without this the bumped
#    version.py / spec sat uncommitted on the Mac and collided with the next
#    Windows release.
#    The guard matters here in a way it doesn't on Windows: this script runs
#    with `set -e`, and when version.py is already at $VERSION the sed above is
#    a no-op, so `git commit` would find nothing staged, exit non-zero and abort
#    before the release is created.
echo "→ Committing version bump"
git add flipper_daemon/version.py language_flipper.spec
if git diff --cached --quiet; then
  echo "  (nothing to commit — version files already at $VERSION)"
else
  git commit -m "bump version to $VERSION (mac)"
  git push
fi

# 5. Release to GitHub
#
# The install steps are in the notes because this is an UNSIGNED build: macOS
# will refuse the first launch, and anyone downloading the DMG straight from
# GitHub never sees the website's explanation. Keep this wording in step with
# site/src/components/InstallHelp.astro (the install.mac_* i18n keys).
#
# Note for macOS 15 (Sequoia) and later: Apple REMOVED the old right-click →
# Open shortcut for unsigned apps, so "Open Anyway" in System Settings is the
# only route. Don't "simplify" these notes back to the right-click trick.
# IFS= is required: without it `read` strips the leading newline (IFS includes
# it) and the notes text runs straight into the "---".
IFS= read -r -d '' INSTALL_STEPS <<'STEPS' || true

---

### Installing

Language Flipper isn't signed with an Apple certificate yet, so macOS will ask
you to confirm the first time. Nothing is wrong.

1. Open the DMG and drag **Language Flipper** into your Applications folder.
2. On first launch, macOS says it can't verify the developer.
3. Open **System Settings → Privacy & Security**.
4. Scroll down and click **Open Anyway** next to Language Flipper.

On macOS 14 and earlier you can instead right-click the app and choose **Open**.

Language Flipper then walks you through granting Accessibility and Input
Monitoring permission — that's how it reads and replaces your text.
STEPS

NOTES_TEXT="${NOTES:-Language Flipper $VERSION — macOS}"
gh release create "v${VERSION}-mac" "dist/Language.Flipper.dmg" \
  --title "Language Flipper $VERSION — macOS" \
  --notes "${NOTES_TEXT}${INSTALL_STEPS}"

echo ""
echo "Released v${VERSION}-mac"
echo ""
echo "NEXT: the marketing site still links the previous DMG."
echo "Update macHref in site/src/components/DownloadRow.astro to:"
echo "  https://github.com/Elad-hor/language-flipper-desktop/releases/download/v${VERSION}-mac/Language.Flipper.dmg"
echo "then commit and push — CI redeploys the site automatically."
