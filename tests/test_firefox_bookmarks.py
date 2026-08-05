import sqlite3

import pytest

from core.firefox_bookmarks import (
    backup_places_db, export_to_firefox, find_places_db, import_firefox_bookmarks,
    is_firefox_running, _url_hash,
)
from core.importer import ImportedBookmark, ImportedFolder

PROFILES_INI_SINGLE_DEFAULT = """\
[Profile0]
Name=default-release
IsRelative=1
Path=abc123.default-release
Default=1

[General]
StartWithLastProfile=1
Version=2
"""

PROFILES_INI_WITH_INSTALL_OVERRIDE = """\
[Install4F96D1932A9F858E]
Default=xyz789.default-release
Locked=1

[Profile1]
Name=default
IsRelative=1
Path=abc123.default
Default=1

[Profile0]
Name=default-release
IsRelative=1
Path=xyz789.default-release

[General]
StartWithLastProfile=1
Version=2
"""


def _write_profiles_ini(base_dir, content):
    base_dir.mkdir(parents=True, exist_ok=True)
    (base_dir / "profiles.ini").write_text(content, encoding="utf-8")


def test_find_places_db_uses_default_flagged_profile(tmp_path):
    base_dir = tmp_path / ".mozilla" / "firefox"
    _write_profiles_ini(base_dir, PROFILES_INI_SINGLE_DEFAULT)
    profile_dir = base_dir / "abc123.default-release"
    profile_dir.mkdir(parents=True)
    db_path = profile_dir / "places.sqlite"
    db_path.write_text("")

    assert find_places_db(home=tmp_path) == db_path


def test_find_places_db_prefers_install_section_override(tmp_path):
    base_dir = tmp_path / ".mozilla" / "firefox"
    _write_profiles_ini(base_dir, PROFILES_INI_WITH_INSTALL_OVERRIDE)
    # "falscher" Default=1-Profilordner existiert absichtlich nicht --
    # müsste ignoriert werden, da der [InstallXXXX]-Abschnitt Vorrang hat.
    profile_dir = base_dir / "xyz789.default-release"
    profile_dir.mkdir(parents=True)
    db_path = profile_dir / "places.sqlite"
    db_path.write_text("")

    assert find_places_db(home=tmp_path) == db_path


def test_find_places_db_falls_back_through_candidate_base_dirs(tmp_path):
    # Kein ~/.mozilla/firefox, aber der Debian-XDG-Pfad ~/.config/mozilla/firefox.
    base_dir = tmp_path / ".config" / "mozilla" / "firefox"
    _write_profiles_ini(base_dir, PROFILES_INI_SINGLE_DEFAULT)
    profile_dir = base_dir / "abc123.default-release"
    profile_dir.mkdir(parents=True)
    db_path = profile_dir / "places.sqlite"
    db_path.write_text("")

    assert find_places_db(home=tmp_path) == db_path


def test_find_places_db_returns_none_when_nothing_found(tmp_path):
    assert find_places_db(home=tmp_path) is None


def _create_places_db(db_path):
    connection = sqlite3.connect(db_path)
    connection.executescript("""
        CREATE TABLE moz_places (id INTEGER PRIMARY KEY, url LONGVARCHAR, title LONGVARCHAR);
        CREATE TABLE moz_bookmarks (
            id INTEGER PRIMARY KEY, type INTEGER, fk INTEGER, parent INTEGER,
            position INTEGER, title LONGVARCHAR, guid TEXT
        );
    """)
    connection.executemany(
        "INSERT INTO moz_bookmarks (id, type, fk, parent, position, title, guid) VALUES (?,?,?,?,?,?,?)",
        [
            (1, 2, None, 0, 0, "", "root________"),
            (2, 2, None, 1, 0, "menu", "menu________"),
            (3, 2, None, 1, 1, "toolbar", "toolbar_____"),
            (4, 2, None, 1, 2, "tags", "tags________"),
            (5, 2, None, 1, 3, "unfiled", "unfiled_____"),
            (6, 2, None, 1, 4, "mobile", "mobile______"),
            # Lesezeichenleiste: eine URL + ein Unterordner mit einer weiteren URL
            (7, 1, 100, 3, 0, "Example", "aaaaaaaaaaaa"),
            (8, 2, None, 3, 1, "Unterordner", "bbbbbbbbbbbb"),
            (9, 1, 101, 8, 0, "Nested", "cccccccccccc"),
            # Separator in der Leiste -- muss ignoriert werden
            (10, 3, None, 3, 2, "", "dddddddddddd"),
            # "unfiled" bleibt leer -> darf im Ergebnis nicht auftauchen
        ],
    )
    connection.executemany(
        "INSERT INTO moz_places (id, url, title) VALUES (?,?,?)",
        [
            (100, "https://example.com", "Example"),
            (101, "https://nested.example.com", "Nested"),
        ],
    )
    connection.commit()
    connection.close()


