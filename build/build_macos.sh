#!/bin/bash
# ╔════════════════════════════════════════════════════════════╗
# ║  AudioQual — macOS Build Script                            ║
# ║  Generates AudioQual.app and optionally a .dmg installer   ║
# ╚════════════════════════════════════════════════════════════╝
#
# Usage:
#   cd <project_root>
#   bash build/build_macos.sh          # Build .app only
#   bash build/build_macos.sh --dmg    # Build .app + .dmg installer
#
# Prerequisites:
#   pip install -r requirements.txt
#   pip install pyinstaller

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VERSION="0.1.0-beta"
APP_NAME="AudioQual"

echo "╔════════════════════════════════════════╗"
echo "║  Building $APP_NAME v$VERSION for macOS  ║"
echo "╚════════════════════════════════════════╝"
echo ""

cd "$PROJECT_ROOT"

# ── 1. Clean previous build ──
echo "→ Cleaning previous build..."
rm -rf dist/AudioQual dist/AudioQual.app build/AudioQual 2>/dev/null || true

# ── 2. Run PyInstaller ──
echo "→ Running PyInstaller..."
python3 -m PyInstaller build/audioqual_macos.spec --noconfirm --clean

echo ""
if [ -d "dist/AudioQual.app" ]; then
    APP_SIZE=$(du -sh "dist/AudioQual.app" | cut -f1)
    echo "✓ AudioQual.app built successfully ($APP_SIZE)"
else
    # PyInstaller with BUNDLE creates the .app inside dist/AudioQual/
    # or directly in dist/ depending on version
    if [ -d "dist/AudioQual/AudioQual.app" ]; then
        echo "✓ AudioQual.app built at dist/AudioQual/AudioQual.app"
    else
        echo "✗ Build failed — AudioQual.app not found"
        exit 1
    fi
fi

# ── 3. Create DMG if requested ──
if [[ "${1:-}" == "--dmg" ]]; then
    echo ""
    echo "→ Creating DMG installer..."

    DMG_NAME="${APP_NAME}-${VERSION}-macOS.dmg"
    DMG_TEMP="dist/dmg_temp"

    # Find the .app
    if [ -d "dist/AudioQual.app" ]; then
        APP_PATH="dist/AudioQual.app"
    else
        APP_PATH="dist/AudioQual/AudioQual.app"
    fi

    # Prepare DMG staging directory
    rm -rf "$DMG_TEMP" "dist/$DMG_NAME"
    mkdir -p "$DMG_TEMP"
    cp -R "$APP_PATH" "$DMG_TEMP/"

    # Create Applications symlink for drag-to-install
    ln -s /Applications "$DMG_TEMP/Applications"

    # Create DMG using hdiutil (macOS built-in)
    hdiutil create \
        -volname "$APP_NAME" \
        -srcfolder "$DMG_TEMP" \
        -ov \
        -format UDZO \
        "dist/$DMG_NAME"

    rm -rf "$DMG_TEMP"

    DMG_SIZE=$(du -sh "dist/$DMG_NAME" | cut -f1)
    echo "✓ DMG created: dist/$DMG_NAME ($DMG_SIZE)"
fi

# ── 4. Summary ──
echo ""
echo "════════════════════════════════════════"
echo "  Build complete!"
echo ""
echo "  App:  dist/AudioQual.app"
if [[ "${1:-}" == "--dmg" ]]; then
    echo "  DMG:  dist/$DMG_NAME"
fi
echo ""
echo "  NOTE: This build is unsigned."
echo "  Users will need to right-click → Open"
echo "  the first time they launch it."
echo "════════════════════════════════════════"
