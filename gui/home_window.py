import time

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFrame, QStatusBar, QProgressBar, QApplication
)

from core import rclone
from core.database import Database
from core.i18n import t
from core.repository import BookmarkRepository
from core.settings import Settings
from gui.browser_import_dialog import BrowserImportDialog
from gui.cloud_setup_dialog import CloudSetupDialog
from gui.export_to_browser_dialog import ExportToBrowserDialog
from gui.settings_dialog import SettingsDialog
from gui.sync_worker import SyncWorker

AUTO_SYNC_CHECK_INTERVAL_MS = 60_000


class ClickableCard(QFrame):
    """Große, antippbare Karte für die drei Hauptaktionen auf der
    Startseite -- bewusst kein einfacher QPushButton, weil Titel und
    erklärender Untertitel unterschiedlich gewichtet dargestellt werden
    sollen (selbsterklärend statt reinem Fachbegriff-Label)."""

    clicked = pyqtSignal()

    def __init__(self, title: str, subtitle: str, parent=None):
        super().__init__(parent)
        self.setProperty("class", "card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setMinimumHeight(76)

        layout = QVBoxLayout(self)
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-size: 15px; font-weight: 600;")
        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setProperty("class", "hint")
        layout.addWidget(self.title_label)
        layout.addWidget(self.subtitle_label)

    def set_texts(self, title: str, subtitle: str) -> None:
        self.title_label.setText(title)
        self.subtitle_label.setText(subtitle)

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)


