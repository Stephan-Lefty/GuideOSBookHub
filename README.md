# GuideOSBookHub

Ein Lesezeichen-Manager für Debian/Linux, der eigene Lesezeichen lokal
verwaltet und sie über eine **frei wählbare Cloud** zwischen mehreren
Geräten synchronisiert – Nextcloud/WebDAV, Proton Drive, Dropbox, Google
Drive, S3-kompatible Speicher usw. Anders als das Schwesterprojekt
[NEXTBookmarks](../NEXTBookmarks) (Browser-Extension + eigene, fest auf
Nextcloud zugeschnittene Server-App) ist GuideOSBookHub eine eigenständige
Desktop-Anwendung mit eigener Lesezeichen-Verwaltung; es liest keine
Browser-Lesezeichen.

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

## Voraussetzungen

- Python 3.10+
- PyQt6
- [rclone](https://rclone.org) – Debian/Ubuntu: `sudo apt install rclone`
  (für die aktuellste Proton-Drive-Unterstützung ggf. den Installer von
  rclone.org verwenden: `curl https://rclone.org/install.sh | sudo bash`)

## Installation

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

### Als Desktop-Anwendung einbinden

```bash
cp guideosbookhub.desktop ~/.local/share/applications/
```

Falls das Projektverzeichnis an einen anderen Ort verschoben wird, den
`Icon=`-Pfad in `guideosbookhub.desktop` entsprechend anpassen.

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
