#!/bin/sh
# Build "Stumpbar.app" and a drag-to-install DMG in dist/.
set -e
cd "$(dirname "$0")"

VERSION=1.0.0
APP="dist/Stumpbar.app"
DMG="dist/Stumpbar-$VERSION.dmg"

[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt py2app

rm -rf build dist
.venv/bin/python setup.py py2app

# Ad-hoc sign so macOS will launch it on this Mac (not notarized).
codesign --force --deep --sign - "$APP"

STAGE=$(mktemp -d)
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
cp LICENSE "$STAGE/LICENSE.txt"
cp THIRD_PARTY_NOTICES.md "$STAGE/Third-Party Notices.md"
hdiutil create -volname "Stumpbar" -srcfolder "$STAGE" -ov -format UDZO "$DMG"
rm -rf "$STAGE"

echo "Built $APP and $DMG"
