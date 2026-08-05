import base64
import configparser
import datetime
import os
import shutil
import sqlite3
import subprocess
import time
import urllib.parse
from pathlib import Path
from typing import Optional

from core.importer import ImportedBookmark, ImportedFolder

PROCESS_NAMES = ["firefox", "firefox-bin", "firefox-esr"]

# Reihenfolge relevant: zuerst der klassische Pfad, dann distributionsspezifische
# Varianten (Debian patcht Firefox z.B. auf den XDG-konformen .config-Pfad um),
# zuletzt Flatpak (offizielle Flathub-App-ID org.mozilla.firefox).
BASE_DIRS = [
    ".mozilla/firefox",
    ".config/mozilla/firefox",
    ".var/app/org.mozilla.firefox/.mozilla/firefox",
]

# Wohlbekannte, seit Jahren stabile Wurzel-GUIDs von Firefox' Places-Datenbank.
# "tags________" ist kein sichtbarer Lesezeichen-Ordner (Tag-Verwaltung) und
# "root________" ist die unsichtbare Gesamt-Wurzel -- beide bewusst ausgeschlossen.
ROOT_GUIDS = ("toolbar_____", "menu________", "unfiled_____", "mobile______")

TYPE_BOOKMARK = 1
TYPE_FOLDER = 2


def _path_for_section(config: configparser.ConfigParser, section: str, base_dir: Path) -> Optional[Path]:
    if not config.has_option(section, "Path"):
        return None
    raw_path = config.get(section, "Path")
    is_relative = config.getboolean(section, "IsRelative", fallback=True)
    return (base_dir / raw_path) if is_relative else Path(raw_path)


def _resolve_profile_dir(base_dir: Path) -> Optional[Path]:
    """Firefox kann mehrere Profile verwalten; welches eine bestimmte
    Installation tatsächlich verwendet, steht -- falls vorhanden -- in einem
    [InstallXXXX]-Abschnitt und hat Vorrang vor dem allgemeinen Default=1-Flag
    eines [ProfileN]-Abschnitts (seit Firefox 67, Mehrfach-Installations-
    Unterstützung)."""
    profiles_ini = base_dir / "profiles.ini"
    if not profiles_ini.is_file():
        return None

    config = configparser.ConfigParser()
    config.read(profiles_ini, encoding="utf-8")

    profile_sections = [s for s in config.sections() if s.startswith("Profile")]

    install_default_path = None
    for section in config.sections():
        if section.startswith("Install") and config.has_option(section, "Default"):
            install_default_path = config.get(section, "Default")
            break

    if install_default_path is not None:
        for section in profile_sections:
            if config.get(section, "Path", fallback=None) == install_default_path:
                return _path_for_section(config, section, base_dir)

    for section in profile_sections:
        if config.getboolean(section, "Default", fallback=False):
            return _path_for_section(config, section, base_dir)

    if profile_sections:
        return _path_for_section(config, profile_sections[0], base_dir)

    return None


def find_places_db(home: Path = None) -> Optional[Path]:
    home = home if home is not None else Path.home()
    for candidate in BASE_DIRS:
        profile_dir = _resolve_profile_dir(home / candidate)
        if profile_dir is None:
            continue
        db_path = profile_dir / "places.sqlite"
        if db_path.is_file():
            return db_path
    return None


def is_firefox_running(run=subprocess.run) -> bool:
    """Sicherheitsnetz: Firefox sperrt places.sqlite exklusiv, solange es
    läuft -- ein Lesezugriff würde ohnehin mit sqlite3.OperationalError
    fehlschlagen, aber diese Prüfung liefert vorab eine verständliche
    Fehlermeldung statt eines rohen DB-Fehlers."""
    for name in PROCESS_NAMES:
        result = run(["pgrep", "-x", name], capture_output=True, text=True)
        if result.returncode == 0:
            return True
    return False


def _build_children(cursor: sqlite3.Cursor, parent_id: int) -> list:
    cursor.execute(
        "SELECT b.id, b.type, b.title, p.url "
        "FROM moz_bookmarks b LEFT JOIN moz_places p ON b.fk = p.id "
        "WHERE b.parent = ? ORDER BY b.position",
        (parent_id,),
    )
    items = []
    for row_id, node_type, title, url in cursor.fetchall():
        if node_type == TYPE_FOLDER:
            items.append(ImportedFolder(name=title or "", children=_build_children(cursor, row_id)))
        elif node_type == TYPE_BOOKMARK and url:
            items.append(ImportedBookmark(title=title or "", url=url))
        # Separatoren (type == 3) haben in ImportedFolder/ImportedBookmark
        # keine Entsprechung und werden bewusst übersprungen.
    return items


