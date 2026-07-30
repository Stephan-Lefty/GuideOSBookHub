import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional

from core import rclone
from core.models import Bookmark, Group
from core.repository import BookmarkRepository

FORMAT_VERSION = 1
TOMBSTONE_RETENTION_DAYS = 30


@dataclass
class SyncResult:
    created: int = 0
    updated: int = 0
    deleted: int = 0
    conflicts: int = 0
    errors: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(fingerprint: dict) -> str:
    return hashlib.sha256(
        json.dumps(fingerprint, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _group_fingerprint(name: str, parent_uid: Optional[str]) -> dict:
    return {"name": name, "parent_uid": parent_uid}


def _bookmark_fingerprint(title, url, description, tags, group_uid, favorite) -> dict:
    return {
        "title": title,
        "url": url,
        "description": description,
        "tags": tags,
        "group_uid": group_uid,
        "favorite": bool(favorite),
    }


class SyncEngine:
    """Synchronisiert genau ein Profil (ein Remote + ein Pfad) zwischen der
    lokalen SQLite-DB und einer einzelnen JSON-Datei in der Cloud. Für
    mehrere Profile wird pro Profil eine eigene Instanz erzeugt."""

    def __init__(self, repo: BookmarkRepository, profile_id: str, remote: str, remote_path: str):
        self.repo = repo
        self.profile_id = profile_id
        self.remote = remote
        self.remote_path = remote_path

    def sync(self) -> SyncResult:
        result = SyncResult()

        try:
            remote_data = self._pull()
        except rclone.RcloneError as e:
            result.errors.append(str(e))
            return result

        sync_state = self.repo.get_sync_state(self.profile_id)
        remote_tombstones = {t["uid"]: t for t in remote_data.get("tombstones", [])}
        outgoing_tombstones = dict(remote_tombstones)

        remote_groups_by_uid = {g["uid"]: g for g in remote_data.get("groups", [])}
        remote_bookmarks_by_uid = {b["uid"]: b for b in remote_data.get("bookmarks", [])}

        self._reconcile_groups(
            remote_groups_by_uid, remote_tombstones, sync_state, outgoing_tombstones, result
        )

        # Nach dem Abgleich der Gruppen neu laden, damit Bookmarks neu
        # angelegte/aktualisierte Gruppen referenzieren können.
        local_groups, local_bookmarks = self.repo.items_for_profile(self.profile_id)
        local_groups_by_uid = {g.uid: g for g in local_groups}

        self._reconcile_bookmarks(
            {b.uid: b for b in local_bookmarks}, remote_bookmarks_by_uid,
            remote_tombstones, local_groups_by_uid, sync_state,
            outgoing_tombstones, result,
        )

        final_groups, final_bookmarks = self.repo.items_for_profile(self.profile_id)
        outgoing = self._build_outgoing(final_groups, final_bookmarks, outgoing_tombstones)

        try:
            self._push(outgoing)
        except rclone.RcloneError as e:
            result.errors.append(str(e))
            return result

        self._finalize_sync_state(final_groups, final_bookmarks)

        return result

    # ---------- Pull / Push ----------

    def _pull(self) -> dict:
        raw = rclone.pull_file(self.remote, self.remote_path)
        if raw is None:
            return {"format_version": FORMAT_VERSION, "groups": [], "bookmarks": [], "tombstones": []}
        return json.loads(raw)

    def _push(self, data: dict) -> None:
        fd, tmp_path = tempfile.mkstemp(suffix=".json")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2)
            rclone.push_file(tmp_path, self.remote, self.remote_path)
        finally:
            os.unlink(tmp_path)

    # ---------- Gruppen ----------

    def _reconcile_groups(self, remote_by_uid, remote_tombstones, sync_state,
                           outgoing_tombstones, result):
        local_groups, _ = self.repo.items_for_profile(self.profile_id)
        local_by_uid = {g.uid: g for g in local_groups}

        group_sync_state = {u: s for u, s in sync_state.items() if s["kind"] == "group"}
        all_uids = set(local_by_uid) | set(remote_by_uid) | set(group_sync_state)

        pending = list(all_uids)
        progress = True
        while pending and progress:
            progress = False
            still_pending = []
            for uid in pending:
                if self._reconcile_one_group(
                    uid, local_by_uid, remote_by_uid, remote_tombstones,
                    group_sync_state, outgoing_tombstones, result,
                ):
                    progress = True
                else:
                    still_pending.append(uid)
            pending = still_pending
        # Gruppen, deren Eltern-Kette nie aufgelöst werden konnte (z.B.
        # kaputte/zyklische Referenz in der Remote-Datei), werden übersprungen
        # statt die Synchronisation abzubrechen.
        for uid in pending:
            result.errors.append(f"Gruppe {uid} konnte nicht aufgelöst werden (fehlende Elterngruppe)")

    def _reconcile_one_group(self, uid, local_by_uid, remote_by_uid, remote_tombstones,
                              known_state, outgoing_tombstones, result) -> bool:
        local_group = local_by_uid.get(uid)
        remote_group = remote_by_uid.get(uid)
        known = known_state.get(uid)
        is_tombstoned = uid in remote_tombstones

        if known is not None and is_tombstoned:
            if local_group is not None:
                self.repo.delete_group_by_uid(uid)
                local_by_uid.pop(uid, None)
            self.repo.clear_sync_state(uid, self.profile_id)
            result.deleted += 1
            return True

        if local_group is None and remote_group is not None and known is None:
            parent_uid = remote_group.get("parent_uid")
            if parent_uid is not None and parent_uid not in local_by_uid:
                return False
            parent_id = local_by_uid[parent_uid].id if parent_uid else None
            new_group = Group(
                id=None, name=remote_group["name"], parent_id=parent_id,
                profile_id=self.profile_id if parent_id is None else None,
                uid=uid, modified=remote_group["modified"],
            )
            self.repo.upsert_group_by_uid(new_group)
            local_by_uid[uid] = self.repo.get_group_by_uid(uid)
            result.created += 1
            return True

        if local_group is not None and remote_group is None and known is None:
            # Neu lokal angelegt, noch nie gesynct -> wird beim Push
            # automatisch mit hochgeladen.
            result.created += 1
            return True

        if known is not None and local_group is None and remote_group is not None:
            # Lokal gelöscht -> Tombstone für den Push erzeugen.
            outgoing_tombstones[uid] = {"uid": uid, "kind": "group", "deleted_at": _now_iso()}
            self.repo.clear_sync_state(uid, self.profile_id)
            result.deleted += 1
            return True

        if local_group is not None and remote_group is not None:
            id_to_uid = {g.id: g.uid for g in local_by_uid.values()}
            local_parent_uid = id_to_uid.get(local_group.parent_id)
            remote_parent_uid = remote_group.get("parent_uid")
            local_fp = _group_fingerprint(local_group.name, local_parent_uid)
            remote_fp = _group_fingerprint(remote_group["name"], remote_parent_uid)
            local_hash = _hash(local_fp)
            remote_hash = _hash(remote_fp)

            if known is None:
                # Beide Seiten haben unabhängig ein Objekt mit derselben uid
                # angelegt (praktisch ausgeschlossen bei UUID4) -> neuere
                # Änderung gewinnt.
                remote_wins = remote_group["modified"] > local_group.modified
            else:
                local_changed = local_hash != known["last_synced_hash"]
                remote_changed = remote_hash != known["last_synced_hash"]
                if local_changed and remote_changed:
                    result.conflicts += 1
                    remote_wins = remote_group["modified"] > local_group.modified
                elif remote_changed:
                    remote_wins = True
                else:
                    remote_wins = False

            if remote_wins:
                if remote_parent_uid is not None and remote_parent_uid not in local_by_uid:
                    return False
                parent_id = local_by_uid[remote_parent_uid].id if remote_parent_uid else None
                updated = Group(
                    id=local_group.id, name=remote_group["name"], parent_id=parent_id,
                    profile_id=local_group.profile_id, uid=uid, modified=remote_group["modified"],
                )
                self.repo.upsert_group_by_uid(updated)
                local_by_uid[uid] = updated
                result.updated += 1
            return True

        return True

    # ---------- Bookmarks ----------

    def _reconcile_bookmarks(self, local_by_uid, remote_by_uid, remote_tombstones,
                              local_groups_by_uid, sync_state, outgoing_tombstones, result):
        bookmark_sync_state = {u: s for u, s in sync_state.items() if s["kind"] == "bookmark"}
        all_uids = set(local_by_uid) | set(remote_by_uid) | set(bookmark_sync_state)
        group_id_to_uid = {g.id: g.uid for g in local_groups_by_uid.values()}

        for uid in all_uids:
            self._reconcile_one_bookmark(
                uid, local_by_uid, remote_by_uid, remote_tombstones,
                local_groups_by_uid, group_id_to_uid, bookmark_sync_state,
                outgoing_tombstones, result,
            )

    def _reconcile_one_bookmark(self, uid, local_by_uid, remote_by_uid, remote_tombstones,
                                 local_groups_by_uid, group_id_to_uid, known_state,
                                 outgoing_tombstones, result):
        local_bm = local_by_uid.get(uid)
        remote_bm = remote_by_uid.get(uid)
        known = known_state.get(uid)
        is_tombstoned = uid in remote_tombstones

        if known is not None and is_tombstoned:
            if local_bm is not None:
                self.repo.delete_bookmark_by_uid(uid)
            self.repo.clear_sync_state(uid, self.profile_id)
            result.deleted += 1
            return

        if local_bm is None and remote_bm is not None and known is None:
            group_uid = remote_bm.get("group_uid")
            group_id = local_groups_by_uid[group_uid].id if group_uid in local_groups_by_uid else None
            new_bm = Bookmark(
                id=None, title=remote_bm["title"], url=remote_bm["url"],
                description=remote_bm.get("description", ""), tags=remote_bm.get("tags", ""),
                group_id=group_id, favorite=remote_bm.get("favorite", False),
                uid=uid, modified=remote_bm["modified"],
            )
            self.repo.upsert_bookmark_by_uid(new_bm)
            result.created += 1
            return

        if local_bm is not None and remote_bm is None and known is None:
            result.created += 1
            return  # wird beim Push mit hochgeladen

        if known is not None and local_bm is None and remote_bm is not None:
            outgoing_tombstones[uid] = {"uid": uid, "kind": "bookmark", "deleted_at": _now_iso()}
            self.repo.clear_sync_state(uid, self.profile_id)
            result.deleted += 1
            return

        if local_bm is not None and remote_bm is not None:
            local_group_uid = group_id_to_uid.get(local_bm.group_id)
            remote_group_uid = remote_bm.get("group_uid")
            local_fp = _bookmark_fingerprint(
                local_bm.title, local_bm.url, local_bm.description, local_bm.tags,
                local_group_uid, local_bm.favorite,
            )
            remote_fp = _bookmark_fingerprint(
                remote_bm["title"], remote_bm["url"], remote_bm.get("description", ""),
                remote_bm.get("tags", ""), remote_group_uid, remote_bm.get("favorite", False),
            )
            local_hash = _hash(local_fp)
            remote_hash = _hash(remote_fp)

            if known is None:
                remote_wins = remote_bm["modified"] > local_bm.modified
            else:
                local_changed = local_hash != known["last_synced_hash"]
                remote_changed = remote_hash != known["last_synced_hash"]
                if local_changed and remote_changed:
                    result.conflicts += 1
                    remote_wins = remote_bm["modified"] > local_bm.modified
                elif remote_changed:
                    remote_wins = True
                else:
                    remote_wins = False

            if remote_wins:
                group_id = (
                    local_groups_by_uid[remote_group_uid].id
                    if remote_group_uid in local_groups_by_uid else None
                )
                updated = Bookmark(
                    id=local_bm.id, title=remote_bm["title"], url=remote_bm["url"],
                    description=remote_bm.get("description", ""), tags=remote_bm.get("tags", ""),
                    group_id=group_id, favorite=remote_bm.get("favorite", False),
                    uid=uid, modified=remote_bm["modified"],
                )
                self.repo.upsert_bookmark_by_uid(updated)
                result.updated += 1

    # ---------- Ausgehende Datei ----------

    def _build_outgoing(self, groups: list[Group], bookmarks: list[Bookmark],
                         tombstones: dict) -> dict:
        groups_by_id = {g.id: g for g in groups}

        cutoff = _now_iso_minus_days(TOMBSTONE_RETENTION_DAYS)
        pruned_tombstones = [
            t for t in tombstones.values() if t["deleted_at"] >= cutoff
        ]

        return {
            "format_version": FORMAT_VERSION,
            "exported_at": _now_iso(),
            "groups": [
                {
                    "uid": g.uid,
                    "name": g.name,
                    "parent_uid": groups_by_id[g.parent_id].uid if g.parent_id in groups_by_id else None,
                    "modified": g.modified,
                }
                for g in groups
            ],
            "bookmarks": [
                {
                    "uid": b.uid,
                    "title": b.title,
                    "url": b.url,
                    "description": b.description,
                    "tags": b.tags,
                    "group_uid": groups_by_id[b.group_id].uid if b.group_id in groups_by_id else None,
                    "favorite": b.favorite,
                    "modified": b.modified,
                }
                for b in bookmarks
            ],
            "tombstones": pruned_tombstones,
        }

    def _finalize_sync_state(self, groups: list[Group], bookmarks: list[Bookmark]) -> None:
        groups_by_id = {g.id: g for g in groups}

        for g in groups:
            parent_uid = groups_by_id[g.parent_id].uid if g.parent_id in groups_by_id else None
            fp = _group_fingerprint(g.name, parent_uid)
            self.repo.set_sync_state(g.uid, self.profile_id, "group", g.modified, _hash(fp))

        for b in bookmarks:
            group_uid = groups_by_id[b.group_id].uid if b.group_id in groups_by_id else None
            fp = _bookmark_fingerprint(b.title, b.url, b.description, b.tags, group_uid, b.favorite)
            self.repo.set_sync_state(b.uid, self.profile_id, "bookmark", b.modified, _hash(fp))


def _now_iso_minus_days(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
