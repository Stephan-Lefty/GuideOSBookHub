import time

import pytest

from core import rclone
from core.database import Database
from core.models import Bookmark
from core.repository import BookmarkRepository
from core.sync import SyncEngine

PROFILE = "profile-x"
REMOTE = "fakeremote"
REMOTE_PATH = "bookmarks.json"


@pytest.fixture
def fake_remote_store(monkeypatch):
    """Ersetzt core.rclone.pull_file/push_file durch einen In-Memory-Speicher,
    damit die Sync-Engine ohne echten rclone-Subprozess getestet werden kann."""

    store = {}

    def fake_pull_file(remote, remote_path, timeout=60):
        return store.get((remote, remote_path))

    def fake_push_file(local_path, remote, remote_path, timeout=60):
        with open(local_path) as f:
            store[(remote, remote_path)] = f.read()

    monkeypatch.setattr(rclone, "pull_file", fake_pull_file)
    monkeypatch.setattr(rclone, "push_file", fake_push_file)

    return store


def make_repo():
    db = Database(db_file=":memory:")
    return BookmarkRepository(db)


def test_first_sync_uploads_local_data(fake_remote_store):
    repo = make_repo()
    group = repo.add_group("Arbeit", profile_id=PROFILE)
    repo.add_bookmark(Bookmark(id=None, title="Anthropic", url="https://anthropic.com",
                                group_id=group.id))

    result = SyncEngine(repo, PROFILE, REMOTE, REMOTE_PATH).sync()

    assert result.ok
    assert result.created == 2  # 1 Gruppe + 1 Lesezeichen
    assert (REMOTE, REMOTE_PATH) in fake_remote_store


def test_new_device_downloads_existing_data(fake_remote_store):
    repo_a = make_repo()
    group = repo_a.add_group("Arbeit", profile_id=PROFILE)
    repo_a.add_bookmark(Bookmark(id=None, title="Anthropic", url="https://anthropic.com",
                                  group_id=group.id))
    SyncEngine(repo_a, PROFILE, REMOTE, REMOTE_PATH).sync()

    repo_b = make_repo()
    result_b = SyncEngine(repo_b, PROFILE, REMOTE, REMOTE_PATH).sync()

    assert result_b.ok
    assert {b.title for b in repo_b.list_bookmarks()} == {"Anthropic"}
    assert repo_b.list_bookmarks()[0].group_id == repo_b.list_groups()[0].id


def test_unassigned_groups_are_never_synced(fake_remote_store):
    repo = make_repo()
    local_only = repo.add_group("Lokal")  # kein profile_id
    repo.add_bookmark(Bookmark(id=None, title="Bleibt lokal", url="https://x.test",
                                group_id=local_only.id))

    result = SyncEngine(repo, PROFILE, REMOTE, REMOTE_PATH).sync()

    assert result.ok
    assert result.created == 0
    assert "Bleibt lokal" not in fake_remote_store[(REMOTE, REMOTE_PATH)]


def test_deletion_propagates_via_tombstone(fake_remote_store):
    repo_a = make_repo()
    group = repo_a.add_group("Arbeit", profile_id=PROFILE)
    bm = repo_a.add_bookmark(Bookmark(id=None, title="Weg", url="https://weg.test",
                                       group_id=group.id))
    SyncEngine(repo_a, PROFILE, REMOTE, REMOTE_PATH).sync()

    repo_b = make_repo()
    SyncEngine(repo_b, PROFILE, REMOTE, REMOTE_PATH).sync()
    assert repo_b.list_bookmarks()

    repo_a.delete_bookmark(bm.id)
    SyncEngine(repo_a, PROFILE, REMOTE, REMOTE_PATH).sync()

    SyncEngine(repo_b, PROFILE, REMOTE, REMOTE_PATH).sync()

    assert repo_b.list_bookmarks() == []


def test_conflict_resolution_prefers_newer_change(fake_remote_store):
    repo_a = make_repo()
    group = repo_a.add_group("Arbeit", profile_id=PROFILE)
    bm = repo_a.add_bookmark(Bookmark(id=None, title="Alt", url="https://x.test",
                                       group_id=group.id))
    SyncEngine(repo_a, PROFILE, REMOTE, REMOTE_PATH).sync()

    repo_b = make_repo()
    SyncEngine(repo_b, PROFILE, REMOTE, REMOTE_PATH).sync()

    bm.title = "Von A"
    repo_a.update_bookmark(bm)
    SyncEngine(repo_a, PROFILE, REMOTE, REMOTE_PATH).sync()

    time.sleep(1.1)  # sicherstellen, dass B's Änderung einen späteren Zeitstempel bekommt

    bm_b = repo_b.list_bookmarks()[0]
    bm_b.title = "Von B (neuer)"
    repo_b.update_bookmark(bm_b)
    result_b = SyncEngine(repo_b, PROFILE, REMOTE, REMOTE_PATH).sync()

    assert result_b.conflicts == 1
    assert repo_b.list_bookmarks()[0].title == "Von B (neuer)"

    SyncEngine(repo_a, PROFILE, REMOTE, REMOTE_PATH).sync()
    assert repo_a.list_bookmarks()[0].title == "Von B (neuer)"


def test_sync_reports_pull_error(monkeypatch):
    def raising_pull(remote, remote_path, timeout=60):
        raise rclone.RcloneRemoteError("Verbindung fehlgeschlagen", stderr="auth error")

    monkeypatch.setattr(rclone, "pull_file", raising_pull)

    repo = make_repo()
    result = SyncEngine(repo, PROFILE, REMOTE, REMOTE_PATH).sync()

    assert not result.ok
    assert "Verbindung fehlgeschlagen" in result.errors[0]
