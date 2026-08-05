import json

import pytest

from core.browser_bookmarks import (
    BrowserDefinition, export_to_chromium_json, find_bookmarks_file, find_export_target,
    is_browser_running, parse_chromium_bookmarks, repository_to_tree,
)
from core.database import Database
from core.importer import ImportedBookmark, ImportedFolder, import_into_repository
from core.repository import BookmarkRepository


@pytest.fixture
def repo():
    db = Database(db_file=":memory:")
    yield BookmarkRepository(db)
    db.close()


SAMPLE_CHROMIUM_JSON = json.dumps({
    "checksum": "abc123",
    "roots": {
        "bookmark_bar": {
            "name": "Lesezeichenleiste",
            "type": "folder",
            "children": [
                {"name": "Example", "type": "url", "url": "https://example.com"},
                {
                    "name": "Unterordner",
                    "type": "folder",
                    "children": [
                        {"name": "Nested", "type": "url", "url": "https://nested.example.com"},
                    ],
                },
            ],
        },
        "other": {
            "name": "Weitere Lesezeichen",
            "type": "folder",
            "children": [
                {"name": "Loose", "type": "url", "url": "https://loose.example.com"},
            ],
        },
        "synced": {
            "name": "Mobile Lesezeichen",
            "type": "folder",
            "children": [],
        },
        "trash": {
            "name": "Papierkorb",
            "type": "folder",
            "children": [
                {"name": "Deleted", "type": "url", "url": "https://deleted.example.com"},
            ],
        },
    },
    "version": 1,
})


def test_parse_chromium_bookmarks_builds_folder_tree():
    root = parse_chromium_bookmarks(SAMPLE_CHROMIUM_JSON)

    assert len(root.children) == 2  # "synced" ist leer -> übersprungen, "trash" ignoriert
    toolbar, other = root.children

    assert isinstance(toolbar, ImportedFolder)
    assert toolbar.name == "Lesezeichenleiste"
    assert other.name == "Weitere Lesezeichen"
    assert other.children == [ImportedBookmark(title="Loose", url="https://loose.example.com")]

    example, subfolder = toolbar.children
    assert example == ImportedBookmark(title="Example", url="https://example.com")
    assert isinstance(subfolder, ImportedFolder)
    assert subfolder.name == "Unterordner"
    assert subfolder.children == [
        ImportedBookmark(title="Nested", url="https://nested.example.com")
    ]


def test_find_bookmarks_file_returns_existing_path(tmp_path):
    profile_dir = tmp_path / ".config" / "vivaldi" / "Default"
    profile_dir.mkdir(parents=True)
    bookmarks_file = profile_dir / "Bookmarks"
    bookmarks_file.write_text("{}")

    browser = BrowserDefinition(
        "vivaldi", "Vivaldi", [".config/vivaldi/Default/Bookmarks"]
    )

    assert find_bookmarks_file(browser, home=tmp_path) == bookmarks_file


def test_find_bookmarks_file_returns_none_when_missing(tmp_path):
    browser = BrowserDefinition(
        "vivaldi", "Vivaldi", [".config/vivaldi/Default/Bookmarks"]
    )

    assert find_bookmarks_file(browser, home=tmp_path) is None


def test_find_export_target_returns_existing_bookmarks_file(tmp_path):
    profile_dir = tmp_path / ".config" / "vivaldi" / "Default"
    profile_dir.mkdir(parents=True)
    bookmarks_file = profile_dir / "Bookmarks"
    bookmarks_file.write_text("{}")

    browser = BrowserDefinition(
        "vivaldi", "Vivaldi", [".config/vivaldi/Default/Bookmarks"]
    )

    assert find_export_target(browser, home=tmp_path) == bookmarks_file


def test_find_export_target_returns_target_path_when_profile_exists_without_bookmarks(tmp_path):
    # Neu installierte Browser legen die Bookmarks-Datei oft erst beim ersten
    # selbst gesetzten Lesezeichen an, nicht schon beim ersten Start.
    profile_dir = tmp_path / ".config" / "vivaldi" / "Default"
    profile_dir.mkdir(parents=True)

    browser = BrowserDefinition(
        "vivaldi", "Vivaldi", [".config/vivaldi/Default/Bookmarks"]
    )

    assert find_export_target(browser, home=tmp_path) == profile_dir / "Bookmarks"


def test_find_export_target_returns_none_when_profile_dir_missing(tmp_path):
    browser = BrowserDefinition(
        "vivaldi", "Vivaldi", [".config/vivaldi/Default/Bookmarks"]
    )

    assert find_export_target(browser, home=tmp_path) is None


def test_end_to_end_parse_and_import(repo):
    root = parse_chromium_bookmarks(SAMPLE_CHROMIUM_JSON)

    result = import_into_repository(repo, root)

    assert result.groups_created == 3  # Lesezeichenleiste, Unterordner, Weitere Lesezeichen
    assert result.bookmarks_created == 3

    groups_by_name = {g.name: g for g in repo.list_groups()}
    assert groups_by_name.keys() == {"Lesezeichenleiste", "Unterordner", "Weitere Lesezeichen"}

    bookmarks = repo.list_bookmarks()
    assert {b.url for b in bookmarks} == {
        "https://example.com", "https://nested.example.com", "https://loose.example.com"
    }