def import_firefox_bookmarks(db_path: Path) -> ImportedFolder:
    """Liest places.sqlite ausschließlich lesend (URI-Modus 'ro') -- niemals
    schreibend, damit unter keinen Umständen versehentlich Firefox' eigene
    Datenbank verändert wird. Schlägt mit sqlite3.OperationalError fehl, wenn
    Firefox noch läuft (places.sqlite ist dann exklusiv gesperrt) -- Aufrufer
    sollten vorher is_firefox_running() prüfen."""
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cursor = connection.cursor()
        root = ImportedFolder(name="")
        for guid in ROOT_GUIDS:
            cursor.execute("SELECT id, title FROM moz_bookmarks WHERE guid = ?", (guid,))
            row = cursor.fetchone()
            if row is None:
                continue
            root_id, title = row
            children = _build_children(cursor, root_id)
            if children:
                root.children.append(ImportedFolder(name=title or "", children=children))
        return root
    finally:
        connection.close()


# ---------- Rück-Export in Firefox ----------
#
# Firefox speichert Lesezeichen -- anders als die Chromium-Familie -- nicht
# als einfache JSON-Datei, sondern in einer SQLite-Datenbank (places.sqlite)
# mit mehreren voneinander abhängigen Tabellen (moz_bookmarks, moz_places,
# moz_origins). Das Schema hat keine Trigger, die abgeleitete Werte wie
# url_hash automatisch berechnen -- diese müssen hier exakt nach Mozillas
# eigenem Algorithmus nachgebaut werden (verifiziert gegen echte
# url_hash-Werte aus einem echten Firefox-Profil, siehe test_firefox_bookmarks.py).
#
# Bewusst NICHT nachgebildet: frecency-Neuberechnung, moz_historyvisits,
# moz_places_metadata und ähnliche rein abgeleitete/optionale Daten -- diese
# aktualisiert Firefox selbst beim nächsten Start. Der für die Anzeige der
# Lesezeichen entscheidende Teil (moz_bookmarks-Baum + moz_places-Grunddaten)
# wird vollständig und korrekt geschrieben.

_GOLDEN_RATIO = 0x9E3779B9
_MASK32 = 0xFFFFFFFF
_MAX_CHARS_TO_HASH = 1500
_PREFIX_SEARCH_WINDOW = 50

TOOLBAR_GUID = "toolbar_____"
SEPARATE_FOLDER_NAME = "GuideOSBookHub (importiert)"


def _rotate_left_5(value: int) -> int:
    return ((value << 5) | (value >> 27)) & _MASK32


def _add_to_hash(hash_value: int, byte: int) -> int:
    return (_GOLDEN_RATIO * (_rotate_left_5(hash_value) ^ byte)) & _MASK32


def _hash_simple(data: bytes) -> int:
    hash_value = 0
    for byte in data:
        hash_value = _add_to_hash(hash_value, byte)
    return hash_value


def _url_hash(url: str) -> int:
    """Portierung von Mozillas HashURL() (toolkit/components/places/Helpers.cpp)
    -- 48-Bit-Hash aus einem 16-Bit-Hash des Schema-Präfixes (obere Bits) und
    einem 32-Bit-Hash der ganzen URL (untere Bits), beide auf maximal die
    ersten 1500 Zeichen begrenzt."""
    data = url.encode("utf-8")[:_MAX_CHARS_TO_HASH]
    colon_index = data[:_PREFIX_SEARCH_WINDOW].find(b":")
    prefix = data[:colon_index] if colon_index != -1 else b""
    prefix_hash = _hash_simple(prefix) & 0xFFFF
    full_hash = _hash_simple(data)
    return (prefix_hash << 32) + full_hash


def _generate_guid() -> str:
    """Firefox-Lesezeichen-GUIDs sind 12 Zeichen aus 9 Zufallsbytes,
    base64url-kodiert (ergibt exakt 12 Zeichen ohne Padding) -- dieselbe
    Technik wie nsNavHistory::GenerateGUID."""
    return base64.urlsafe_b64encode(os.urandom(9)).decode("ascii")


