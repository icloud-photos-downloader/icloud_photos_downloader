#!/bin/bash
# Builds "Photos Sync.app" (menu bar app) with Swift Package Manager; works with Command Line Tools only (no Xcode).
# Usage: ./build_app.sh [output-dir]      default output: ./build
set -euo pipefail
cd "$(dirname "$0")"

OUT="${1:-build}"
APP="$OUT/Photos Sync.app"

# Build outside this folder: it may live on OneDrive, whose sync corrupts SwiftPM's build database.
SCRATCH="${SCRATCH_PATH:-$HOME/Library/Caches/icloudpd-menubar/build}"

swift build -c release --scratch-path "$SCRATCH"
BIN="$(swift build -c release --scratch-path "$SCRATCH" --show-bin-path)/MenuBarApp"

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"
mkdir -p "$APP/Contents/Resources"
cp "$BIN" "$APP/Contents/MacOS/PhotosSync"

# app icon: the icon of Apple's Photos app, taken from this Mac at build time (it is not part of the
# repository); a generated icon is the fallback
PHOTOS_ICON="/System/Applications/Photos.app/Contents/Resources/AppIcon.icns"
if [ -f "$PHOTOS_ICON" ]; then
    cp "$PHOTOS_ICON" "$APP/Contents/Resources/AppIcon.icns"
else
    ICONSET="$(mktemp -d)/AppIcon.iconset"
    mkdir -p "$ICONSET"
    swift make_icon.swift "$ICONSET/base.png"
    for px in 16 32 128 256 512; do
        sips -z $px $px "$ICONSET/base.png" --out "$ICONSET/icon_${px}x${px}.png" >/dev/null
        sips -z $((px * 2)) $((px * 2)) "$ICONSET/base.png" --out "$ICONSET/icon_${px}x${px}@2x.png" >/dev/null
    done
    rm "$ICONSET/base.png"
    iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/AppIcon.icns"
fi

# the icloudpd of this repository (it has the status API and --delete-list the app needs)
mkdir -p "$APP/Contents/Resources/icloudpd-src"
rsync -a --exclude '__pycache__' --exclude '*.pyc' --exclude '*.egg-info' ../src/ "$APP/Contents/Resources/icloudpd-src/"

cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key><string>PhotosSync</string>
    <key>CFBundleIconFile</key><string>AppIcon</string>
    <key>CFBundleIdentifier</key><string>com.marlo.icloudpd-menubar</string>
    <key>CFBundleName</key><string>Photos Sync</string>
    <key>CFBundleDisplayName</key><string>Photos Sync</string>
    <key>CFBundlePackageType</key><string>APPL</string>
    <key>CFBundleShortVersionString</key><string>0.1.0</string>
    <key>CFBundleVersion</key><string>1</string>
    <key>LSMinimumSystemVersion</key><string>13.0</string>
    <key>LSUIElement</key><true/>
    <key>NSHighResolutionCapable</key><true/>
    <key>NSPhotoLibraryUsageDescription</key><string>Photos Sync reads new photos to save a copy, and removes from Photos the photos you deleted in iCloud, after you confirm.</string>
    <key>NSAppleEventsUsageDescription</key><string>Photos Sync imports the photos it downloads into the Photos app.</string>
</dict>
</plist>
PLIST

# ad-hoc signature: needed for notifications and "open at login"
codesign --force --sign - "$APP"
echo "Built $APP"
