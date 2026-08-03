from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QMessageBox, QStackedWidget, QWidget, QRadioButton, QButtonGroup, QFrame
)

from core.browser_bookmarks import (
    CHROMIUM_BROWSERS, export_to_chromium_json, find_bookmarks_file, is_browser_running,
    repository_to_tree, write_bookmarks_file,
)
from core.i18n import t


def _step_titles():
    return [
        t("export.step_title.browser"), t("export.step_title.strategy"),
        t("export.step_title.confirm"),
    ]


def _strategies():
    return [
        ("merge", t("export.strategy.merge.title"), t("export.strategy.merge.hint")),
        (
            "separate_folder", t("export.strategy.separate_folder.title"),
            t("export.strategy.separate_folder.hint"),
        ),
        ("replace", t("export.strategy.replace.title"), t("export.strategy.replace.hint")),
    ]


class ExportToBrowserDialog(QDialog):
    """Schreibt die aktuellen GuideOSBookHub-Lesezeichen zurück in einen
    Chromium-basierten Browser (Vivaldi, Chrome, Chromium, Brave, Edge,
    Opera). Läuft in drei klar benannten Schritten, damit die Bedienung
    ohne Vorwissen verständlich ist."""

    def __init__(self, repo, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.setWindowTitle(t("export.window_title"))
        self.resize(480, 440)

        layout = QVBoxLayout(self)

        self.step_label = QLabel("")
        self.step_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(self.step_label)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_browser_step())
        self.stack.addWidget(self._build_strategy_step())
        self.stack.addWidget(self._build_confirm_step())
        layout.addWidget(self.stack)

        buttons_row = QHBoxLayout()
        self.back_button = QPushButton(t("export.back_button"))
        self.back_button.setProperty("class", "secondary")
        self.back_button.clicked.connect(self._on_back)
        self.cancel_button = QPushButton(t("export.cancel_button"))
        self.cancel_button.setProperty("class", "secondary")
        self.cancel_button.clicked.connect(self.reject)
        self.next_button = QPushButton(t("export.next_button"))
        self.next_button.setProperty("class", "primary")
        self.next_button.clicked.connect(self._on_next)
        buttons_row.addWidget(self.back_button)
        buttons_row.addWidget(self.cancel_button)
        buttons_row.addStretch()
        buttons_row.addWidget(self.next_button)
        layout.addLayout(buttons_row)

        self._update_step_ui()

    # ---------- Schritt-Aufbau ----------

    def _build_browser_step(self) -> QWidget:
        widget = QWidget()
        v = QVBoxLayout(widget)
        label = QLabel(t("export.browser_step_label"))
        label.setWordWrap(True)
        v.addWidget(label)

        self.browser_list = QListWidget()
        first_enabled_row = None
        for row, browser in enumerate(CHROMIUM_BROWSERS):
            found = find_bookmarks_file(browser) is not None
            status = t("export.found") if found else t("export.not_found")
            item = QListWidgetItem(f"{browser.label} — {status}")
            item.setData(Qt.ItemDataRole.UserRole, browser.id)
            if not found:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            elif first_enabled_row is None:
                first_enabled_row = row
            self.browser_list.addItem(item)
        if first_enabled_row is not None:
            self.browser_list.setCurrentRow(first_enabled_row)
        self.browser_list.currentRowChanged.connect(lambda *_: self._update_step_ui())
        v.addWidget(self.browser_list)
        return widget

    def _build_strategy_step(self) -> QWidget:
        widget = QWidget()
        v = QVBoxLayout(widget)
        label = QLabel(t("export.strategy_step_label"))
        label.setWordWrap(True)
        v.addWidget(label)

        self.strategy_group = QButtonGroup(widget)
        self.strategy_buttons = {}
        for key, title, explanation in _strategies():
            radio = QRadioButton(title)
            self.strategy_group.addButton(radio)
            self.strategy_buttons[radio] = key
            v.addWidget(radio)
            hint = QLabel(explanation)
            hint.setWordWrap(True)
            hint.setProperty("class", "hint")
            v.addWidget(hint)
        next(iter(self.strategy_buttons)).setChecked(True)  # "Zusammenführen" als sicherer Default
        v.addStretch()
        return widget

    def _build_confirm_step(self) -> QWidget:
        widget = QWidget()
        v = QVBoxLayout(widget)
        card = QFrame()
        card.setProperty("class", "card")
        card_layout = QVBoxLayout(card)
        self.warning_label = QLabel("")
        self.warning_label.setWordWrap(True)
        card_layout.addWidget(self.warning_label)
        v.addWidget(card)
        v.addStretch()
        return widget

    # ---------- Navigation ----------

    def _current_browser(self):
        item = self.browser_list.currentItem()
        if item is None:
            return None
        browser_id = item.data(Qt.ItemDataRole.UserRole)
        return next(b for b in CHROMIUM_BROWSERS if b.id == browser_id)

    def _current_strategy(self) -> str:
        return self.strategy_buttons[self.strategy_group.checkedButton()]

    def _update_step_ui(self):
        index = self.stack.currentIndex()
        self.step_label.setText(t("export.step_label", step=index + 1, title=_step_titles()[index]))
        self.back_button.setEnabled(index > 0)
        self.next_button.setText(t("export.write_button") if index == 2 else t("export.next_button"))

        if index == 2:
            browser = self._current_browser()
            name = browser.label if browser else ""
            self.warning_label.setText(t("export.warning_text", browser=name))

    def _on_back(self):
        self.stack.setCurrentIndex(self.stack.currentIndex() - 1)
        self._update_step_ui()

    def _on_next(self):
        index = self.stack.currentIndex()

        if index == 0 and self._current_browser() is None:
            QMessageBox.warning(
                self, t("export.selection_missing_title"), t("export.selection_missing_text")
            )
            return

        if index < 2:
            self.stack.setCurrentIndex(index + 1)
            self._update_step_ui()
            return

        self._run_export()

    # ---------- Ausführung ----------

    def _run_export(self):
        browser = self._current_browser()
        strategy = self._current_strategy()

        if is_browser_running(browser):
            QMessageBox.warning(
                self, t("export.browser_running_title"),
                t("export.browser_running_text", browser=browser.label)
            )
            return

        path = find_bookmarks_file(browser)
        if path is None:
            QMessageBox.warning(
                self, t("export.not_found_title"),
                t("export.not_found_text", browser=browser.label)
            )
            return

        try:
            existing_text = path.read_text(encoding="utf-8")
            tree = repository_to_tree(self.repo)
            new_text = export_to_chromium_json(existing_text, tree, strategy)
            write_bookmarks_file(path, new_text)
        except OSError as error:
            QMessageBox.warning(self, t("export.failed_title"), str(error))
            return

        QMessageBox.information(
            self, t("export.done_title"), t("export.done_text", browser=browser.label)
        )
        self.accept()
