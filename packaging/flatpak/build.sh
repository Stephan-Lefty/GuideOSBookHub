#!/usr/bin/env bash
set -euo pipefail

# Baut und installiert GuideOSBookHub als Flatpak für den aktuellen Nutzer.
#
# Voraussetzungen:
#   - flatpak und flatpak-builder installiert
#   - Runtime + SDK einmalig einrichten (nur beim ersten Mal nötig):
#       flatpak install -y flathub org.freedesktop.Platform//23.08 \
#                                  org.freedesktop.Sdk//23.08 \
#                                  org.freedesktop.Sdk.Extension.python3//23.08

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFEST="$HERE/io.github.stephanlefty.GuideOSBookHub.json"
BUILD_DIR="$HERE/build-dir"

flatpak-builder --user --install --force-clean "$BUILD_DIR" "$MANIFEST"

echo
echo "Installiert. Starten mit:"
echo "  flatpak run io.github.stephanlefty.GuideOSBookHub"