def _now_prtime() -> int:
    """Firefox verwendet PRTime: Mikrosekunden seit der Unix-Epoche (nicht zu
    verwechseln mit Chromiums 1601er-Epoche in core/browser_bookmarks.py)."""
    return int(time.time() * 1_000_000)


def _rev_host(url: str) -> str:
    host = urllib.parse.urlsplit(url).hostname
    if not host:
        return ""
    return host.lower()[::-1] + "."


def _find_or_create_origin(cursor: sqlite3.Cursor, url: str) -> Optional[int]:
    parts = urllib.parse.urlsplit(url)
    if not parts.scheme or not parts.hostname:
        return None  # z.B. about:/data:-URLs ohne Host -- kein Origin-Eintrag nötig
    prefix = f"{parts.scheme}://"
    host = parts.hostname.lower()
    cursor.execute("SELECT id FROM moz_origins WHERE prefix = ? AND host = ?", (prefix, host))
    row = cursor.fetchone()
    if row is not None:
        return row[0]
    cursor.execute(
        "INSERT INTO moz_origins (prefix, host, frecency) VALUES (?, ?, -1)", (prefix, host)
    )
    return cursor.lastrowid


def _find_or_create_place(cursor: sqlite3.Cursor, url: str, title: str) -> int:
    cursor.execute("SELECT id, foreign_count FROM moz_places WHERE url = ?", (url,))
    row = cursor.fetchone()
    if row is not None:
        place_id, foreign_count = row
        cursor.execute(
            "UPDATE moz_places SET foreign_count = ? WHERE id = ?", (foreign_count + 1, place_id)
        )
        return place_id

    origin_id = _find_or_create_origin(cursor, url)
    cursor.execute(
        "INSERT INTO moz_places "
        "(url, title, rev_host, guid, url_hash, foreign_count, origin_id, frecency) "
        "VALUES (?, ?, ?, ?, ?, 1, ?, -1)",
        (url, title, _rev_host(url), _generate_guid(), _url_hash(url), origin_id),
    )
    return cursor.lastrowid


def _create_folder_row(cursor: sqlite3.Cursor, parent_id: int, position: int, title: str) -> int:
    now = _now_prtime()
    cursor.execute(
        "INSERT INTO moz_bookmarks (type, parent, position, title, dateAdded, lastModified, guid) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (TYPE_FOLDER, parent_id, position, title, now, now, _generate_guid()),
    )
    return cursor.lastrowid


def _insert_bookmark_row(
    cursor: sqlite3.Cursor, parent_id: int, position: int, title: str, url: str
) -> None:
    place_id = _find_or_create_place(cursor, url, title)
    now = _now_prtime()
    cursor.execute(
        "INSERT INTO moz_bookmarks "
        "(type, fk, parent, position, title, dateAdded, lastModified, guid) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (TYPE_BOOKMARK, place_id, parent_id, position, title, now, now, _generate_guid()),
    )


def _insert_tree(cursor: sqlite3.Cursor, parent_id: int, nodes: list, start_position: int = 0) -> None:
    for offset, node in enumerate(nodes):
        position = start_position + offset
        if isinstance(node, ImportedFolder):
            folder_id = _create_folder_row(cursor, parent_id, position, node.name)
            _insert_tree(cursor, folder_id, node.children)
        elif isinstance(node, ImportedBookmark):
            _insert_bookmark_row(cursor, parent_id, position, node.title, node.url)


def _next_position(cursor: sqlite3.Cursor, parent_id: int) -> int:
    cursor.execute(
        "SELECT COALESCE(MAX(position), -1) + 1 FROM moz_bookmarks WHERE parent = ?", (parent_id,)
    )
    return cursor.fetchone()[0]


def _existing_folder_id_by_name(cursor: sqlite3.Cursor, parent_id: int, name: str) -> Optional[int]:
    cursor.execute(
        "SELECT id FROM moz_bookmarks WHERE parent = ? AND type = ? AND title = ? "
        "ORDER BY position LIMIT 1",
        (parent_id, TYPE_FOLDER, name),
    )
    row = cursor.fetchone()
    return row[0] if row is not None else None


