#!/usr/bin/env bash
set -euo pipefail

# Baut ein binäres .deb für GuideOSBookHub (Debian/Ubuntu und Derivate).
# Reines dpkg-deb, ohne debhelper/dh_make, da das Paket keine kompilierten
# Bestandteile enthält (Architecture: all). rclone wird bewusst nur als
# "Recommends" statt "Depends" eingetragen: die App funktioniert auch ohne
# rclone als reiner lokaler Lesezeichen-Manager und bietet die Installation
# beim ersten Start selbst per Dialog an (siehe gui/rclone_install_dialog.py).
#
# Voraussetzung auf dem Bau-Rechner: dpkg-deb (Teil von dpkg, auf jedem
# Debian-basierten System bereits vorhanden).

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$HERE/../.." && pwd)"
VERSION="$(grep -m1 '^version' "$PROJECT_ROOT/pyproject.toml" | sed -E 's/version = "(.*)"/\1/')"
BUILD_DIR="$HERE/build"
PKG_DIR="$BUILD_DIR/guideosbookhub_${VERSION}_all"

if ! command -v dpkg-deb >/dev/null 2>&1; then
    echo "Fehler: dpkg-deb nicht gefunden (nur auf Debian/Ubuntu-artigen Systemen vorhanden)." >&2
    exit 1
fi

rm -rf "$PKG_DIR"
mkdir -p "$PKG_DIR/DEBIAN" \
         "$PKG_DIR/usr/bin" \
         "$PKG_DIR/usr/lib/guideosbookhub" \
         "$PKG_DIR/usr/share/applications" \
         "$PKG_DIR/usr/share/icons/hicolor/16x16/apps" \
         "$PKG_DIR/usr/share/icons/hicolor/32x32/apps" \
         "$PKG_DIR/usr/share/icons/hicolor/48x48/apps" \
         "$PKG_DIR/usr/share/icons/hicolor/128x128/apps" \
         "$PKG_DIR/usr/share/icons/hicolor/256x256/apps"

echo "==> Kopiere Python-Quellcode"
cp "$PROJECT_ROOT/guideosbookhub.py" "$PKG_DIR/usr/lib/guideosbookhub/"
cp -r "$PROJECT_ROOT/core" "$PKG_DIR/usr/lib/guideosbookhub/"
cp -r "$PROJECT_ROOT/gui" "$PKG_DIR/usr/lib/guideosbookhub/"
find "$PKG_DIR/usr/lib/guideosbookhub" -name "__pycache__" -exec rm -rf {} +

echo "==> Icon-Pfad in guideosbookhub.py auf installierten Ort umbiegen"
sed -i 's#Path(__file__).parent / "icons" / "icon-256.png"#Path("/usr/share/icons/hicolor/256x256/apps/guideosbookhub.png")#' \
    "$PKG_DIR/usr/lib/guideosbookhub/guideosbookhub.py"

echo "==> Wrapper-Skript /usr/bin/guideosbookhub"
cat > "$PKG_DIR/usr/bin/guideosbookhub" <<'EOF'
#!/bin/sh
export PYTHONPATH="/usr/lib/guideosbookhub:${PYTHONPATH:-}"
exec python3 -m guideosbookhub "$@"
EOF
chmod +x "$PKG_DIR/usr/bin/guideosbookhub"

echo "==> Desktop-Datei und Icons"
sed -e 's#^Exec=.*#Exec=guideosbookhub#' -e 's#^Icon=.*#Icon=guideosbookhub#' \
    "$PROJECT_ROOT/guideosbookhub.desktop" > "$PKG_DIR/usr/share/applications/guideosbookhub.desktop"
for size in 16 32 48 128 256; do
    cp "$PROJECT_ROOT/icons/icon-${size}.png" \
       "$PKG_DIR/usr/share/icons/hicolor/${size}x${size}/apps/guideosbookhub.png"
done

echo "==> DEBIAN/control"
cat > "$PKG_DIR/DEBIAN/control" <<EOF
Package: guideosbookhub
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: all
Depends: python3 (>= 3.10), python3-pyqt6
Recommends: rclone
Maintainer: Stephan R. <stephan.roesner@protonmail.com>
Description: Lesezeichen-Manager mit Cloud-Sync über einen frei wählbaren Anbieter
 GuideOSBookHub verwaltet Lesezeichen lokal und synchronisiert sie über
 rclone mit einer frei wählbaren Cloud (Nextcloud/WebDAV, Proton Drive,
 Dropbox, Google Drive, S3-kompatible Speicher u.v.m.). Fehlt rclone, bietet
 die App beim ersten Start eine Installation per Dialog an.
EOF

echo "==> Baue .deb"
dpkg-deb --build --root-owner-group "$PKG_DIR"

echo "==> Fertig: ${PKG_DIR}.deb"
