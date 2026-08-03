import time

from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QAction, QDesktopServices
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QSplitter, QTreeWidget,
    QTreeWidgetItem, QTableWidget, QTableWidgetItem, QLineEdit, QToolBar,
    QMessageBox, QAbstractItemView, QHeaderView, QStatusBar, QFileDialog
)

from core import rclone
from core.database import Database
from core.importer import import_into_repository, parse_netscape_html
from core.repository import BookmarkRepository
from core.settings import Settings
from gui.bookmark_dialog import AddEditBookmarkDialog
from gui.browser_import_dialog import BrowserImportDialog
from gui.cloud_setup_dialog import CloudSetupDialog
from gui.group_dialog import AddEditGroupDialog
from gui.qt_i18n import confirm_yes_no
from gui.settings_dialog import SettingsDialog
from gui.sync_worker import SyncWorker

SELECTION_ROLE = Qt.ItemDataRole.UserRole
BOOKMARK_ID_ROLE = Qt.ItemDataRole.UserRole

AUTO_SYNC_CHECK_INTERVAL_MS = 60_000


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("GuideOSBookHub")
        self.resize(900, 600)

        self.db = Database()
        self.repo = BookmarkRepository(self.db)
        self._sync_worker = None
        self._next_due = {}  # profile_id -> Unix-Timestamp, wann der nächste Auto-Sync fällig ist

        self._build_ui()
        self._reload_groups()
        self._reload_bookmarks()
        self._start_auto_sync_timer()

        if not Settings.is_onboarding_shown():
            QTimer.singleShot(0, self._show_onboarding)

    # ---------- UI-Aufbau ----------

    def _build_ui(self):
        toolbar = QToolBar("Aktionen")
        self.addToolBar(toolbar)

        actions = [
            ("Lesezeichen hinzufügen", self._on_add_bookmark),
            ("Ordner hinzufügen", self._on_add_group),
            ("Bearbeiten", self._on_edit_bookmark),
            ("Löschen", self._on_delete_bookmark),
            ("URL öffnen", self._on_open_url),
            ("Favorit umschalten", self._on_toggle_favorite),
            ("Importieren…", self._on_import_bookmarks),
            ("Aus Browser importieren…", self._on_import_from_browser),
        ]
        for label, handler in actions:
            action = QAction(label, self)
            action.triggered.connect(handler)
            toolbar.addAction(action)

        toolbar.addSeparator()

        for label, handler in [
            ("Einstellungen", self._on_open_settings),
            ("Jetzt synchronisieren", self._on_sync_now),
        ]:
            action = QAction(label, self)
            action.triggered.connect(handler)
            toolbar.addAction(action)

        central = QWidget()
        self.setCentralWidget(central)
        outer_layout = QVBoxLayout(central)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Suche nach Titel, URL oder Tags...")
        self.search_edit.textChanged.connect(self._reload_bookmarks)
        outer_layout.addWidget(self.search_edit)

        splitter = QSplitter()
        outer_layout.addWidget(splitter)

        self.group_tree = QTreeWidget()
        self.group_tree.setHeaderHidden(True)
        self.group_tree.currentItemChanged.connect(self._reload_bookmarks)
        splitter.addWidget(self.group_tree)

        self.bookmark_table = QTableWidget(0, 3)
        self.bookmark_table.setHorizontalHeaderLabels(["★", "Titel", "URL"])
        self.bookmark_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.bookmark_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.bookmark_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self.bookmark_table.doubleClicked.connect(self._on_open_url)
        splitter.addWidget(self.bookmark_table)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Bereit.")

    # ---------- Gruppen/Ordnerbaum ----------

    def _reload_groups(self):
        self.group_tree.clear()

        all_item = QTreeWidgetItem(["Alle Lesezeichen"])
        all_item.setData(0, SELECTION_ROLE, "all")
        self.group_tree.addTopLevelItem(all_item)

        favorites_item = QTreeWidgetItem(["Favoriten"])
        favorites_item.setData(0, SELECTION_ROLE, "favorites")
        self.group_tree.addTopLevelItem(favorites_item)

        groups = self.repo.list_groups()

        def add_children(parent_id, parent_item):
            for group in groups:
                if group.parent_id != parent_id:
                    continue
                item = QTreeWidgetItem([group.name])
                item.setData(0, SELECTION_ROLE, group.id)
                if parent_item is None:
                    self.group_tree.addTopLevelItem(item)
                else:
                    parent_item.addChild(item)
                add_children(group.id, item)

        add_children(None, None)
        self.group_tree.expandAll()
        self.group_tree.setCurrentItem(all_item)

    def _current_group_selection(self):
        item = self.group_tree.currentItem()
        if item is None:
            return "all"
        return item.data(0, SELECTION_ROLE)

    # ---------- Lesezeichenliste ----------

    def _reload_bookmarks(self, *_args):
        selection = self._current_group_selection()
        search = self.search_edit.text().strip()

        if selection == "all":
            bookmarks = self.repo.list_bookmarks(search=search)
        elif selection == "favorites":
            bookmarks = self.repo.list_bookmarks(search=search, favorites_only=True)
        else:
            bookmarks = self.repo.list_bookmarks(group_id=selection, search=search)

        self.bookmark_table.setRowCount(len(bookmarks))
        for row, bookmark in enumerate(bookmarks):
            star_item = QTableWidgetItem("★" if bookmark.favorite else "")
            star_item.setData(BOOKMARK_ID_ROLE, bookmark.id)
            self.bookmark_table.setItem(row, 0, star_item)
            self.bookmark_table.setItem(row, 1, QTableWidgetItem(bookmark.title))
            self.bookmark_table.setItem(row, 2, QTableWidgetItem(bookmark.url))

    def _current_bookmark_id(self):
        row = self.bookmark_table.currentRow()
        if row < 0:
            return None
        item = self.bookmark_table.item(row, 0)
        return item.data(BOOKMARK_ID_ROLE) if item else None

    # ---------- Lesezeichen-Aktionen ----------

    def _on_add_bookmark(self):
        groups = self.repo.list_groups()
        dialog = AddEditBookmarkDialog(groups, parent=self)
        selection = self._current_group_selection()
        if isinstance(selection, int):
            index = dialog.group_combo.findData(selection)
            if index >= 0:
                dialog.group_combo.setCurrentIndex(index)
        if dialog.exec():
            self.repo.add_bookmark(dialog.get_bookmark())
            self._reload_bookmarks()

    def _on_edit_bookmark(self):
        bookmark_id = self._current_bookmark_id()
        if bookmark_id is None:
            return
        bookmark = self.repo.get_bookmark(bookmark_id)
        groups = self.repo.list_groups()
        dialog = AddEditBookmarkDialog(groups, bookmark=bookmark, parent=self)
        if dialog.exec():
            self.repo.update_bookmark(dialog.get_bookmark())
            self._reload_bookmarks()

    def _on_delete_bookmark(self):
        bookmark_id = self._current_bookmark_id()
        if bookmark_id is None:
            return
        confirmed = confirm_yes_no(
            self, "Lesezeichen löschen", "Dieses Lesezeichen wirklich löschen?"
        )
        if confirmed:
            self.repo.delete_bookmark(bookmark_id)
            self._reload_bookmarks()

    def _on_toggle_favorite(self):
        bookmark_id = self._current_bookmark_id()
        if bookmark_id is None:
            return
        self.repo.toggle_favorite(bookmark_id)
        self._reload_bookmarks()

    def _on_open_url(self):
        bookmark_id = self._current_bookmark_id()
        if bookmark_id is None:
            return
        bookmark = self.repo.get_bookmark(bookmark_id)
        if bookmark:
            QDesktopServices.openUrl(QUrl(bookmark.url))

    # ---------- Ordner-Aktionen ----------

    def _on_add_group(self):
        groups = self.repo.list_groups()
        dialog = AddEditGroupDialog(groups, parent=self)
        if dialog.exec():
            name, parent_id, profile_id = dialog.get_group()
            self.repo.add_group(name, parent_id=parent_id, profile_id=profile_id)
            self._reload_groups()

    # ---------- Import ----------

    def _on_import_bookmarks(self):
        path, _filter = QFileDialog.getOpenFileName(
            self, "Lesezeichen importieren", "", "HTML-Dateien (*.html *.htm)"
        )
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                html_text = f.read()
            root = parse_netscape_html(html_text)
            result = import_into_repository(self.repo, root)
        except OSError as error:
            QMessageBox.warning(self, "Import fehlgeschlagen", str(error))
            return

        self._reload_groups()
        self._reload_bookmarks()

        QMessageBox.information(
            self, "Import abgeschlossen",
            f"{result.groups_created} Ordner und {result.bookmarks_created} Lesezeichen "
            f"importiert, {result.bookmarks_skipped} Duplikate übersprungen."
        )

    def _on_import_from_browser(self):
        dialog = BrowserImportDialog(self.repo, first_run=False, parent=self)
        if dialog.exec():
            self._reload_groups()
            self._reload_bookmarks()

    def _show_onboarding(self):
        BrowserImportDialog(self.repo, first_run=True, parent=self).exec()
        self._reload_groups()
        self._reload_bookmarks()

        if rclone.is_rclone_installed():
            CloudSetupDialog(self.repo, first_run=True, parent=self).exec()

        Settings.mark_onboarding_shown()

    # ---------- Einstellungen / Sync ----------

    def _on_open_settings(self):
        dialog = SettingsDialog(self.repo, parent=self)
        dialog.exec()

    def _on_sync_now(self):
        profiles = Settings.list_profiles()
        if not profiles:
            QMessageBox.information(
                self, "Kein Profil",
                "Bitte zuerst über 'Einstellungen' ein Sync-Profil anlegen."
            )
            return
        self._run_sync(profiles)

    def _run_sync(self, profiles: list[dict]):
        if self._sync_worker is not None and self._sync_worker.isRunning():
            return
        self.statusBar().showMessage("Synchronisiere...")
        self._sync_worker = SyncWorker(profiles)
        self._sync_worker.profile_finished.connect(self._on_profile_sync_finished)
        self._sync_worker.finished_all.connect(self._on_sync_all_finished)
        self._sync_worker.start()

    def _on_profile_sync_finished(self, profile_name: str, result):
        if result.errors:
            self.statusBar().showMessage(f"{profile_name}: Fehler – {result.errors[0]}", 8000)
        else:
            self.statusBar().showMessage(
                f"{profile_name}: {result.created} neu, {result.updated} aktualisiert, "
                f"{result.deleted} gelöscht, {result.conflicts} Konflikte gelöst", 8000
            )

    def _on_sync_all_finished(self):
        self._reload_groups()
        self._reload_bookmarks()

    def _start_auto_sync_timer(self):
        self._auto_sync_timer = QTimer(self)
        self._auto_sync_timer.timeout.connect(self._check_auto_sync)
        self._auto_sync_timer.start(AUTO_SYNC_CHECK_INTERVAL_MS)

    def _check_auto_sync(self):
        now = time.time()
        due_profiles = []
        for profile in Settings.list_profiles():
            if not profile.get("auto_sync"):
                continue
            interval_seconds = profile.get("sync_interval", 15) * 60
            if now - self._next_due.get(profile["id"], 0) >= interval_seconds:
                due_profiles.append(profile)
        if due_profiles:
            for profile in due_profiles:
                self._next_due[profile["id"]] = now
            self._run_sync(due_profiles)

    def closeEvent(self, event):
        self.db.close()
        super().closeEvent(event)
