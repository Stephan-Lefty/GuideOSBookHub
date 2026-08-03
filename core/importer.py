import sqlite3
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Optional

from core.models import Bookmark
from core.repository import BookmarkRepository


@dataclass
class ImportedBookmark:
    title: str
    url: str


@dataclass
class ImportedFolder:
    name: str
    children: list = field(default_factory=list)  # list[Union[ImportedFolder, ImportedBookmark]]


@dataclass
class ImportResult:
    groups_created: int = 0
    bookmarks_created: int = 0
    bookmarks_skipped: int = 0


class _NetscapeBookmarkParser(HTMLParser):
    """Parst das Netscape-Bookmark-HTML-Format, das praktisch jeder Browser
    (Vivaldi, Chrome, Edge, Brave, Opera, Firefox, Safari, ...) beim
    Lesezeichen-Export erzeugt. Kein valides XML/HTML (DT/p unclosed), daher
    ein tolerantes Streaming-Parsing statt eines DOM-Parsers."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = ImportedFolder(name="")
        self._container_stack = [self.root.children]
        self._dl_pushed_stack = []
        self._pending_folder: Optional[ImportedFolder] = None

        self._in_h3 = False
        self._in_a = False
        self._text_buffer = ""
        self._current_href = ""

    def handle_starttag(self, tag, attrs):
        if tag == "h3":
            self._in_h3 = True
            self._text_buffer = ""
        elif tag == "a":
            self._in_a = True
            self._text_buffer = ""
            self._current_href = dict(attrs).get("href", "")
        elif tag == "dl":
            if self._pending_folder is not None:
                self._container_stack.append(self._pending_folder.children)
                self._pending_folder = None
                self._dl_pushed_stack.append(True)
            else:
                self._dl_pushed_stack.append(False)

    def handle_endtag(self, tag):
        if tag == "h3":
            self._in_h3 = False
            folder = ImportedFolder(name=self._text_buffer.strip())
            self._container_stack[-1].append(folder)
            self._pending_folder = folder
        elif tag == "a":
            self._in_a = False
            if self._current_href:
                title = self._text_buffer.strip() or self._current_href
                self._container_stack[-1].append(
                    ImportedBookmark(title=title, url=self._current_href)
                )
        elif tag == "dl":
            if self._dl_pushed_stack and self._dl_pushed_stack.pop():
                self._container_stack.pop()

    def handle_data(self, data):
        if self._in_h3 or self._in_a:
            self._text_buffer += data


def parse_netscape_html(html_text: str) -> ImportedFolder:
    parser = _NetscapeBookmarkParser()
    parser.feed(html_text)
    return parser.root


def import_into_repository(
    repo: BookmarkRepository, root: ImportedFolder, parent_id: Optional[int] = None
) -> ImportResult:
    result = ImportResult()
    _import_children(repo, root.children, parent_id, result)
    return result


def _import_children(
    repo: BookmarkRepository,
    items: list,
    parent_id: Optional[int],
    result: ImportResult,
) -> None:
    for item in items:
        if isinstance(item, ImportedFolder):
            group = repo.add_group(item.name, parent_id=parent_id)
            result.groups_created += 1
            _import_children(repo, item.children, group.id, result)
        elif isinstance(item, ImportedBookmark):
            try:
                repo.add_bookmark(
                    Bookmark(id=None, title=item.title, url=item.url, group_id=parent_id)
                )
                result.bookmarks_created += 1
            except sqlite3.IntegrityError:
                result.bookmarks_skipped += 1
