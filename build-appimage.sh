#!/usr/bin/env bash
set -euo pipefail

APP_ID="org.evans.LinuxOpsCenter"
APP_NAME="LinuxOpsCenter"
ENTRY="main.py"
DESKTOP_FILE="org.evans.LinuxOpsCenter.desktop"
ICON_FILE="org.evans.LinuxOpsCenter.svg"
META_FILE="org.evans.LinuxOpsCenter.metainfo.xml"
APPDIR="AppDir"
DIST_DIR="dist"
BUILD_DIR="build"
OUT_APPIMAGE="${APP_ID}-$(uname -m).AppImage"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_TOOL="$SCRIPT_DIR/tools/appimagetool.AppImage"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Missing required command: python3"
  exit 1
fi

if ! python3 -c 'import PyInstaller' >/dev/null 2>&1; then
  echo "PyInstaller is not installed."
  echo "Install with: python3 -m pip install --user pyinstaller"
  exit 1
fi

APPIMAGETOOL_BIN=""
if command -v appimagetool >/dev/null 2>&1; then
  APPIMAGETOOL_BIN="$(command -v appimagetool)"
elif [ -f "$LOCAL_TOOL" ]; then
  chmod +x "$LOCAL_TOOL"
  APPIMAGETOOL_BIN="$LOCAL_TOOL"
else
  echo "appimagetool was not found."
  echo "Install it system-wide, or place it at: $LOCAL_TOOL"
  exit 1
fi

cd "$SCRIPT_DIR"
rm -rf "$APPDIR" "$DIST_DIR" "$BUILD_DIR" "${APP_NAME}.spec"

python3 -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --onedir \
  --name "$APP_NAME" \
  "$ENTRY"

mkdir -p "$APPDIR/usr/bin"
cp -a "$DIST_DIR/$APP_NAME/." "$APPDIR/usr/bin/"

cat > "$APPDIR/AppRun" <<EOF
#!/usr/bin/env sh
set -eu
HERE="\$(dirname "\$(readlink -f "\$0")")"
exec "\$HERE/usr/bin/$APP_NAME" "\$@"
EOF
chmod +x "$APPDIR/AppRun"

cat > "$APPDIR/$APP_ID.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Linux Ops Center
Comment=Systemd dashboard, disk visualizer, and package audit
Exec=$APP_NAME
Icon=$APP_ID
Terminal=false
Categories=Utility;System;Monitor;
StartupNotify=true
StartupWMClass=LinuxOpsCenter
EOF

cp "$ICON_FILE" "$APPDIR/$APP_ID.svg"
mkdir -p "$APPDIR/usr/share/icons/hicolor/scalable/apps"
cp "$ICON_FILE" "$APPDIR/usr/share/icons/hicolor/scalable/apps/$APP_ID.svg"
mkdir -p "$APPDIR/usr/share/applications"
cp "$APPDIR/$APP_ID.desktop" "$APPDIR/usr/share/applications/$APP_ID.desktop"
mkdir -p "$APPDIR/usr/share/metainfo"
cp "$META_FILE" "$APPDIR/usr/share/metainfo/$APP_ID.metainfo.xml"

if [[ "$APPIMAGETOOL_BIN" == *.AppImage ]]; then
  "$APPIMAGETOOL_BIN" --appimage-extract-and-run "$APPDIR" "$OUT_APPIMAGE"
else
  "$APPIMAGETOOL_BIN" "$APPDIR" "$OUT_APPIMAGE"
fi

echo "Built: $OUT_APPIMAGE"
