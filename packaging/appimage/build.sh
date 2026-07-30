#!/usr/bin/env bash
set -euo pipefail

# Baut ein AppImage für GuideOSBookHub: bündelt einen eigenen Python-Venv
# (inkl. PyQt6, das seine Qt6-Bibliotheken bereits selbst mitbringt) sowie
# ein statisches rclone-Binary. Ergebnis läuft ohne Installation und ohne
# Systemabhängigkeiten (außer den üblichen Linux-Basisbibliotheken) auf
# praktisch jeder halbwegs aktuellen x86_64-Distribution, unabhängig von
# der verwendeten Desktop-Umgebung.
#
# Voraussetzungen auf dem Bau-Rechner:
#   - python3 (>=3.10) mit venv-Modul
#   - curl, unzip
#   - appimagetool (https://github.com/AppImage/appimagetool/releases),
#     ausführbar im PATH

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$HERE/../.." && pwd)"
BUILD_DIR="$HERE/build"
APPDIR="$BUILD_DIR/GuideOSBookHub.AppDir"

if ! command -v appimagetool >/dev/null 2>&1; then
    echo "Fehler: appimagetool nicht gefunden." >&2
    echo "Herunterladen von https://github.com/AppImage/appimagetool/releases," >&2
    echo "ausführbar machen (chmod +x) und ins PATH legen." >&2
    exit 1
fi

rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons/hicolor/256x256/apps"

echo "==> Erzeuge eigenständigen Python-Venv im AppDir (usr/)"
python3 -m venv "$APPDIR/usr"
"$APPDIR/usr/bin/pip" install --upgrade pip -q
"$APPDIR/usr/bin/pip" install "$PROJECT_ROOT" -q

echo "==> Lade aktuelles rclone (statisches Binary) für linux-amd64"
curl -fsSL "https://downloads.rclone.org/rclone-current-linux-amd64.zip" -o "$BUILD_DIR/rclone.zip"
rm -rf "$BUILD_DIR/rclone_extracted"
unzip -oq "$BUILD_DIR/rclone.zip" -d "$BUILD_DIR/rclone_extracted"
install -Dm755 "$BUILD_DIR"/rclone_extracted/*/rclone "$APPDIR/usr/bin/rclone"

echo "==> Kopiere Desktop-Datei und Icon"
cp "$PROJECT_ROOT/icons/icon-256.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/guideosbookhub.png"
cp "$APPDIR/usr/share/icons/hicolor/256x256/apps/guideosbookhub.png" "$APPDIR/guideosbookhub.png"
sed -e 's#^Exec=.*#Exec=guideosbookhub#' -e 's#^Icon=.*#Icon=guideosbookhub#' \
    "$PROJECT_ROOT/guideosbookhub.desktop" > "$APPDIR/usr/share/applications/guideosbookhub.desktop"
cp "$APPDIR/usr/share/applications/guideosbookhub.desktop" "$APPDIR/guideosbookhub.desktop"

echo "==> Schreibe AppRun"
cat > "$APPDIR/AppRun" <<'EOF'
#!/usr/bin/env bash
HERE="$(dirname "$(readlink -f "${0}")")"
# usr/bin zuerst im PATH: das gebündelte rclone (und der eigene Python-Venv)
# haben Vorrang vor gleichnamigen, ggf. abweichenden System-Programmen.
export PATH="$HERE/usr/bin:$PATH"
exec "$HERE/usr/bin/guideosbookhub" "$@"
EOF
chmod +x "$APPDIR/AppRun"

echo "==> Baue AppImage mit appimagetool"
ARCH=x86_64 appimagetool "$APPDIR" "$BUILD_DIR/GuideOSBookHub-x86_64.AppImage"

echo "==> Fertig: $BUILD_DIR/GuideOSBookHub-x86_64.AppImage"
