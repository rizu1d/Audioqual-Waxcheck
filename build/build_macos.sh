#!/bin/bash
# ╔════════════════════════════════════════════════════════════╗
# ║  WaxCheck — macOS Build Script                            ║
# ║  Generates WaxCheck.app and optionally a .dmg installer   ║
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
APP_NAME="WaxCheck"

echo "╔════════════════════════════════════════╗"
echo "║  Building $APP_NAME v$VERSION for macOS  ║"
echo "╚════════════════════════════════════════╝"
echo ""

cd "$PROJECT_ROOT"

# ── 1. Clean previous build ──
echo "→ Cleaning previous build..."
rm -rf dist/WaxCheck dist/WaxCheck.app build/WaxCheck 2>/dev/null || true

# ── 2. Run PyInstaller ──
echo "→ Running PyInstaller..."
python3 -m PyInstaller build/waxcheck_macos.spec --noconfirm --clean

echo ""
if [ -d "dist/WaxCheck.app" ]; then
    APP_SIZE=$(du -sh "dist/WaxCheck.app" | cut -f1)
    echo "✓ WaxCheck.app built successfully ($APP_SIZE)"
else
    # PyInstaller with BUNDLE creates the .app inside dist/WaxCheck/
    # or directly in dist/ depending on version
    if [ -d "dist/WaxCheck/WaxCheck.app" ]; then
        echo "✓ WaxCheck.app built at dist/WaxCheck/WaxCheck.app"
    else
        echo "✗ Build failed — WaxCheck.app not found"
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
    if [ -d "dist/WaxCheck.app" ]; then
        APP_PATH="dist/WaxCheck.app"
    else
        APP_PATH="dist/WaxCheck/WaxCheck.app"
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
echo "  App:  dist/WaxCheck.app"
if [[ "${1:-}" == "--dmg" ]]; then
    echo "  DMG:  dist/$DMG_NAME"
fi
echo ""
echo "  NOTE: This build is unsigned."
echo "  Users will need to right-click → Open"
echo "  the first time they launch it."
echo "════════════════════════════════════════"