def test_repository_to_tree_round_trips_import(repo):
    root = parse_chromium_bookmarks(SAMPLE_CHROMIUM_JSON)
    import_into_repository(repo, root)

    tree = repository_to_tree(repo)

    names_and_types = {
        (item.name if isinstance(item, ImportedFolder) else item.title)
        for item in tree.children
    }
    assert names_and_types == {"Lesezeichenleiste", "Weitere Lesezeichen"}

    toolbar = next(i for i in tree.children if i.name == "Lesezeichenleiste")
    urls = {i.url for i in toolbar.children if isinstance(i, ImportedBookmark)}
    assert urls == {"https://example.com"}
    subfolder = next(i for i in toolbar.children if isinstance(i, ImportedFolder))
    assert subfolder.name == "Unterordner"
    assert subfolder.children == [
        ImportedBookmark(title="Nested", url="https://nested.example.com")
    ]


EXISTING_BROWSER_JSON = json.dumps({
    "checksum": "old",
    "roots": {
        "bookmark_bar": {
            "id": "5", "name": "Bookmarks bar", "type": "folder",
            "children": [
                {"id": "6", "name": "Existing", "type": "url", "url": "https://existing.example.com"},
                {
                    "id": "7", "name": "Unterordner", "type": "folder",
                    "children": [
                        {"id": "8", "name": "AlreadyThere", "type": "url",
                         "url": "https://nested.example.com"},
                    ],
                },
            ],
        },
        "other": {"id": "2", "name": "Other bookmarks", "type": "folder", "children": []},
        "synced": {"id": "3", "name": "Mobile bookmarks", "type": "folder", "children": []},
    },
    "version": 1,
})


def _simple_export_tree():
    return ImportedFolder(name="", children=[
        ImportedBookmark(title="New", url="https://new.example.com"),
        ImportedFolder(name="Unterordner", children=[
            ImportedBookmark(title="Nested", url="https://nested.example.com"),
        ]),
    ])


def test_export_replace_overwrites_bookmark_bar():
    result = json.loads(export_to_chromium_json(EXISTING_BROWSER_JSON, _simple_export_tree(), "replace"))

    bar_children = result["roots"]["bookmark_bar"]["children"]
    urls = {c["url"] for c in bar_children if c["type"] == "url"}
    assert urls == {"https://new.example.com"}
    assert "checksum" not in result


def test_export_separate_folder_keeps_existing_and_appends():
    result = json.loads(
        export_to_chromium_json(EXISTING_BROWSER_JSON, _simple_export_tree(), "separate_folder")
    )

    bar_children = result["roots"]["bookmark_bar"]["children"]
    names = {c["name"] for c in bar_children}
    assert "Existing" in names
    new_folder = next(c for c in bar_children if c["name"] == "GuideOSBookHub (importiert)")
    assert {c.get("url") for c in new_folder["children"] if c["type"] == "url"} == {
        "https://new.example.com"
    }


def test_export_merge_adds_new_and_skips_duplicate_urls():
    result = json.loads(export_to_chromium_json(EXISTING_BROWSER_JSON, _simple_export_tree(), "merge"))

    bar_children = result["roots"]["bookmark_bar"]["children"]
    top_urls = {c["url"] for c in bar_children if c["type"] == "url"}
    assert top_urls == {"https://existing.example.com", "https://new.example.com"}


def test_export_without_existing_bookmarks_file_builds_from_empty_state():
    # find_export_target liefert einen Zielpfad, auch wenn der Browser noch
    # keine eigene Bookmarks-Datei angelegt hat (frisch installiert/gestartet).
    result = json.loads(export_to_chromium_json(None, _simple_export_tree(), "replace"))

    bar_children = result["roots"]["bookmark_bar"]["children"]
    urls = {c["url"] for c in bar_children if c["type"] == "url"}
    assert urls == {"https://new.example.com"}

    subfolder = next(c for c in bar_children if c["name"] == "Unterordner")
    nested_urls = [c["url"] for c in subfolder["children"] if c["type"] == "url"]
    assert nested_urls == ["https://nested.example.com"]  # kein Duplikat trotz zweiten Imports


def test_export_generates_unique_ids_continuing_from_existing_max():
    result = json.loads(export_to_chromium_json(EXISTING_BROWSER_JSON, _simple_export_tree(), "merge"))

    all_ids = []

    def collect(node):
        if "id" in node:
            all_ids.append(node["id"])
        for child in node.get("children", []):
            collect(child)

    for root_node in result["roots"].values():
        collect(root_node)

    assert len(all_ids) == len(set(all_ids))  # keine Kollisionen


class _FakePgrepResult:
    def __init__(self, returncode):
        self.returncode = returncode


def test_is_browser_running_true_when_process_found():
    browser = BrowserDefinition("vivaldi", "Vivaldi", [], ["vivaldi", "vivaldi-bin"])
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        return _FakePgrepResult(0 if args[-1] == "vivaldi-bin" else 1)

    assert is_browser_running(browser, run=fake_run) is True
    assert calls == [["pgrep", "-x", "vivaldi"], ["pgrep", "-x", "vivaldi-bin"]]


def test_is_browser_running_false_when_no_process_found():
    browser = BrowserDefinition("vivaldi", "Vivaldi", [], ["vivaldi", "vivaldi-bin"])

    assert is_browser_running(browser, run=lambda *a, **k: _FakePgrepResult(1)) is False
