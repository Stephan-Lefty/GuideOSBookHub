from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QFormLayout, QLineEdit, QComboBox, QSpinBox,
    QCheckBox, QMessageBox, QWidget, QDialogButtonBox
)

from core import rclone
from core.settings import Settings
from gui.rclone_install_dialog import RcloneInstallDialog
from gui.sync_worker import ConnectionTestWorker


class SettingsDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Einstellungen")
        self.resize(600, 400)
        self._test_worker = None
        self.available_remotes: list[str] = []

        layout = QVBoxLayout(self)

        if not rclone.is_rclone_installed():
            layout.addWidget(QLabel(
                "rclone wurde nicht gefunden. Ohne rclone kann kein Sync-Profil "
                "angelegt werden."
            ))
            install_button = QPushButton("rclone installieren")
            install_button.clicked.connect(self._on_install_rclone)
            layout.addWidget(install_button)
            close_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
            close_box.rejected.connect(self.reject)
            layout.addWidget(close_box)
            return

        try:
            self.available_remotes = rclone.list_remotes()
        except rclone.RcloneError as e:
            layout.addWidget(QLabel(str(e)))

        body = QHBoxLayout()
        layout.addLayout(body)

        self.profile_list = QListWidget()
        self.profile_list.currentRowChanged.connect(self._on_profile_selected)
        body.addWidget(self.profile_list, 1)

        form_widget = QWidget()
        form = QFormLayout(form_widget)
        body.addWidget(form_widget, 2)

        self.name_edit = QLineEdit()
        self.remote_combo = QComboBox()
        self.remote_combo.addItems(self.available_remotes)
        self.refresh_remotes_btn = QPushButton("Remotes aktualisieren")
        self.refresh_remotes_btn.clicked.connect(self._refresh_remotes)
        self.path_edit = QLineEdit()
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 1440)
        self.interval_spin.setSuffix(" min")
        self.auto_sync_check = QCheckBox("Automatisch synchronisieren")
        self.test_button = QPushButton("Verbindung testen")
        self.test_button.clicked.connect(self._on_test_connection)
        self.test_result_label = QLabel("")
        self.test_result_label.setWordWrap(True)

        form.addRow("Name", self.name_edit)
        form.addRow("Remote", self.remote_combo)
        form.addRow("", self.refresh_remotes_btn)
        form.addRow("Pfad/Dateiname", self.path_edit)
        form.addRow("Sync-Intervall", self.interval_spin)
        form.addRow("", self.auto_sync_check)
        form.addRow("", self.test_button)
        form.addRow("", self.test_result_label)

        buttons_row = QHBoxLayout()
        self.add_button = QPushButton("Neues Profil")
        self.add_button.clicked.connect(self._on_add_profile)
        self.remove_button = QPushButton("Profil entfernen")
        self.remove_button.clicked.connect(self._on_remove_profile)
        self.save_button = QPushButton("Speichern")
        self.save_button.clicked.connect(self._on_save_profile)
        buttons_row.addWidget(self.add_button)
        buttons_row.addWidget(self.remove_button)
        buttons_row.addStretch()
        buttons_row.addWidget(self.save_button)
        layout.addLayout(buttons_row)

        close_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_box.rejected.connect(self.reject)
        layout.addWidget(close_box)

        self._reload_profile_list()

    # ---------- Profil-Liste ----------

    def _reload_profile_list(self):
        self.profile_list.blockSignals(True)
        self.profile_list.clear()
        for profile in Settings.list_profiles():
            item = QListWidgetItem(profile["name"])
            item.setData(Qt.ItemDataRole.UserRole, profile["id"])
            self.profile_list.addItem(item)
        self.profile_list.blockSignals(False)
        if self.profile_list.count():
            self.profile_list.setCurrentRow(0)
        else:
            self._on_profile_selected(-1)

    def _current_profile_id(self):
        item = self.profile_list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _on_profile_selected(self, _row):
        profile_id = self._current_profile_id()
        profile = Settings.get_profile(profile_id) if profile_id else None
        self.test_result_label.setText("")

        if not profile:
            self.name_edit.clear()
            self.path_edit.clear()
            self.interval_spin.setValue(15)
            self.auto_sync_check.setChecked(True)
            return

        self.name_edit.setText(profile["name"])
        index = self.remote_combo.findText(profile["remote"])
        if index >= 0:
            self.remote_combo.setCurrentIndex(index)
        self.path_edit.setText(profile["remote_path"])
        self.interval_spin.setValue(profile["sync_interval"])
        self.auto_sync_check.setChecked(profile["auto_sync"])

    def _refresh_remotes(self):
        try:
            self.available_remotes = rclone.list_remotes()
        except rclone.RcloneError as e:
            QMessageBox.warning(self, "Fehler", str(e))
            return
        current = self.remote_combo.currentText()
        self.remote_combo.clear()
        self.remote_combo.addItems(self.available_remotes)
        index = self.remote_combo.findText(current)
        if index >= 0:
            self.remote_combo.setCurrentIndex(index)

    # ---------- Profil-Aktionen ----------

    def _on_add_profile(self):
        if not self.available_remotes:
            QMessageBox.warning(
                self, "Kein Remote konfiguriert",
                "Bitte zuerst per 'rclone config' im Terminal mindestens ein Remote "
                "einrichten, dann hier auf 'Remotes aktualisieren' klicken."
            )
            return
        profile = Settings.add_profile(
            name="Neues Profil", remote=self.available_remotes[0], remote_path="bookmarks.json"
        )
        self._reload_profile_list()
        for row in range(self.profile_list.count()):
            if self.profile_list.item(row).data(Qt.ItemDataRole.UserRole) == profile["id"]:
                self.profile_list.setCurrentRow(row)
                break

    def _on_remove_profile(self):
        profile_id = self._current_profile_id()
        if not profile_id:
            return
        confirm = QMessageBox.question(
            self, "Profil entfernen",
            "Profil wirklich entfernen? Bereits synchronisierte Lesezeichen bleiben lokal "
            "erhalten, werden aber nicht mehr mit diesem Ziel abgeglichen."
        )
        if confirm == QMessageBox.StandardButton.Yes:
            Settings.remove_profile(profile_id)
            self._reload_profile_list()

    def _on_save_profile(self):
        profile_id = self._current_profile_id()
        if not profile_id:
            return
        Settings.update_profile(
            profile_id,
            name=self.name_edit.text().strip() or "Unbenanntes Profil",
            remote=self.remote_combo.currentText(),
            remote_path=self.path_edit.text().strip() or "bookmarks.json",
            sync_interval=self.interval_spin.value(),
            auto_sync=self.auto_sync_check.isChecked(),
        )
        self._reload_profile_list()

    def _on_test_connection(self):
        remote = self.remote_combo.currentText()
        if not remote:
            return
        self.test_result_label.setText("Teste Verbindung...")
        self.test_button.setEnabled(False)
        self._test_worker = ConnectionTestWorker(remote)
        self._test_worker.finished_test.connect(self._on_test_finished)
        self._test_worker.start()

    def _on_test_finished(self, success: bool, message: str):
        self.test_button.setEnabled(True)
        prefix = "OK: " if success else "Fehler: "
        self.test_result_label.setText(prefix + message)

    def _on_install_rclone(self):
        RcloneInstallDialog(self).exec()
        # Der obere Teil dieses Dialogs wurde nur für den "rclone fehlt"-Fall
        # aufgebaut; nach einer (möglicherweise erfolgreichen) Installation
        # einfach schließen, damit der Nutzer die Einstellungen neu öffnet
        # und die volle Profil-Oberfläche bekommt.
        self.accept()
