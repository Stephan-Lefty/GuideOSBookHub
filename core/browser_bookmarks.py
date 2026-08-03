import itertools
import json
import os
import subprocess
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from core.importer import ImportedBookmark, ImportedFolder


@dataclass
class BrowserDefinition:
    id: str
    label: str
    candidate_paths: list = field(default_factory=list)  # relativ zu home()
    process_names: list = field(default_factory=list)  # für is_browser_running()


CHROMIUM_BROWSERS = [
    BrowserDefinition(
        "vivaldi", "Vivaldi",
        [".config/vivaldi/Default/Bookmarks"], ["vivaldi", "vivaldi-bin"],
    ),
    BrowserDefinition(
        "chrome", "Google Chrome",
        [".config/google-chrome/Default/Bookmarks"], ["chrome", "google-chrome"],
    ),
    BrowserDefinition(
        "chromium", "Chromium",
        [".config/chromium/Default/Bookmarks"], ["chromium", "chromium-browse"],
    ),
    BrowserDefinition(
        "brave", "Brave",
        [".config/BraveSoftware/Brave-Browser/Default/Bookmarks"],
        ["brave", "brave-browser"],
    ),
    BrowserDefinition(
        "edge", "Microsoft Edge",
        [".config/microsoft-edge/Default/Bookmarks"], ["msedge", "microsoft-edge"],
    ),
    BrowserDefinition("opera", "Opera", [".config/opera/Bookmarks"], ["opera"]),
]


def find_bookmarks_file(browser: BrowserDefinition, home: Path = None) -> Optional[Path]:
    home = home if home is not None else Path.home()
    for candidate in browser.candidate_paths:
        path = home / candidate
        if path.is_file():
            return path
    return None


def is_browser_running(browser: BrowserDefinition, run=subprocess.run) -> bool:
    """Sicherheitsnetz vor dem Rück-Export: Schreiben in die Bookmarks-Datei
    eines laufenden Browsers kann Daten korrumpieren, da der Browser sie
    beim eigenen Speichern/Schließen wieder überschreibt. `run` ist per
    Dependency Injection austauschbar, damit Tests keinen echten Prozess
    brauchen."""
    for name in browser.process_names:
        result = run(["pgrep", "-x", name], capture_output=True, text=True)
        if result.returncode == 0:
            return True
    return False


ROOT_KEYS = ("bookmark_bar", "other", "synced")  # "trash" bewusst ausgeschlossen


def _convert_node(node: dict):
    node_type = node.get("type")
    if node_type == "folder":
        return ImportedFolder(
            name=node.get("name", ""),
            children=[_convert_node(child) for child in node.get("children", [])],
        )
    if node_type == "url":
        return ImportedBookmark(title=node.get("name", ""), url=node.get("url", ""))
    return None


def parse_chromium_bookmarks(json_text: str) -> ImportedFolder:
    data = json.loads(json_text)
    roots = data.get("roots", {})

    root = ImportedFolder(name="")
    for key in ROOT_KEYS:
        root_node = roots.get(key)
        if not isinstance(root_node, dict) or not root_node.get("children"):
            continue
        converted = _convert_node(root_node)
        if converted is not None:
            root.children.append(converted)

    return root


# ---------- Rück-Export in den Browser ----------

CHROME_EPOCH = datetime(1601, 1, 1, tzinfo=timezone.utc)


def _chrome_timestamp() -> str:
    return str(int((datetime.now(timezone.utc) - CHROME_EPOCH).total_seconds() * 1_000_000))


def repository_to_tree(repo) -> ImportedFolder:
    """Kehrt import_into_repository() um: baut aus dem aktuellen
    Repository-Inhalt denselben ImportedFolder/ImportedBookmark-Baum, den
    auch der Import-Parser erzeugt."""
    groups_by_parent = {}
    for group in repo.list_groups():
        groups_by_parent.setdefault(group.parent_id, []).append(group)

    bookmarks_by_group = {}
    for bookmark in repo.list_bookmarks():
        bookmarks_by_group.setdefault(bookmark.group_id, []).append(bookmark)

    def build(group_id) -> list:
        items = [
            ImportedFolder(name=g.name, children=build(g.id))
            for g in groups_by_parent.get(group_id, [])
        ]
        items += [
            ImportedBookmark(title=b.title, url=b.url)
            for b in bookmarks_by_group.get(group_id, [])
        ]
        return items

    return ImportedFolder(name="", children=build(None))


