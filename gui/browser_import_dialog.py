import sqlite3

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QMessageBox, QFileDialog
)

from core.browser_bookmarks import CHROMIUM_BROWSERS, find_bookmarks_file, parse_chromium_bookmarks
from core.firefox_bookmarks import find_places_db, import_firefox_bookmarks, is_firefox_running
from core.i18n import t
from core.importer import import_into_repository, parse_netscape_html

OTHER_FILE_ID = "__other_file__"
FIREFOX_ID = "__firefox__"


class BrowserImportDialog(QDialog):
    """Lässt den Nutzer einen Browser auswählen und importiert dessen
    Lesezeichen automatisch (Chromium-Familie: direkter Zugriff auf die
    Bookmarks-JSON-Datei im Profilordner, kein manueller Export nötig).
    Für alles andere (z.B. Firefox) bleibt der manuelle HTML-Datei-Import
    als Rückfalloption erhalten."""

    def __init__(self, repo, first_run: bool = False, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.setWindowTitle(t("import.window_title"))
        self.resize(420, 320)

        layout = QVBoxLayout(self)

        intro = t("import.intro_first_run") if first_run else t("import.intro")
        intro_label = QLabel(intro)
        intro_label.setWordWrap(True)
        layout.addWidget(intro_label)

        self.browser_list = QListWidget()
        for browser in CHROMIUM_BROWSERS:
            item = QListWidgetItem(browser.label)
            item.setData(Qt.ItemDataRole.UserRole, browser.id)
            self.browser_list.addItem(item)
        firefox_item = QListWidgetItem(t("import.firefox_label"))
        firefox_item.setData(Qt.ItemDataRole.UserRole, FIREFOX_ID)
        self.browser_list.addItem(firefox_item)
        other_item = QListWidgetItem(t("import.other_file_item"))
        other_item.setData(Qt.ItemDataRole.UserRole, OTHER_FILE_ID)
        self.browser_list.addItem(other_item)
        self.browser_list.setCurrentRow(0)
        layout.addWidget(self.browser_list)

        buttons_row = QHBoxLayout()
        self.skip_button = QPushButton(t("import.skip_button") if first_run else t("import.cancel_button"))
        self.skip_button.clicked.connect(self.reject)
        self.import_button = QPushButton(t("import.import_button"))
        self.import_button.clicked.connect(self._on_import_clicked)
        buttons_row.addWidget(self.skip_button)
        buttons_row.addStretch()
        buttons_row.addWidget(self.import_button)
        layout.addLayout(buttons_row)

    def _on_import_clicked(self):
        item = self.browser_list.currentItem()
        if item is None:
            return
        browser_id = item.data(Qt.ItemDataRole.UserRole)

        if browser_id == OTHER_FILE_ID:
            self._import_from_html_file()
            return

        if browser_id == FIREFOX_ID:
            self._import_from_firefox()
            return

        browser = next(b for b in CHROMIUM_BROWSERS if b.id == browser_id)
        path = find_bookmarks_file(browser)
        if path is None:
            QMessageBox.warning(
                self, t("import.not_found_title"),
                t("import.not_found_text", browser=browser.label)
            )
            self._import_from_html_file()
            return

        try:
            json_text = path.read_text(encoding="utf-8")
            root = parse_chromium_bookmarks(json_text)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, t("import.failed_title"), str(error))
            return

        self._finish_import(root)

    def _import_from_firefox(self):
        if is_firefox_running():
            QMessageBox.warning(
                self, t("import.firefox_running_title"), t("import.firefox_running_text")
            )
            return

        db_path = find_places_db()
        if db_path is None:
            QMessageBox.warning(
                self, t("import.not_found_title"),
                t("import.not_found_text", browser="Firefox")
            )
            self._import_from_html_file()
            return

        try:
            root = import_firefox_bookmarks(db_path)
        except (sqlite3.Error, OSError) as error:
            QMessageBox.warning(self, t("import.failed_title"), str(error))
            return

        self._finish_import(root)

    def _import_from_html_file(self):
        path, _filter = QFileDialog.getOpenFileName(
            self, t("import.file_dialog_title"), "", t("import.file_dialog_filter")
        )
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                html_text = f.read()
            root = parse_netscape_html(html_text)
        except OSError as error:
            QMessageBox.warning(self, t("import.failed_title"), str(error))
            return

        self._finish_import(root)

    def _finish_import(self, root):
        result = import_into_repository(self.repo, root)
        QMessageBox.information(
            self, t("import.done_title"),
            t(
                "import.done_text", groups=result.groups_created,
                bookmarks=result.bookmarks_created, skipped=result.bookmarks_skipped,
            )
        )
        self.accept()