def _existing_urls_in_folder(cursor: sqlite3.Cursor, parent_id: int) -> set:
    cursor.execute(
        "SELECT p.url FROM moz_bookmarks b JOIN moz_places p ON b.fk = p.id "
        "WHERE b.parent = ? AND b.type = ?",
        (parent_id, TYPE_BOOKMARK),
    )
    return {row[0] for row in cursor.fetchall()}


def _merge_children(cursor: sqlite3.Cursor, parent_id: int, new_items: list) -> None:
    """Gleiche Semantik wie core.browser_bookmarks._merge_children: Ordner
    werden anhand des Namens gefunden/angelegt und rekursiv weiter gemergt,
    Lesezeichen anhand der URL innerhalb desselben Ordners auf Duplikate
    geprüft."""
    existing_urls = _existing_urls_in_folder(cursor, parent_id)
    position = _next_position(cursor, parent_id)

    for item in new_items:
        if isinstance(item, ImportedFolder):
            target_id = _existing_folder_id_by_name(cursor, parent_id, item.name)
            if target_id is None:
                target_id = _create_folder_row(cursor, parent_id, position, item.name)
                position += 1
            _merge_children(cursor, target_id, item.children)
        elif isinstance(item, ImportedBookmark):
            if item.url in existing_urls:
                continue
            _insert_bookmark_row(cursor, parent_id, position, item.title, item.url)
            existing_urls.add(item.url)
            position += 1


def _delete_subtree(cursor: sqlite3.Cursor, bookmark_id: int) -> None:
    cursor.execute("SELECT id FROM moz_bookmarks WHERE parent = ?", (bookmark_id,))
    for (child_id,) in cursor.fetchall():
        _delete_subtree(cursor, child_id)
    cursor.execute("DELETE FROM moz_bookmarks WHERE id = ?", (bookmark_id,))


def _clear_children(cursor: sqlite3.Cursor, parent_id: int) -> None:
    cursor.execute("SELECT id FROM moz_bookmarks WHERE parent = ?", (parent_id,))
    for (child_id,) in cursor.fetchall():
        _delete_subtree(cursor, child_id)


def backup_places_db(db_path: Path) -> Path:
    """Kopiert places.sqlite (inkl. WAL/SHM-Begleitdateien, falls vorhanden)
    unter einem Zeitstempel-Namen, bevor geschrieben wird -- falls beim
    Rück-Export etwas schiefgeht, einfach die Backup-Datei zurückbenennen
    (Firefox muss dabei geschlossen sein)."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = db_path.with_name(f"{db_path.name}.backup-{timestamp}")
    shutil.copy2(db_path, backup_path)
    for suffix in ("-wal", "-shm"):
        sidecar = db_path.with_name(db_path.name + suffix)
        if sidecar.is_file():
            shutil.copy2(sidecar, backup_path.with_name(backup_path.name + suffix))
    return backup_path


def export_to_firefox(db_path: Path, tree: ImportedFolder, strategy: str) -> None:
    """strategy: 'merge' | 'separate_folder' | 'replace'. Schreibt immer in
    die Bookmarks-Toolbar (toolbar_____), analog zu bookmark_bar bei den
    Chromium-Browsern. Aufrufer müssen vorher is_firefox_running() prüfen --
    Firefox sperrt places.sqlite exklusiv, ein Schreibversuch bei laufendem
    Firefox schlägt sonst mit sqlite3.OperationalError fehl."""
    connection = sqlite3.connect(db_path)
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT id FROM moz_bookmarks WHERE guid = ?", (TOOLBAR_GUID,))
        row = cursor.fetchone()
        if row is None:
            raise ValueError("Firefox-Lesezeichenleiste nicht gefunden -- beschädigtes Profil?")
        toolbar_id = row[0]

        if strategy == "replace":
            _clear_children(cursor, toolbar_id)
            _insert_tree(cursor, toolbar_id, tree.children)
        elif strategy == "separate_folder":
            position = _next_position(cursor, toolbar_id)
            folder_id = _create_folder_row(cursor, toolbar_id, position, SEPARATE_FOLDER_NAME)
            _insert_tree(cursor, folder_id, tree.children)
        elif strategy == "merge":
            _merge_children(cursor, toolbar_id, tree.children)
        else:
            raise ValueError(f"Unbekannte Strategie: {strategy}")

        connection.commit()
        cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()
