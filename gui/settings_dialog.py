from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QFormLayout, QLineEdit, QComboBox, QSpinBox,
    QCheckBox, QMessageBox, QWidget, QDialogButtonBox
)

from core import rclone
from core.i18n import SUPPORTED_LANGUAGES, t
from core.settings import Settings
from gui.cloud_setup_dialog import CloudSetupDialog
from gui.qt_i18n import confirm_yes_no, germanize_button_box
from gui.rclone_install_dialog import RcloneInstallDialog
from gui.sync_worker import ConnectionTestWorker


class SettingsDialog(QDialog):

    def __init__(self, repo, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.setWindowTitle(t("settings.window_title"))
        self.resize(600, 400)
        self._test_worker = None
        self.available_remotes: list[str] = []
        self.language_changed = False

        layout = QVBoxLayout(self)

        layout.addLayout(self._build_language_row())

        if not rclone.is_rclone_installed():
            layout.addWidget(QLabel(t("settings.rclone_missing_label")))
            install_button = QPushButton(t("settings.install_rclone_button"))
            install_button.clicked.connect(self._on_install_rclone)
            layout.addWidget(install_button)
            close_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
            germanize_button_box(close_box)
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
        self.refresh_remotes_btn = QPushButton(t("settings.refresh_remotes_button"))
        self.refresh_remotes_btn.clicked.connect(self._refresh_remotes)
        self.add_cloud_remote_btn = QPushButton(t("settings.add_cloud_remote_button"))
        self.add_cloud_remote_btn.clicked.connect(self._on_add_cloud_remote)
        self.path_edit = QLineEdit()
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 1440)
        self.interval_spin.setSuffix(t("settings.interval_suffix"))
        self.auto_sync_check = QCheckBox(t("settings.auto_sync_checkbox"))
        self.test_button = QPushButton(t("settings.test_button"))
        self.test_button.clicked.connect(self._on_test_connection)
        self.test_result_label = QLabel("")
        self.test_result_label.setWordWrap(True)

        form.addRow(t("settings.field.name"), self.name_edit)
        form.addRow(t("settings.field.remote"), self.remote_combo)
        form.addRow("", self.refresh_remotes_btn)
        form.addRow("", self.add_cloud_remote_btn)
        form.addRow(t("settings.field.path"), self.path_edit)
        form.addRow(t("settings.field.interval"), self.interval_spin)
        form.addRow("", self.auto_sync_check)
        form.addRow("", self.test_button)
        form.addRow("", self.test_result_label)

        buttons_row = QHBoxLayout()
        self.add_button = QPushButton(t("settings.add_profile_button"))
        self.add_button.clicked.connect(self._on_add_profile)
        self.remove_button = QPushButton(t("settings.remove_profile_button"))
        self.remove_button.clicked.connect(self._on_remove_profile)
        self.save_button = QPushButton(t("settings.save_button"))
        self.save_button.clicked.connect(self._on_save_profile)
        buttons_row.addWidget(self.add_button)
        buttons_row.addWidget(self.remove_button)
        buttons_row.addStretch()
        buttons_row.addWidget(self.save_button)
        layout.addLayout(buttons_row)

        close_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        germanize_button_box(close_box)
        close_box.rejected.connect(self.reject)
        layout.addWidget(close_box)

        self._reload_profile_list()

    # ---------- Sprache ----------

    def _build_language_row(self):
        row = QHBoxLayout()
        row.addWidget(QLabel(t("settings.field.language")))
        self.language_combo = QComboBox()
        for code, label in SUPPORTED_LANGUAGES:
            self.language_combo.addItem(label, code)
        current_index = self.language_combo.findData(Settings.get_language())
        if current_index >= 0:
            self.language_combo.setCurrentIndex(current_index)
        self.language_combo.currentIndexChanged.connect(self._on_language_changed)
        row.addWidget(self.language_combo)
        row.addStretch()
        return row

    def _on_language_changed(self, index: int):
        code = self.language_combo.itemData(index)
        if code and code != Settings.get_language():
            Settings.set_language(code)
            self.language_changed = True
            # Dialog neu öffnen statt jedes Widget einzeln neu zu beschriften --
            # der Dialog wird bei jedem Öffnen ohnehin frisch aufgebaut.
            self.accept()

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
            QMessageBox.warning(self, t("common.error_title"), str(e))
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
                self, t("settings.no_remote_title"), t("settings.no_remote_text")
            )
            return
        profile = Settings.add_profile(
            name=t("settings.new_profile_default_name"), remote=self.available_remotes[0],
            remote_path="GuideOSBookHub/bookmarks.json"
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
        confirmed = confirm_yes_no(
            self, t("settings.remove_confirm_title"), t("settings.remove_confirm_text")
        )
        if confirmed:
            Settings.remove_profile(profile_id)
            self._reload_profile_list()

    def _on_save_profile(self):
        profile_id = self._current_profile_id()
        if not profile_id:
            return
        Settings.update_profile(
            profile_id,
            name=self.name_edit.text().strip() or t("settings.unnamed_profile"),
            remote=self.remote_combo.currentText(),
            remote_path=self.path_edit.text().strip() or "GuideOSBookHub/bookmarks.json",
            sync_interval=self.interval_spin.value(),
            auto_sync=self.auto_sync_check.isChecked(),
        )
        self._reload_profile_list()

    def _on_test_connection(self):
        remote = self.remote_combo.currentText()
        if not remote:
            return
        self.test_result_label.setText(t("settings.testing_connection"))
        self.test_button.setEnabled(False)
        self._test_worker = ConnectionTestWorker(remote)
        self._test_worker.finished_test.connect(self._on_test_finished)
        self._test_worker.start()

    def _on_test_finished(self, success: bool, message: str):
        self.test_button.setEnabled(True)
        prefix = t("common.ok_prefix") if success else t("common.error_prefix")
        self.test_result_label.setText(prefix + message)

    def _on_add_cloud_remote(self):
        dialog = CloudSetupDialog(self.repo, first_run=False, parent=self)
        if dialog.exec():
            self._refresh_remotes()
            self._reload_profile_list()

    def _on_install_rclone(self):
        RcloneInstallDialog(self).exec()
        # Der obere Teil dieses Dialogs wurde nur für den "rclone fehlt"-Fall
        # aufgebaut; nach einer (möglicherweise erfolgreichen) Installation
        # einfach schließen, damit der Nutzer die Einstellungen neu öffnet
        # und die volle Profil-Oberfläche bekommt.
        self.accept()