class HomeWindow(QMainWindow):
    """Startseite von GuideOSBookHub: die eigentliche Verwaltung der
    einzelnen Lesezeichen (anlegen/ändern/löschen) findet im Browser
    selbst statt -- diese App ist die Sync-Brücke zwischen Browser(n) und
    Cloud/USB-Stick (Import, Cloud-/Stick-Sync-Einrichtung, Rück-Export)."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(t("app.title"))
        self.resize(560, 520)

        self.db = Database()
        self.repo = BookmarkRepository(self.db)
        self._sync_worker = None
        self._next_due = {}  # profile_id -> Unix-Timestamp, wann der nächste Auto-Sync fällig ist

        self._build_ui()
        self._start_auto_sync_timer()

        if not Settings.is_onboarding_shown():
            QTimer.singleShot(0, self._show_onboarding)

    # ---------- UI-Aufbau ----------

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        header = QHBoxLayout()
        icon_label = QLabel()
        app_icon = QApplication.instance().windowIcon()
        if not app_icon.isNull():
            icon_label.setPixmap(app_icon.pixmap(28, 28))
        header.addWidget(icon_label)
        self.title_label = QLabel(t("app.title"))
        self.title_label.setStyleSheet("font-size: 20px; font-weight: 700;")
        header.addWidget(self.title_label)
        header.addStretch()
        self.settings_button = QPushButton(t("home.settings_button"))
        self.settings_button.setProperty("class", "secondary")
        self.settings_button.clicked.connect(self._on_open_settings)
        header.addWidget(self.settings_button)
        layout.addLayout(header)

        self.tagline_label = QLabel(t("home.tagline"))
        self.tagline_label.setWordWrap(True)
        self.tagline_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(self.tagline_label)

        self.subtitle_label = QLabel(t("home.subtitle"))
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setProperty("class", "hint")
        layout.addWidget(self.subtitle_label)

        self.import_card = ClickableCard(
            t("home.import_card.title"), t("home.import_card.subtitle")
        )
        self.import_card.clicked.connect(self._on_import_from_browser)
        layout.addWidget(self.import_card)

        self.cloud_card = ClickableCard(
            t("home.cloud_card.title"), t("home.cloud_card.subtitle")
        )
        self.cloud_card.clicked.connect(self._on_setup_cloud)
        layout.addWidget(self.cloud_card)

        self.export_card = ClickableCard(
            t("home.export_card.title"), t("home.export_card.subtitle")
        )
        self.export_card.clicked.connect(self._on_export_to_browser)
        layout.addWidget(self.export_card)

        layout.addStretch()

        self.sync_progress = QProgressBar()
        self.sync_progress.setRange(0, 100)
        self.sync_progress.setTextVisible(True)
        self.sync_progress.setVisible(False)
        layout.addWidget(self.sync_progress)

        sync_row = QHBoxLayout()
        sync_row.addStretch()
        self.sync_button = QPushButton(t("home.sync_button"))
        self.sync_button.setProperty("class", "primary")
        self.sync_button.clicked.connect(self._on_sync_now)
        sync_row.addWidget(self.sync_button)
        layout.addLayout(sync_row)

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage(t("home.status_ready"))

    # ---------- Karten-Aktionen ----------

    def _on_import_from_browser(self):
        BrowserImportDialog(self.repo, first_run=False, parent=self).exec()

    def _on_setup_cloud(self):
        CloudSetupDialog(self.repo, first_run=False, parent=self).exec()

    def _on_export_to_browser(self):
        ExportToBrowserDialog(self.repo, parent=self).exec()

    def _on_open_settings(self):
        SettingsDialog(self.repo, parent=self).exec()
        self.retranslate_ui()

    def retranslate_ui(self):
        """Aktualisiert alle sichtbaren Texte nach einem Sprachwechsel in den
        Einstellungen -- HomeWindow bleibt (anders als die Dialoge, die bei
        jedem Öffnen neu gebaut werden) für die gesamte Laufzeit bestehen."""
        self.title_label.setText(t("app.title"))
        self.settings_button.setText(t("home.settings_button"))
        self.tagline_label.setText(t("home.tagline"))
        self.subtitle_label.setText(t("home.subtitle"))
        self.import_card.set_texts(t("home.import_card.title"), t("home.import_card.subtitle"))
        self.cloud_card.set_texts(t("home.cloud_card.title"), t("home.cloud_card.subtitle"))
        self.export_card.set_texts(t("home.export_card.title"), t("home.export_card.subtitle"))
        self.sync_button.setText(t("home.sync_button"))
        self.statusBar().showMessage(t("home.status_ready"))

    # ---------- Erststart ----------

    def _show_onboarding(self):
        BrowserImportDialog(self.repo, first_run=True, parent=self).exec()

        if rclone.is_rclone_installed():
            CloudSetupDialog(self.repo, first_run=True, parent=self).exec()

        Settings.mark_onboarding_shown()

    # ---------- Sync ----------

    def _on_sync_now(self):
        profiles = Settings.list_profiles()
        if not profiles:
            self._on_setup_cloud()
            return
        self._run_sync(profiles)

    def _run_sync(self, profiles: list[dict]):
        if self._sync_worker is not None and self._sync_worker.isRunning():
            return
        self._sync_total = len(profiles)
        self._sync_completed = 0
        self.sync_button.setEnabled(False)
        self.sync_progress.setValue(0)
        self.sync_progress.setVisible(True)
        self.statusBar().showMessage(t("home.status_syncing"))
        self._sync_worker = SyncWorker(profiles)
        self._sync_worker.profile_finished.connect(self._on_profile_sync_finished)
        self._sync_worker.finished_all.connect(self._on_sync_all_finished)
        self._sync_worker.start()

    def _on_profile_sync_finished(self, profile_name: str, result):
        self._sync_completed += 1
        self.sync_progress.setValue(int(self._sync_completed / self._sync_total * 100))

        if result.errors:
            self.statusBar().showMessage(
                t("home.status_profile_error", profile=profile_name, error=result.errors[0]), 8000
            )
        else:
            self.statusBar().showMessage(
                t(
                    "home.status_profile_result", profile=profile_name,
                    created=result.created, updated=result.updated,
                    deleted=result.deleted, conflicts=result.conflicts,
                ), 8000
            )

    def _on_sync_all_finished(self):
        self.sync_button.setEnabled(True)
        self.sync_progress.setVisible(False)

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