def test_import_firefox_bookmarks_builds_tree_and_skips_empty_roots_and_separators(tmp_path):
    db_path = tmp_path / "places.sqlite"
    _create_places_db(db_path)

    root = import_firefox_bookmarks(db_path)

    assert len(root.children) == 1  # nur "toolbar", "menu"/"unfiled"/"mobile" sind leer
    toolbar = root.children[0]
    assert isinstance(toolbar, ImportedFolder)
    assert toolbar.name == "toolbar"

    example, subfolder = toolbar.children
    assert example == ImportedBookmark(title="Example", url="https://example.com")
    assert isinstance(subfolder, ImportedFolder)
    assert subfolder.name == "Unterordner"
    assert subfolder.children == [
        ImportedBookmark(title="Nested", url="https://nested.example.com")
    ]


class _FakePgrepResult:
    def __init__(self, returncode):
        self.returncode = returncode


def test_is_firefox_running_true_when_process_found():
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        return _FakePgrepResult(0 if args[-1] == "firefox-bin" else 1)

    assert is_firefox_running(run=fake_run) is True
    assert calls == [["pgrep", "-x", "firefox"], ["pgrep", "-x", "firefox-bin"]]


def test_is_firefox_running_false_when_no_process_found():
    assert is_firefox_running(run=lambda *a, **k: _FakePgrepResult(1)) is False


# ---------- Export ----------

# Echte (url, url_hash)-Paare aus einem echten Firefox-Profil (Firefox 151) --
# verifiziert die Portierung von Mozillas HashURL()-Algorithmus bit-genau,
# nicht nur strukturell.
REAL_URL_HASH_PAIRS = [
    ("https://support.mozilla.org/products/firefox", 47358327123126),
    (
        "https://support.mozilla.org/kb/customize-firefox-controls-buttons-and-toolbars"
        "?utm_source=firefox-browser&utm_medium=default-bookmarks&utm_campaign=customize",
        47359956450016,
    ),
    ("https://www.mozilla.org/contribute/", 47357364218428),
    ("https://www.mozilla.org/about/", 47357608426557),
]


@pytest.mark.parametrize("url,expected_hash", REAL_URL_HASH_PAIRS)
def test_url_hash_matches_real_firefox_values(url, expected_hash):
    assert _url_hash(url) == expected_hash


