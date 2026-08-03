import pytest

from core.database import Database
from core.importer import (
    ImportedBookmark, ImportedFolder, import_into_repository, parse_netscape_html
)
from core.repository import BookmarkRepository


@pytest.fixture
def repo():
    db = Database(db_file=":memory:")
    yield BookmarkRepository(db)
    db.close()


SAMPLE_HTML = """
<!DOCTYPE NETSCAPE-Bookmark-file-1>
<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">
<TITLE>Bookmarks</TITLE>
<H1>Bookmarks</H1>
<DL><p>
    <DT><H3>Lesezeichenleiste</H3>
    <DL><p>
        <DT><A HREF="https://example.com">Example</A>
        <DT><H3>Unterordner</H3>
        <DL><p>
            <DT><A HREF="https://nested.example.com">Nested</A>
        </DL><p>
    </DL><p>
    <DT><A HREF="https://loose.example.com">Loose</A>
</DL><p>
"""


def test_parse_netscape_html_builds_folder_tree():
    root = parse_netscape_html(SAMPLE_HTML)

    assert len(root.children) == 2
    toolbar, loose = root.children

    assert isinstance(toolbar, ImportedFolder)
    assert toolbar.name == "Lesezeichenleiste"
    assert isinstance(loose, ImportedBookmark)
    assert loose.url == "https://loose.example.com"

    example, subfolder = toolbar.children
    assert isinstance(example, ImportedBookmark)
    assert example.title == "Example"
    assert example.url == "https://example.com"

    assert isinstance(subfolder, ImportedFolder)
    assert subfolder.name == "Unterordner"
    assert subfolder.children == [
        ImportedBookmark(title="Nested", url="https://nested.example.com")
    ]


def test_import_into_repository_creates_groups_and_bookmarks(repo):
    root = parse_netscape_html(SAMPLE_HTML)

    result = import_into_repository(repo, root)

    assert result.groups_created == 2
    assert result.bookmarks_created == 3
    assert result.bookmarks_skipped == 0

    groups_by_name = {g.name: g for g in repo.list_groups()}
    assert groups_by_name.keys() == {"Lesezeichenleiste", "Unterordner"}
    assert groups_by_name["Unterordner"].parent_id == groups_by_name["Lesezeichenleiste"].id

    bookmarks = repo.list_bookmarks()
    assert {b.url for b in bookmarks} == {
        "https://example.com", "https://nested.example.com", "https://loose.example.com"
    }

    loose_bookmark = next(b for b in bookmarks if b.url == "https://loose.example.com")
    assert loose_bookmark.group_id is None


def test_import_skips_duplicate_urls_in_same_folder(repo):
    root = ImportedFolder(name="", children=[
        ImportedFolder(name="Ordner", children=[
            ImportedBookmark(title="A", url="https://dup.example.com"),
            ImportedBookmark(title="B", url="https://dup.example.com"),
        ])
    ])

    result = import_into_repository(repo, root)

    assert result.groups_created == 1
    assert result.bookmarks_created == 1
    assert result.bookmarks_skipped == 1
    assert len(repo.list_bookmarks()) == 1