def _empty_chromium_data() -> dict:
    def permanent_folder(name: str) -> dict:
        return {
            "children": [], "date_added": "0", "date_modified": "0",
            "guid": str(uuid.uuid4()), "id": str(next(_id_seed)),
            "name": name, "type": "folder",
        }

    _id_seed = itertools.count(1)
    return {
        "roots": {
            "bookmark_bar": permanent_folder("Bookmarks bar"),
            "other": permanent_folder("Other bookmarks"),
            "synced": permanent_folder("Mobile bookmarks"),
        },
        "version": 1,
    }


def _max_existing_id(data: dict) -> int:
    max_id = 0

    def walk(node):
        nonlocal max_id
        if not isinstance(node, dict):
            return
        node_id = node.get("id")
        if isinstance(node_id, str) and node_id.isdigit():
            max_id = max(max_id, int(node_id))
        for child in node.get("children", []):
            walk(child)

    for root_node in data.get("roots", {}).values():
        walk(root_node)
    return max_id


def _tree_to_chromium_nodes(items: list, id_counter) -> list:
    nodes = []
    for item in items:
        if isinstance(item, ImportedFolder):
            nodes.append({
                "children": _tree_to_chromium_nodes(item.children, id_counter),
                "date_added": _chrome_timestamp(),
                "guid": str(uuid.uuid4()),
                "id": str(next(id_counter)),
                "name": item.name,
                "type": "folder",
            })
        elif isinstance(item, ImportedBookmark):
            nodes.append({
                "date_added": _chrome_timestamp(),
                "guid": str(uuid.uuid4()),
                "id": str(next(id_counter)),
                "name": item.title,
                "type": "url",
                "url": item.url,
            })
    return nodes


def _merge_children(existing_children: list, new_items: list, id_counter) -> None:
    existing_folders_by_name = {
        child["name"]: child for child in existing_children if child.get("type") == "folder"
    }
    existing_urls = {child["url"] for child in existing_children if child.get("type") == "url"}

    for item in new_items:
        if isinstance(item, ImportedFolder):
            target = existing_folders_by_name.get(item.name)
            if target is None:
                target = {
                    "children": [], "date_added": _chrome_timestamp(),
                    "guid": str(uuid.uuid4()), "id": str(next(id_counter)),
                    "name": item.name, "type": "folder",
                }
                existing_children.append(target)
                existing_folders_by_name[item.name] = target
            _merge_children(target["children"], item.children, id_counter)
        elif isinstance(item, ImportedBookmark):
            if item.url in existing_urls:
                continue
            existing_children.append({
                "date_added": _chrome_timestamp(),
                "guid": str(uuid.uuid4()),
                "id": str(next(id_counter)),
                "name": item.title,
                "type": "url",
                "url": item.url,
            })
            existing_urls.add(item.url)


def export_to_chromium_json(existing_json_text: Optional[str], tree: ImportedFolder,
                             strategy: str) -> str:
    """strategy: 'merge' | 'separate_folder' | 'replace'."""
    data = json.loads(existing_json_text) if existing_json_text else _empty_chromium_data()
    data.pop("checksum", None)  # Chromium berechnet ihn beim nächsten Start neu

    id_counter = itertools.count(_max_existing_id(data) + 1)
    bookmark_bar = data.setdefault("roots", {}).setdefault(
        "bookmark_bar", {"children": [], "type": "folder", "name": "Bookmarks bar"}
    )
    bookmark_bar.setdefault("children", [])

    if strategy == "replace":
        bookmark_bar["children"] = _tree_to_chromium_nodes(tree.children, id_counter)
    elif strategy == "separate_folder":
        bookmark_bar["children"].append({
            "children": _tree_to_chromium_nodes(tree.children, id_counter),
            "date_added": _chrome_timestamp(),
            "guid": str(uuid.uuid4()),
            "id": str(next(id_counter)),
            "name": "GuideOSBookHub (importiert)",
            "type": "folder",
        })
    elif strategy == "merge":
        _merge_children(bookmark_bar["children"], tree.children, id_counter)
    else:
        raise ValueError(f"Unbekannte Strategie: {strategy}")

    return json.dumps(data, indent=3)


def write_bookmarks_file(path: Path, json_text: str) -> None:
    """Schreiben über Temp-Datei + os.replace (gleiches Muster wie
    core/sync.py:_push), damit ein Absturz mitten im Schreiben nicht die
    bestehende Bookmarks-Datei des Browsers zerstört."""
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json_text)
        os.replace(tmp_path, path)
    except BaseException:
        os.unlink(tmp_path)
        raise
