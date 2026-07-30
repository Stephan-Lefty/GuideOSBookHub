from core.database import Database


def test_database_creation():

    db = Database(db_file=":memory:")

    assert db is not None

    db.close()


def test_schema_has_expected_tables():

    db = Database(db_file=":memory:")

    cursor = db.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}

    assert {"groups", "bookmarks", "sync_state"} <= tables

    db.close()


def test_migrate_upgrades_legacy_schema_without_data_loss():
    """Simuliert eine bereits existierende DB im alten Schema (vor uid/
    profile_id/sync_state) und prüft, dass die Migration bestehende Daten
    erhält."""

    db = Database.__new__(Database)
    import sqlite3
    db.conn = sqlite3.connect(":memory:")

    db.conn.execute("""
        CREATE TABLE groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id INTEGER,
            name TEXT NOT NULL
        )
    """)
    db.conn.execute("""
        CREATE TABLE bookmarks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE,
            description TEXT,
            tags TEXT,
            group_id INTEGER,
            favorite INTEGER DEFAULT 0,
            created DATETIME DEFAULT CURRENT_TIMESTAMP,
            modified DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.conn.execute("INSERT INTO groups (parent_id, name) VALUES (NULL, 'Alt')")
    db.conn.execute(
        "INSERT INTO bookmarks (title, url) VALUES ('Bestand', 'https://bestand.test')"
    )
    db.conn.commit()

    db.create_tables()
    db.migrate()

    groups = db.conn.execute("SELECT name, uid FROM groups").fetchall()
    bookmarks = db.conn.execute("SELECT title, uid FROM bookmarks").fetchall()

    assert groups[0][0] == "Alt"
    assert groups[0][1] is not None
    assert bookmarks[0][0] == "Bestand"
    assert bookmarks[0][1] is not None

    db.close()