def _create_full_places_db(db_path):
    """Baut das reale places.sqlite-Schema minimal nach (alle Spalten, die
    export_to_firefox tatsächlich liest/schreibt) und legt die vier
    Standard-Wurzelordner an, wie sie jedes echte Firefox-Profil hat."""
    connection = sqlite3.connect(db_path)
    connection.executescript("""
        CREATE TABLE moz_origins (
            id INTEGER PRIMARY KEY, prefix TEXT NOT NULL, host TEXT NOT NULL,
            frecency INTEGER NOT NULL
        );
        CREATE TABLE moz_places (
            id INTEGER PRIMARY KEY, url LONGVARCHAR, title LONGVARCHAR,
            rev_host LONGVARCHAR, guid TEXT, url_hash INTEGER DEFAULT 0,
            foreign_count INTEGER DEFAULT 0, origin_id INTEGER, frecency INTEGER DEFAULT -1
        );
        CREATE UNIQUE INDEX moz_places_guid_uniqueindex ON moz_places (guid);
        CREATE TABLE moz_bookmarks (
            id INTEGER PRIMARY KEY, type INTEGER, fk INTEGER DEFAULT NULL,
            parent INTEGER, position INTEGER, title LONGVARCHAR,
            dateAdded INTEGER, lastModified INTEGER, guid TEXT
        );
        CREATE UNIQUE INDEX moz_bookmarks_guid_uniqueindex ON moz_bookmarks (guid);
    """)
    connection.executemany(
        "INSERT INTO moz_bookmarks (id, type, fk, parent, position, title, guid) VALUES (?,?,?,?,?,?,?)",
        [
            (1, 2, None, 0, 0, "", "root________"),
            (2, 2, None, 1, 0, "menu", "menu________"),
            (3, 2, None, 1, 1, "toolbar", "toolbar_____"),
            (4, 2, None, 1, 2, "tags", "tags________"),
            (5, 2, None, 1, 3, "unfiled", "unfiled_____"),
            (6, 2, None, 1, 4, "mobile", "mobile______"),
        ],
    )
    connection.commit()
    connection.close()


def _toolbar_tree(db_path) -> ImportedFolder:
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT id FROM moz_bookmarks WHERE guid = 'toolbar_____'")
        (toolbar_id,) = cursor.fetchone()
        from core.firefox_bookmarks import _build_children
        return ImportedFolder(name="toolbar", children=_build_children(cursor, toolbar_id))
    finally:
        connection.close()


def _new_tree() -> ImportedFolder:
    return ImportedFolder(name="", children=[
        ImportedBookmark(title="New", url="https://new.example.com"),
    ])


def test_export_replace_overwrites_toolbar_children(tmp_path):
    db_path = tmp_path / "places.sqlite"
    _create_full_places_db(db_path)
    export_to_firefox(db_path, ImportedFolder(name="", children=[
        ImportedBookmark(title="Existing", url="https://existing.example.com"),
    ]), "replace")

    export_to_firefox(db_path, _new_tree(), "replace")

    toolbar = _toolbar_tree(db_path)
    urls = {c.url for c in toolbar.children if isinstance(c, ImportedBookmark)}
    assert urls == {"https://new.example.com"}


def test_export_separate_folder_keeps_existing_and_appends(tmp_path):
    db_path = tmp_path / "places.sqlite"
    _create_full_places_db(db_path)
    export_to_firefox(db_path, ImportedFolder(name="", children=[
        ImportedBookmark(title="Existing", url="https://existing.example.com"),
    ]), "replace")

    export_to_firefox(db_path, _new_tree(), "separate_folder")

    toolbar = _toolbar_tree(db_path)
    names = {c.name for c in toolbar.children if isinstance(c, ImportedFolder)}
    assert "GuideOSBookHub (importiert)" in names
    existing_urls = {c.url for c in toolbar.children if isinstance(c, ImportedBookmark)}
    assert existing_urls == {"https://existing.example.com"}
    new_folder = next(c for c in toolbar.children if getattr(c, "name", None) == "GuideOSBookHub (importiert)")
    assert {c.url for c in new_folder.children} == {"https://new.example.com"}


def test_export_merge_adds_new_and_skips_duplicate_urls(tmp_path):
    db_path = tmp_path / "places.sqlite"
    _create_full_places_db(db_path)
    export_to_firefox(db_path, ImportedFolder(name="", children=[
        ImportedBookmark(title="Existing", url="https://existing.example.com"),
    ]), "replace")

    export_to_firefox(db_path, ImportedFolder(name="", children=[
        ImportedBookmark(title="New", url="https://new.example.com"),
        ImportedBookmark(title="Existing again", url="https://existing.example.com"),
    ]), "merge")

    toolbar = _toolbar_tree(db_path)
    urls = {c.url for c in toolbar.children if isinstance(c, ImportedBookmark)}
    assert urls == {"https://existing.example.com", "https://new.example.com"}


