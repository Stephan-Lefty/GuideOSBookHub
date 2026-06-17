import sqlite3
from pathlib import Path


APP_DIR = (
    Path.home()
    / ".bookmarkhub"
)

APP_DIR.mkdir(
    exist_ok=True
)

DB_FILE = APP_DIR / "bookmarkhub.db"


class Database:

    def __init__(self):

        self.conn = sqlite3.connect(
            DB_FILE
        )

        self.create_tables()

    def create_tables(self):

        cursor = self.conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS groups
        (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id INTEGER,
            name TEXT NOT NULL
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS bookmarks
        (
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

        self.conn.commit()

    def close(self):

        self.conn.close()