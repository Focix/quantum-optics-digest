#!/bin/bash
# Build, ad-hoc sign and install the native widget. Needs the Command Line Tools only
# (no Xcode): WidgetKit and SwiftUI both ship in the CLT SDK.
#
#   ./build.sh            build and install to /Applications
#   ./build.sh --no-install  leave the .app in build/ only
set -euo pipefail

cd "$(dirname "$0")"
SDK=$(xcrun --show-sdk-path)
TARGET=arm64-apple-macos14.0
APP=build/Quantum\ Optics\ Digest.app
EXT="$APP/Contents/PlugIns/DigestWidget.appex"

rm -rf build
mkdir -p "$APP/Contents/MacOS" "$EXT/Contents/MacOS"

# The app: shared sources + its own UI.
xcrun swiftc -target "$TARGET" -sdk "$SDK" -O \
  -o "$APP/Contents/MacOS/QuantumOpticsDigest" \
  Sources/Shared/*.swift Sources/App/*.swift

# The widget extension: shared sources + the WidgetBundle. -parse-as-library keeps @main on
# the WidgetBundle rather than looking for top-level code, and the entry point must be
# _NSExtensionMain, as Xcode links widget extensions: it performs the NSExtension host
# handshake that tells ExtensionFoundation which extension point this process is serving.
# Entering Swift's generated main instead crashes at launch with "Unrecognized extension type",
# which chronod sees as the process dying, so the widget never reaches the gallery.
xcrun swiftc -target "$TARGET" -sdk "$SDK" -O -parse-as-library -application-extension \
  -Xlinker -e -Xlinker _NSExtensionMain \
  -o "$EXT/Contents/MacOS/DigestWidget" \
  Sources/Shared/*.swift Sources/Widget/*.swift

cp Resources/Info-App.plist "$APP/Contents/Info.plist"
cp Resources/Info-Widget.plist "$EXT/Contents/Info.plist"

# Sign inside out; ad-hoc (-) is enough for a locally installed widget.
codesign --force --sign - --entitlements Resources/Widget.entitlements --timestamp=none "$EXT"
codesign --force --sign - --entitlements Resources/App.entitlements --timestamp=none "$APP"
codesign --verify --deep --strict "$APP"

echo "built $APP"

if [ "${1:-}" != "--no-install" ]; then
  # WidgetKit only lists widgets whose host app is installed and has been launched once.
  rm -rf "/Applications/Quantum Optics Digest.app"
  cp -R "$APP" /Applications/
  echo "installed to /Applications/Quantum Optics Digest.app"
fi
