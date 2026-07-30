import pytest

from core.database import Database
from core.models import Bookmark
from core.repository import BookmarkRepository


@pytest.fixture
def repo():
    db = Database(db_file=":memory:")
    yield BookmarkRepository(db)
    db.close()


def test_add_and_list_bookmark(repo):
    repo.add_bookmark(Bookmark(id=None, title="Test", url="https://example.com"))

    bookmarks = repo.list_bookmarks()

    assert len(bookmarks) == 1
    assert bookmarks[0].title == "Test"
    assert bookmarks[0].uid


def test_group_hierarchy_and_cascade_delete(repo):
    parent = repo.add_group("Parent")
    child = repo.add_group("Child", parent_id=parent.id)
    repo.add_bookmark(Bookmark(id=None, title="X", url="https://x.test", group_id=child.id))

    repo.delete_group(parent.id, cascade=True)

    assert repo.list_groups() == []
    assert repo.list_bookmarks() == []


def test_search_and_favorites(repo):
    b1 = repo.add_bookmark(Bookmark(id=None, title="Anthropic", url="https://anthropic.com"))
    repo.add_bookmark(Bookmark(id=None, title="Python", url="https://python.org"))
    repo.toggle_favorite(b1.id)

    assert [b.title for b in repo.list_bookmarks(search="anthro")] == ["Anthropic"]
    assert [b.title for b in repo.list_bookmarks(favorites_only=True)] == ["Anthropic"]


def test_items_for_profile_respects_inheritance(repo):
    top = repo.add_group("Top", profile_id="profile-a")
    sub = repo.add_group("Sub", parent_id=top.id)
    other_top = repo.add_group("Other")  # kein Profil -> bleibt lokal

    repo.add_bookmark(Bookmark(id=None, title="In Sub", url="https://a.test", group_id=sub.id))
    repo.add_bookmark(Bookmark(id=None, title="Local", url="https://b.test", group_id=other_top.id))

    groups, bookmarks = repo.items_for_profile("profile-a")

    assert {g.name for g in groups} == {"Top", "Sub"}
    assert {b.title for b in bookmarks} == {"In Sub"}


def test_upsert_bookmark_by_uid_inserts_then_updates(repo):
    bm = Bookmark(id=None, title="Original", url="https://x.test", uid="fixed-uid",
                  modified="2026-01-01T00:00:00+00:00")
    repo.upsert_bookmark_by_uid(bm)
    assert repo.get_bookmark_by_uid("fixed-uid").title == "Original"

    bm.title = "Geändert"
    repo.upsert_bookmark_by_uid(bm)

    assert len(repo.list_bookmarks()) == 1
    assert repo.get_bookmark_by_uid("fixed-uid").title == "Geändert"


def test_sync_state_roundtrip(repo):
    repo.set_sync_state("uid-1", "profile-a", "bookmark", "2026-01-01T00:00:00+00:00", "hash123")

    state = repo.get_sync_state("profile-a")
    assert state["uid-1"]["last_synced_hash"] == "hash123"

    repo.clear_sync_state("uid-1", "profile-a")
    assert repo.get_sync_state("profile-a") == {}
