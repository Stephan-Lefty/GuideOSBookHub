# GuideOSBookHub

Ein Lesezeichen-Manager für Linux, der eigene Lesezeichen lokal verwaltet
und sie über eine **frei wählbare Cloud** zwischen mehreren Geräten
synchronisiert – Nextcloud/WebDAV, Proton Drive, Dropbox, Google Drive,
S3-kompatible Speicher usw. Anders als das Schwesterprojekt
[NEXTBookmarks](../NEXTBookmarks) (Browser-Extension + eigene, fest auf
Nextcloud zugeschnittene Server-App) ist GuideOSBookHub eine eigenständige
Desktop-Anwendung mit eigener Lesezeichen-Verwaltung; es liest keine
Browser-Lesezeichen.

Die App selbst ist **distributions- und Desktop-unabhängig**: sie basiert
auf PyQt6 (läuft identisch unter GNOME, KDE, XFCE, ...) und steht in vier
Installationsformen zur Verfügung – von einem einzigen portablen AppImage
bis zum nativen `.deb` für Debian/Ubuntu (siehe [Installation](#installation)).

Die Cloud-Anbindung läuft nicht über Provider-eigenen Code, sondern über
[rclone](https://rclone.org), das rund 70 Speicherdienste einheitlich
unterstützt – u.a. auch Proton Drive, für das es (Stand 2026) keine
offizielle Dritt-API gibt.

## Funktionsumfang

- Lesezeichen und Ordner lokal anlegen, bearbeiten, löschen, favorisieren
- Suche über Titel, URL und Tags
- Mehrere unabhängige **Sync-Profile** gleichzeitig (z.B. "Arbeit" →
  Nextcloud, "Privat" → Proton Drive) – jeder Top-Level-Ordner kann einem
  Profil zugewiesen werden, Unterordner erben davon
- Automatischer und manueller Sync, läuft im Hintergrund-Thread (blockiert
  die Oberfläche nicht)
- Zwei-Wege-Sync mit Konfliktlösung (neuere Änderung gewinnt, wie bei
  NEXTBookmarks), Löschungen werden über Tombstones nachvollzogen
- Prüft beim Start, ob `rclone` vorhanden ist; falls nicht, öffnet sich ein
  Dialog, der die Installation per Klick anbietet (siehe
  [rclone-Installation](#rclone-installation))

## Voraussetzungen

- Python 3.10+ und PyQt6 (bei AppImage/Flatpak/.deb bereits enthalten)
- [rclone](https://rclone.org) – wird nicht zwingend vorab benötigt: fehlt
  es, bietet die App selbst eine Installation per Dialog an (Details siehe
  unten). AppImage und Flatpak bringen ohnehin ein eigenes rclone mit.

## Installation

Vier gleichwertige Wege stehen zur Auswahl – je nachdem, wie viel man
selbst verwalten möchte:

| Format | Distributions-unabhängig | Bringt rclone mit | Geeignet für |
|---|---|---|---|
| AppImage | ✅ jede x86_64-Distro | ✅ | Einzelne Datei, kein Root nötig |
| Flatpak | ✅ jede Distro mit Flatpak | ✅ (im Sandbox) | Saubere Desktop-Integration |
| `.deb` | Debian/Ubuntu und Derivate | – (`Recommends`) | Native apt-Integration |
| pip/pipx | ✅ jede Distro mit Python 3.10+ | – | Entwicklung, volle Kontrolle |

### AppImage (jede Distribution, x86_64)

```bash
./packaging/appimage/build.sh
```

Baut `packaging/appimage/build/GuideOSBookHub-x86_64.AppImage` – bündelt
einen eigenen Python-Venv (inkl. PyQt6) sowie ein statisches rclone-Binary,
läuft ohne Installation direkt per Doppelklick/`./GuideOSBookHub-x86_64.AppImage`.
Voraussetzung zum Bauen: [appimagetool](https://github.com/AppImage/appimagetool/releases)
im PATH.

### Flatpak (jede Distribution mit Flatpak)

```bash
./packaging/flatpak/build.sh
flatpak run io.github.stephanlefty.GuideOSBookHub
```

Baut und installiert das Flatpak für den aktuellen Nutzer, inkl. gebündeltem
rclone im Sandbox. Voraussetzung: `flatpak` und `flatpak-builder`, sowie
einmalig `org.freedesktop.Platform//23.08` + `org.freedesktop.Sdk//23.08` +
`org.freedesktop.Sdk.Extension.python3//23.08` (siehe Kommentar im Skript).

### `.deb`-Paket (Debian/Ubuntu und Derivate)

```bash
./packaging/deb/build.sh
sudo apt install ./packaging/deb/build/guideosbookhub_0.1.0_all.deb
```

Installiert `guideosbookhub` systemweit inkl. Menüeintrag; rclone ist nur
als `Recommends` eingetragen, nicht als harte Abhängigkeit.

### pip/pipx (jede Distribution, für Entwicklung)

```bash
pipx install .
```

Alternativ in einer virtuellen Umgebung:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Danach steht der Befehl `guideosbookhub` zur Verfügung.

```bash
cp guideosbookhub.desktop ~/.local/share/applications/
```

integriert die App zusätzlich ins Anwendungsmenü (Icon-Pfad ggf. anpassen,
falls das Projektverzeichnis verschoben wird).

## rclone-Installation

AppImage und Flatpak bringen bereits ein eigenes, aktuelles rclone mit –
hier ist nichts weiter zu tun. Bei `.deb`/pip/pipx wird beim ersten Start
geprüft, ob ein System-`rclone` gefunden wird; falls nicht, erscheint ein
Dialog mit einem "Installieren"-Button. Der Klick löst das offizielle
rclone-Installationsskript aus, abgesichert über eine grafische
PolicyKit-Rechteabfrage (`pkexec`) – funktioniert unabhängig von
Distribution und Desktop-Umgebung, ganz ohne Terminal. Alternativ jederzeit
manuell: `sudo apt install rclone` oder der Installer von
[rclone.org](https://rclone.org/downloads/).

## Cloud-Remote einrichten

Die eigentliche Verbindung zu einer Cloud (inkl. OAuth-Login/2FA bei
Proton Drive, Google Drive, Dropbox, ...) richtet man einmalig selbst über
rclone im Terminal ein:

```bash
rclone config
```

Beispiele:

- **Proton Drive**: Remote-Typ `protondrive` wählen, Zugangsdaten eingeben
- **Nextcloud/ownCloud**: Remote-Typ `webdav`, Vendor `nextcloud`, Server-URL
  + App-Passwort eingeben
- **Dropbox/Google Drive/S3**: jeweiliger Remote-Typ, Browser-Login folgen

Danach in GuideOSBookHub unter **Einstellungen** ein neues Sync-Profil
anlegen: Namen vergeben, das gerade eingerichtete Remote auswählen (Button
"Remotes aktualisieren", falls es noch nicht in der Liste erscheint),
Dateipfad/-namen und Sync-Intervall festlegen. Einen Ordner in der App über
"Ordner hinzufügen"/"bearbeiten" als Top-Level-Ordner diesem Profil
zuweisen, damit sein Inhalt tatsächlich mitgesynct wird – neu angelegte
Ordner sind standardmäßig rein lokal.

## Bekannte Grenzen

- Kein Locking auf rclone-Ebene: synchronisieren zwei Geräte im selben
  Sekundenfenster, gewinnt der zuletzt schreibende Push (für ein
  persönliches Tool ein akzeptabler Kompromiss).
- Konfliktlösung ist bewusst einfach gehalten (neuere Änderung gewinnt,
  ohne Rückfrage) – siehe `core/sync.py`.

## Entwicklung

```bash
pip install -e .
python3 guideosbookhub.py
```

Tests liegen unter `tests/`.

## Lizenz

GPL-3.0-or-later, siehe [LICENSE](LICENSE).
