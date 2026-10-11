#!/usr/bin/env bash
# Wrap the PyInstaller onedir output (dist/rpg-database-manager) into an AppImage.
set -euo pipefail
cd "$(dirname "$0")/../.."
APPDIR=build/AppDir
rm -rf "$APPDIR" && mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" \
  "$APPDIR/usr/share/icons/hicolor/256x256/apps"
cp -r dist/rpg-database-manager/. "$APPDIR/usr/bin/"
cp packaging/linux/rpg-database-manager.desktop "$APPDIR/usr/share/applications/"
cp packaging/linux/rpg-database-manager.desktop "$APPDIR/"
cp data/icons/app_icon.png "$APPDIR/usr/share/icons/hicolor/256x256/apps/rpg-database-manager.png"
cp data/icons/app_icon.png "$APPDIR/rpg-database-manager.png"
# Qt's xcb platform plugin needs libxcb-cursor, which many desktops do not have installed
mkdir -p "$APPDIR/usr/lib"
CURSOR_LIB="$(ldconfig -p | awk '/libxcb-cursor\.so\.0 /{print $NF; exit}')"
if [ -n "$CURSOR_LIB" ]; then cp -L "$CURSOR_LIB" "$APPDIR/usr/lib/"; else echo "WARNING: libxcb-cursor.so.0 not found, not bundled"; fi
cat > "$APPDIR/AppRun" <<'RUN'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
export LD_LIBRARY_PATH="$HERE/usr/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "$HERE/usr/bin/rpg-database-manager" "$@"
RUN
chmod +x "$APPDIR/AppRun"
# A fixed appimagetool release, verified by checksum (a rolling build would change without notice)
TOOL=build/appimagetool
TOOL_SHA256=ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0
if [ ! -x "$TOOL" ]; then
  curl -fsSL -o "$TOOL" https://github.com/AppImage/appimagetool/releases/download/1.9.1/appimagetool-x86_64.AppImage
  echo "$TOOL_SHA256  $TOOL" | sha256sum -c -
  chmod +x "$TOOL"
fi
ARCH=x86_64 "$TOOL" --appimage-extract-and-run "$APPDIR" RPG_Database_Manager-x86_64.AppImage
