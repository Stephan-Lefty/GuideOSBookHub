import sqlite3
import uuid
from pathlib import Path


APP_DIR = (
    Path.home()
    / ".guideosbookhub"
)

APP_DIR.mkdir(
    exist_ok=True
)

DB_FILE = APP_DIR / "guideosbookhub.db"


class Database:

    def __init__(self, db_file=None):

        self.conn = sqlite3.connect(
            db_file or DB_FILE
        )

        self.create_tables()
        self.migrate()

    def create_tables(self):

        cursor = self.conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS groups
        (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid TEXT,
            parent_id INTEGER,
            name TEXT NOT NULL,
            profile_id TEXT,
            modified DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)

        self._create_bookmarks_table(cursor)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS sync_state
        (
            uid TEXT NOT NULL,
            profile_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            last_synced_modified TEXT NOT NULL,
            last_synced_hash TEXT NOT NULL,
            PRIMARY KEY (uid, profile_id)
        )
        """)

        self.conn.commit()

    def _create_bookmarks_table(self, cursor):

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS bookmarks
        (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            uid TEXT,

            title TEXT NOT NULL,

            url TEXT NOT NULL,

            description TEXT,

            tags TEXT,

            group_id INTEGER,

            favorite INTEGER DEFAULT 0,

            created DATETIME DEFAULT CURRENT_TIMESTAMP,

            modified DATETIME DEFAULT CURRENT_TIMESTAMP,

            UNIQUE(url, group_id)
        )
        """)

    def migrate(self):
        """Bringt eine bereits existierende Datenbank (altes Schema ohne
        uid/profile_id/sync_state) auf den aktuellen Stand, ohne Daten zu
        verlieren."""

        self._migrate_bookmarks_table()

        self._add_column_if_missing("groups", "uid", "TEXT")
        self._add_column_if_missing("groups", "profile_id", "TEXT")
        self._add_column_if_missing("groups", "modified", "DATETIME")

        self._backfill_missing_uids("groups")
        self._backfill_missing_uids("bookmarks")

        self.conn.commit()

    def _migrate_bookmarks_table(self):
        """Die alte bookmarks-Tabelle hatte UNIQUE(url) statt UNIQUE(url,
        group_id) und keine uid-Spalte. Ein UNIQUE-Constraint lässt sich in
        SQLite nicht per ALTER TABLE ändern, daher wird die Tabelle bei
        Bedarf einmalig neu angelegt und die Daten kopiert (die neue
        Constraint ist eine Lockerung der alten, jede alte Zeile passt also
        garantiert in die neue Tabelle)."""

        cursor = self.conn.cursor()

        cursor.execute("PRAGMA table_info(bookmarks)")
        columns = {row[1] for row in cursor.fetchall()}

        if "uid" in columns:
            return

        cursor.execute("ALTER TABLE bookmarks RENAME TO bookmarks_old")

        self._create_bookmarks_table(cursor)

        cursor.execute("""
            INSERT INTO bookmarks
                (id, title, url, description, tags, group_id, favorite, created, modified)
            SELECT id, title, url, description, tags, group_id, favorite, created, modified
            FROM bookmarks_old
        """)

        cursor.execute("DROP TABLE bookmarks_old")

    def _add_column_if_missing(self, table, column, col_type):

        cursor = self.conn.cursor()

        cursor.execute(f"PRAGMA table_info({table})")
        existing = {row[1] for row in cursor.fetchall()}

        if column not in existing:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")

    def _backfill_missing_uids(self, table):

        cursor = self.conn.cursor()

        cursor.execute(f"SELECT id FROM {table} WHERE uid IS NULL")
        rows = cursor.fetchall()

        for (row_id,) in rows:
            cursor.execute(
                f"UPDATE {table} SET uid = ? WHERE id = ?",
                (str(uuid.uuid4()), row_id)
            )

    def close(self):

        self.conn.close()
