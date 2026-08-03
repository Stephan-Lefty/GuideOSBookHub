import sqlite3
from datetime import datetime, timezone
from typing import Optional

from core.database import Database
from core.models import Bookmark, Group, new_uid


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class BookmarkRepository:
    """Einzige Stelle mit SQL-Zugriff. Wird sowohl von der GUI als auch von
    der Sync-Engine (core/sync.py) verwendet."""

    def __init__(self, db: Database):
        self.db = db
        self.conn = db.conn
        self.conn.row_factory = sqlite3.Row

    # ---------- Groups ----------

    def list_groups(self) -> list[Group]:
        cursor = self.conn.execute("SELECT * FROM groups ORDER BY name")
        return [self._row_to_group(row) for row in cursor.fetchall()]

    def get_group(self, group_id: int) -> Optional[Group]:
        cursor = self.conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,))
        row = cursor.fetchone()
        return self._row_to_group(row) if row else None

    def get_group_by_uid(self, uid: str) -> Optional[Group]:
        cursor = self.conn.execute("SELECT * FROM groups WHERE uid = ?", (uid,))
        row = cursor.fetchone()
        return self._row_to_group(row) if row else None

    def add_group(self, name: str, parent_id: Optional[int] = None,
                  profile_id: Optional[str] = None) -> Group:
        uid = new_uid()
        modified = _now()
        cursor = self.conn.execute(
            "INSERT INTO groups (uid, parent_id, name, profile_id, modified) "
            "VALUES (?, ?, ?, ?, ?)",
            (uid, parent_id, name, profile_id, modified),
        )
        self.conn.commit()
        return Group(id=cursor.lastrowid, name=name, parent_id=parent_id,
                     profile_id=profile_id, uid=uid, modified=modified)

    def update_group(self, group_id: int, name: str, parent_id: Optional[int] = None,
                      profile_id: Optional[str] = None) -> None:
        self.conn.execute(
            "UPDATE groups SET name = ?, parent_id = ?, profile_id = ?, modified = ? "
            "WHERE id = ?",
            (name, parent_id, profile_id, _now(), group_id),
        )
        self.conn.commit()

    def assign_unassigned_top_level_groups_to_profile(self, profile_id: str) -> int:
        """Weist alle Top-Level-Ordner ohne Sync-Profil dem übergebenen
        Profil zu (z.B. direkt nach dem Anlegen des ersten Cloud-Profils,
        damit frisch aus dem Browser importierte Ordner ohne manuellen
        Zwischenschritt mitsynchronisiert werden)."""
        groups = self.conn.execute(
            "SELECT id FROM groups WHERE parent_id IS NULL AND profile_id IS NULL"
        ).fetchall()
        for row in groups:
            self.conn.execute(
                "UPDATE groups SET profile_id = ?, modified = ? WHERE id = ?",
                (profile_id, _now(), row["id"]),
            )
        self.conn.commit()
        return len(groups)

    def delete_group(self, group_id: int, cascade: bool = True) -> None:
        if cascade:
            children = self.conn.execute(
                "SELECT id FROM groups WHERE parent_id = ?", (group_id,)
            ).fetchall()
            for child in children:
                self.delete_group(child["id"], cascade=True)
            self.conn.execute("DELETE FROM bookmarks WHERE group_id = ?", (group_id,))
        else:
            self.conn.execute(
                "UPDATE bookmarks SET group_id = NULL WHERE group_id = ?", (group_id,)
            )
            self.conn.execute(
                "UPDATE groups SET parent_id = NULL WHERE parent_id = ?", (group_id,)
            )
        self.conn.execute("DELETE FROM groups WHERE id = ?", (group_id,))
        self.conn.commit()

    # ---------- Bookmarks ----------

    def list_bookmarks(self, group_id: Optional[int] = None, search: str = "",
                        favorites_only: bool = False) -> list[Bookmark]:
        query = "SELECT * FROM bookmarks WHERE 1=1"
        params: list = []

        if group_id is not None:
            query += " AND group_id = ?"
            params.append(group_id)

        if search:
            query += " AND (title LIKE ? OR url LIKE ? OR tags LIKE ?)"
            like = f"%{search}%"
            params += [like, like, like]

        if favorites_only:
            query += " AND favorite = 1"

        query += " ORDER BY title"

        cursor = self.conn.execute(query, params)
        return [self._row_to_bookmark(row) for row in cursor.fetchall()]

    def get_bookmark(self, bookmark_id: int) -> Optional[Bookmark]:
        cursor = self.conn.execute("SELECT * FROM bookmarks WHERE id = ?", (bookmark_id,))
        row = cursor.fetchone()
        return self._row_to_bookmark(row) if row else None

    def get_bookmark_by_uid(self, uid: str) -> Optional[Bookmark]:
        cursor = self.conn.execute("SELECT * FROM bookmarks WHERE uid = ?", (uid,))
        row = cursor.fetchone()
        return self._row_to_bookmark(row) if row else None

    def add_bookmark(self, bookmark: Bookmark) -> Bookmark:
        uid = bookmark.uid or new_uid()
        modified = _now()
        cursor = self.conn.execute(
            "INSERT INTO bookmarks (uid, title, url, description, tags, group_id, favorite, modified) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (uid, bookmark.title, bookmark.url, bookmark.description, bookmark.tags,
             bookmark.group_id, int(bookmark.favorite), modified),
        )
        self.conn.commit()
        bookmark.id = cursor.lastrowid
        bookmark.uid = uid
        bookmark.modified = modified
        return bookmark

    def update_bookmark(self, bookmark: Bookmark) -> None:
        modified = _now()
        self.conn.execute(
            "UPDATE bookmarks SET title = ?, url = ?, description = ?, tags = ?, "
            "group_id = ?, favorite = ?, modified = ? WHERE id = ?",
            (bookmark.title, bookmark.url, bookmark.description, bookmark.tags,
             bookmark.group_id, int(bookmark.favorite), modified, bookmark.id),
        )
        self.conn.commit()
        bookmark.modified = modified

    def delete_bookmark(self, bookmark_id: int) -> None:
        self.conn.execute("DELETE FROM bookmarks WHERE id = ?", (bookmark_id,))
        self.conn.commit()

    def toggle_favorite(self, bookmark_id: int) -> None:
        self.conn.execute(
            "UPDATE bookmarks SET favorite = NOT favorite, modified = ? WHERE id = ?",
            (_now(), bookmark_id),
        )
        self.conn.commit()

    # ---------- Sync support (core/sync.py) ----------

    def all_groups(self) -> list[Group]:
        return self.list_groups()

    def all_bookmarks(self) -> list[Bookmark]:
        return self.list_bookmarks()

    def items_for_profile(self, profile_id: str) -> tuple[list[Group], list[Bookmark]]:
        """Alle Gruppen/Lesezeichen, die (direkt oder vererbt über die
        oberste Vorfahren-Gruppe) zu diesem Sync-Profil gehören. Lesezeichen
        ohne Gruppe gehören zu keinem Profil (bleiben lokal)."""

        all_groups = self.all_groups()
        groups_by_id = {g.id: g for g in all_groups}

        def top_level_profile(group: Group) -> Optional[str]:
            current = group
            while current.parent_id is not None:
                parent = groups_by_id.get(current.parent_id)
                if parent is None:
                    break
                current = parent
            return current.profile_id

        matching_groups = [g for g in all_groups if top_level_profile(g) == profile_id]
        matching_group_ids = {g.id for g in matching_groups}

        matching_bookmarks = [
            b for b in self.all_bookmarks()
            if b.group_id in matching_group_ids
        ]

        return matching_groups, matching_bookmarks

    def upsert_bookmark_by_uid(self, bookmark: Bookmark) -> None:
        """group_id muss vom Aufrufer (Sync-Engine) bereits auf eine lokale
        ID aufgelöst worden sein."""
        existing = self.get_bookmark_by_uid(bookmark.uid)
        if existing:
            self.conn.execute(
                "UPDATE bookmarks SET title = ?, url = ?, description = ?, tags = ?, "
                "group_id = ?, favorite = ?, modified = ? WHERE uid = ?",
                (bookmark.title, bookmark.url, bookmark.description, bookmark.tags,
                 bookmark.group_id, int(bookmark.favorite), bookmark.modified, bookmark.uid),
            )
        else:
            self.conn.execute(
                "INSERT INTO bookmarks (uid, title, url, description, tags, group_id, favorite, modified) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (bookmark.uid, bookmark.title, bookmark.url, bookmark.description, bookmark.tags,
                 bookmark.group_id, int(bookmark.favorite), bookmark.modified),
            )
        self.conn.commit()

    def upsert_group_by_uid(self, group: Group) -> None:
        """parent_id muss vom Aufrufer (Sync-Engine) bereits auf eine lokale
        ID aufgelöst worden sein."""
        existing = self.get_group_by_uid(group.uid)
        if existing:
            self.conn.execute(
                "UPDATE groups SET name = ?, parent_id = ?, profile_id = ?, modified = ? "
                "WHERE uid = ?",
                (group.name, group.parent_id, group.profile_id, group.modified, group.uid),
            )
        else:
            self.conn.execute(
                "INSERT INTO groups (uid, parent_id, name, profile_id, modified) "
                "VALUES (?, ?, ?, ?, ?)",
                (group.uid, group.parent_id, group.name, group.profile_id, group.modified),
            )
        self.conn.commit()

    def delete_bookmark_by_uid(self, uid: str) -> None:
        self.conn.execute("DELETE FROM bookmarks WHERE uid = ?", (uid,))
        self.conn.commit()

    def delete_group_by_uid(self, uid: str) -> None:
        group = self.get_group_by_uid(uid)
        if group:
            self.delete_group(group.id, cascade=True)

    def get_sync_state(self, profile_id: str) -> dict:
        cursor = self.conn.execute(
            "SELECT uid, kind, last_synced_modified, last_synced_hash "
            "FROM sync_state WHERE profile_id = ?",
            (profile_id,),
        )
        return {
            row["uid"]: {
                "kind": row["kind"],
                "last_synced_modified": row["last_synced_modified"],
                "last_synced_hash": row["last_synced_hash"],
            }
            for row in cursor.fetchall()
        }

    def set_sync_state(self, uid: str, profile_id: str, kind: str,
                        modified: str, content_hash: str) -> None:
        self.conn.execute(
            "INSERT INTO sync_state (uid, profile_id, kind, last_synced_modified, last_synced_hash) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(uid, profile_id) DO UPDATE SET "
            "last_synced_modified = excluded.last_synced_modified, "
            "last_synced_hash = excluded.last_synced_hash",
            (uid, profile_id, kind, modified, content_hash),
        )
        self.conn.commit()

    def clear_sync_state(self, uid: str, profile_id: str) -> None:
        self.conn.execute(
            "DELETE FROM sync_state WHERE uid = ? AND profile_id = ?", (uid, profile_id)
        )
        self.conn.commit()

    # ---------- Row conversion ----------

    def _row_to_group(self, row: sqlite3.Row) -> Group:
        return Group(
            id=row["id"],
            name=row["name"],
            parent_id=row["parent_id"],
            profile_id=row["profile_id"],
            uid=row["uid"],
            modified=row["modified"],
        )

    def _row_to_bookmark(self, row: sqlite3.Row) -> Bookmark:
        return Bookmark(
            id=row["id"],
            title=row["title"],
            url=row["url"],
            description=row["description"] or "",
            tags=row["tags"] or "",
            group_id=row["group_id"],
            favorite=bool(row["favorite"]),
            uid=row["uid"],
            modified=row["modified"],
        )