def test_export_merge_recurses_into_matching_folder_by_name(tmp_path):
    db_path = tmp_path / "places.sqlite"
    _create_full_places_db(db_path)
    export_to_firefox(db_path, ImportedFolder(name="", children=[
        ImportedFolder(name="Arbeit", children=[
            ImportedBookmark(title="A", url="https://a.example.com"),
        ]),
    ]), "replace")

    export_to_firefox(db_path, ImportedFolder(name="", children=[
        ImportedFolder(name="Arbeit", children=[
            ImportedBookmark(title="B", url="https://b.example.com"),
        ]),
    ]), "merge")

    toolbar = _toolbar_tree(db_path)
    assert len(toolbar.children) == 1  # kein zweiter "Arbeit"-Ordner angelegt
    work_folder = toolbar.children[0]
    assert work_folder.name == "Arbeit"
    urls = {c.url for c in work_folder.children}
    assert urls == {"https://a.example.com", "https://b.example.com"}


def test_export_reuses_existing_moz_places_row_and_increments_foreign_count(tmp_path):
    db_path = tmp_path / "places.sqlite"
    _create_full_places_db(db_path)
    export_to_firefox(db_path, ImportedFolder(name="", children=[
        ImportedBookmark(title="Shared", url="https://shared.example.com"),
    ]), "separate_folder")
    export_to_firefox(db_path, ImportedFolder(name="", children=[
        ImportedBookmark(title="Shared again", url="https://shared.example.com"),
    ]), "separate_folder")

    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()
    cursor.execute(
        "SELECT COUNT(*), MAX(foreign_count) FROM moz_places WHERE url = ?",
        ("https://shared.example.com",),
    )
    count, foreign_count = cursor.fetchone()
    connection.close()

    assert count == 1  # nur eine moz_places-Zeile für dieselbe URL
    assert foreign_count == 2  # zweimal referenziert


def test_export_populates_url_hash_matching_real_algorithm(tmp_path):
    db_path = tmp_path / "places.sqlite"
    _create_full_places_db(db_path)
    url, expected_hash = REAL_URL_HASH_PAIRS[0]
    export_to_firefox(db_path, ImportedFolder(name="", children=[
        ImportedBookmark(title="X", url=url),
    ]), "replace")

    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()
    cursor.execute("SELECT url_hash FROM moz_places WHERE url = ?", (url,))
    (stored_hash,) = cursor.fetchone()
    connection.close()

    assert stored_hash == expected_hash


def test_backup_places_db_creates_timestamped_copy(tmp_path):
    db_path = tmp_path / "places.sqlite"
    db_path.write_text("original content")

    backup_path = backup_places_db(db_path)

    assert backup_path.is_file()
    assert backup_path.read_text() == "original content"
    assert backup_path.name.startswith("places.sqlite.backup-")


def test_backup_places_db_copies_wal_and_shm_sidecars_when_present(tmp_path):
    db_path = tmp_path / "places.sqlite"
    db_path.write_text("original content")
    (tmp_path / "places.sqlite-wal").write_text("wal content")
    (tmp_path / "places.sqlite-shm").write_text("shm content")

    backup_path = backup_places_db(db_path)

    assert (backup_path.parent / f"{backup_path.name}-wal").read_text() == "wal content"
    assert (backup_path.parent / f"{backup_path.name}-shm").read_text() == "shm content"


def test_export_then_import_round_trips_full_tree(tmp_path):
    db_path = tmp_path / "places.sqlite"
    _create_full_places_db(db_path)
    tree = ImportedFolder(name="", children=[
        ImportedBookmark(title="Top", url="https://top.example.com"),
        ImportedFolder(name="Sub", children=[
            ImportedBookmark(title="Nested", url="https://nested.example.com"),
        ]),
    ])

    export_to_firefox(db_path, tree, "replace")
    imported = import_firefox_bookmarks(db_path)

    assert len(imported.children) == 1
    toolbar = imported.children[0]
    assert toolbar.name == "toolbar"
    top, sub = toolbar.children
    assert top == ImportedBookmark(title="Top", url="https://top.example.com")
    assert isinstance(sub, ImportedFolder)
    assert sub.name == "Sub"
    assert sub.children == [ImportedBookmark(title="Nested", url="https://nested.example.com")]
