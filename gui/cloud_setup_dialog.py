from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit,
    QComboBox, QPushButton, QMessageBox, QProgressBar, QListWidget, QListWidgetItem,
    QStackedWidget, QWidget, QFileDialog
)

from core import rclone
from core.cloud_providers import PROVIDERS, get_provider
from core.i18n import t
from core.settings import Settings
from gui.qt_i18n import confirm_yes_no

DEFAULT_REMOTE_PATH = "GuideOSBookHub/bookmarks.json"

STEP_PROVIDER = 0
STEP_DETAILS = 1


def _vendor_choices():
    return [
        (t("cloud.vendor.nextcloud"), "nextcloud"),
        (t("cloud.vendor.owncloud"), "owncloud"),
        (t("cloud.vendor.other"), "other"),
    ]


def _finish_after_reachability_check(worker, name: str) -> None:
    """Gemeinsamer Abschluss für alle rclone-basierten Setup-Worker: Remote
    testen, bei Fehler wieder löschen (kein Datenmüll), sonst fertig melden."""
    worker.step_progress.emit(85, t("cloud.step_test"))
    try:
        rclone.check_remote_reachable(name)
    except rclone.RcloneRemoteError as e:
        rclone.delete_remote(name)
        message = str(e) + (f"\n\n{e.stderr}" if e.stderr else "")
        worker.finished_setup.emit(False, message)
        return
    except rclone.RcloneError as e:
        rclone.delete_remote(name)
        worker.finished_setup.emit(False, str(e))
        return

    worker.step_progress.emit(100, t("cloud.step_done"))
    worker.finished_setup.emit(True, t("cloud.step_done"))


class RemoteSetupWorker(QThread):
    """Legt ein Remote per beliebiger create_fn an und prüft die
    Erreichbarkeit im Hintergrund. create_fn ist ein null-stelliger
    Callable, der bereits alle providerspezifischen Zugangsdaten gebunden
    hat (z.B. via functools.partial) -- deckt WebDAV und Proton Drive
    gleichermaßen ab, da sich beide nur in der create-Funktion selbst
    unterscheiden."""

    step_progress = pyqtSignal(int, str)
    finished_setup = pyqtSignal(bool, str)

    def __init__(self, name: str, create_fn, parent=None):
        super().__init__(parent)
        self.name = name
        self.create_fn = create_fn

    def run(self):
        self.step_progress.emit(10, t("cloud.step_create"))
        try:
            self.create_fn()
        except rclone.RcloneRemoteError as e:
            message = str(e) + (f"\n\n{e.stderr}" if e.stderr else "")
            self.finished_setup.emit(False, message)
            return
        except rclone.RcloneError as e:
            self.finished_setup.emit(False, str(e))
            return

        _finish_after_reachability_check(self, self.name)


class OAuthSetupWorker(QThread):
    """Führt den kompletten Browser-Login-Ablauf für OAuth-Anbieter aus:
    rclone authorize (öffnet den Standardbrowser und wartet auf den Login),
    dann Remote-Anlage mit dem erhaltenen Token, dann Erreichbarkeitstest."""

    step_progress = pyqtSignal(int, str)
    finished_setup = pyqtSignal(bool, str)

    def __init__(self, name: str, backend: str, parent=None):
        super().__init__(parent)
        self.name = name
        self.backend = backend

    def run(self):
        self.step_progress.emit(10, t("cloud.oauth_waiting"))
        try:
            token = rclone.authorize_oauth(self.backend)
        except rclone.RcloneRemoteError as e:
            message = str(e) + (f"\n\n{e.stderr}" if e.stderr else "")
            self.finished_setup.emit(False, message)
            return
        except rclone.RcloneError as e:
            self.finished_setup.emit(False, str(e))
            return

        self.step_progress.emit(60, t("cloud.step_create"))
        try:
            rclone.create_oauth_remote(self.name, self.backend, token)
        except rclone.RcloneRemoteError as e:
            message = str(e) + (f"\n\n{e.stderr}" if e.stderr else "")
            self.finished_setup.emit(False, message)
            return
        except rclone.RcloneError as e:
            self.finished_setup.emit(False, str(e))
            return

        _finish_after_reachability_check(self, self.name)


class CloudSetupDialog(QDialog):
    """Richtet eine Sync-Verbindung ein: WebDAV/Nextcloud/ownCloud, Proton
    Drive, Google Drive, Microsoft OneDrive, Dropbox, pCloud oder ein
    lokaler Ordner/USB-Stick (kein rclone-Remote nötig). Zweistufig:
    Anbieter wählen, dann providerspezifisches Formular."""

    def __init__(self, repo, first_run: bool = False, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.first_run = first_run
        self.setWindowTitle(t("cloud.window_title"))
        self.resize(460, 400)
        self._worker = None
        self.selected_provider = None
        self.chosen_local_folder = None

        layout = QVBoxLayout(self)

        self.step_label = QLabel("")
        self.step_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(self.step_label)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_provider_step())
        self.details_container = QWidget()
        self.stack.addWidget(self.details_container)
        layout.addWidget(self.stack)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        buttons_row = QHBoxLayout()
        self.back_button = QPushButton(t("cloud.back_button"))
        self.back_button.setProperty("class", "secondary")
        self.back_button.clicked.connect(self._on_back)
        self.skip_button = QPushButton(t("cloud.skip_button") if first_run else t("cloud.cancel_button"))
        self.skip_button.setProperty("class", "secondary")
        self.skip_button.clicked.connect(self.reject)
        self.action_button = QPushButton(t("cloud.next_button"))
        self.action_button.setProperty("class", "primary")
        self.action_button.clicked.connect(self._on_action)
        buttons_row.addWidget(self.back_button)
        buttons_row.addWidget(self.skip_button)
        buttons_row.addStretch()
        buttons_row.addWidget(self.action_button)
        layout.addLayout(buttons_row)

        self._update_step_ui()

    # ---------- Schritt 1: Anbieter wählen ----------

    def _build_provider_step(self) -> QWidget:
        widget = QWidget()
        v = QVBoxLayout(widget)
        intro = QLabel(t("cloud.intro_first_run") if self.first_run else t("cloud.intro"))
        intro.setWordWrap(True)
        v.addWidget(intro)

        self.provider_list = QListWidget()
        for provider in PROVIDERS:
            item = QListWidgetItem(t(provider.label_key))
            item.setData(Qt.ItemDataRole.UserRole, provider.id)
            self.provider_list.addItem(item)
        self.provider_list.setCurrentRow(0)
        v.addWidget(self.provider_list)
        return widget

    # ---------- Schritt 2: providerspezifisches Formular ----------

    def _build_details_step(self) -> None:
        old_layout = self.details_container.layout()
        if old_layout is not None:
            QWidget().setLayout(old_layout)  # alten Layout inkl. Kindwidgets loslösen

        layout = QVBoxLayout(self.details_container)
        auth_kind = self.selected_provider.auth_kind

        if auth_kind in ("credentials", "credentials_2fa"):
            self._build_credentials_form(layout, auth_kind)
        elif auth_kind == "oauth":
            self._build_oauth_form(layout)
        elif auth_kind == "local":
            self._build_local_form(layout)

    def _build_credentials_form(self, layout: QVBoxLayout, auth_kind: str) -> None:
        form = QFormLayout()
        default_name = t(self.selected_provider.label_key)
        self.name_edit = QLineEdit(default_name)
        form.addRow(t("cloud.field.name"), self.name_edit)

        self.vendor_combo = None
        self.url_edit = None
        if self.selected_provider.id == "webdav":
            self.vendor_choices = _vendor_choices()
            self.vendor_combo = QComboBox()
            for label, _value in self.vendor_choices:
                self.vendor_combo.addItem(label)
            self.url_edit = QLineEdit()
            self.url_edit.setPlaceholderText(t("cloud.url_placeholder"))
            form.addRow(t("cloud.field.vendor"), self.vendor_combo)
            form.addRow(t("cloud.field.url"), self.url_edit)

        self.user_edit = QLineEdit()
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow(t("cloud.field.user"), self.user_edit)
        form.addRow(t("cloud.field.password"), self.password_edit)

        self.twofa_edit = None
        self.mailbox_password_edit = None
        if auth_kind == "credentials_2fa":
            self.twofa_edit = QLineEdit()
            self.mailbox_password_edit = QLineEdit()
            self.mailbox_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
            form.addRow(t("cloud.protondrive_twofa_field"), self.twofa_edit)
            form.addRow(t("cloud.protondrive_mailbox_password_field"), self.mailbox_password_edit)

        layout.addLayout(form)

        hint_key = "cloud.hint" if self.selected_provider.id == "webdav" else "cloud.protondrive_hint"
        hint = QLabel(t(hint_key))
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addStretch()

    def _build_oauth_form(self, layout: QVBoxLayout) -> None:
        form = QFormLayout()
        self.name_edit = QLineEdit(t(self.selected_provider.label_key))
        form.addRow(t("cloud.field.name"), self.name_edit)
        layout.addLayout(form)

        intro = QLabel(t("cloud.oauth_intro", provider=t(self.selected_provider.label_key)))
        intro.setWordWrap(True)
        layout.addWidget(intro)
        layout.addStretch()

    def _build_local_form(self, layout: QVBoxLayout) -> None:
        form = QFormLayout()
        self.name_edit = QLineEdit(t(self.selected_provider.label_key))
        form.addRow(t("cloud.field.name"), self.name_edit)
        layout.addLayout(form)

        intro = QLabel(t("cloud.local_intro"))
        intro.setWordWrap(True)
        layout.addWidget(intro)

        choose_row = QHBoxLayout()
        choose_button = QPushButton(t("cloud.local_choose_button"))
        choose_button.setProperty("class", "secondary")
        choose_button.clicked.connect(self._on_choose_local_folder)
        choose_row.addWidget(choose_button)
        choose_row.addStretch()
        layout.addLayout(choose_row)

        self.local_path_label = QLabel(
            f"{t('cloud.local_selected_path_label')} {self.chosen_local_folder or '—'}"
        )
        self.local_path_label.setWordWrap(True)
        layout.addWidget(self.local_path_label)
        layout.addStretch()

    def _on_choose_local_folder(self):
        folder = QFileDialog.getExistingDirectory(self, t("cloud.local_choose_button"))
        if folder:
            self.chosen_local_folder = folder
            self.local_path_label.setText(f"{t('cloud.local_selected_path_label')} {folder}")

    # ---------- Navigation ----------

    def _update_step_ui(self):
        index = self.stack.currentIndex()
        title = t("cloud.step_title.provider") if index == STEP_PROVIDER else t("cloud.step_title.details")
        self.step_label.setText(t("cloud.step_label", step=index + 1, title=title))
        self.back_button.setVisible(index == STEP_DETAILS)

        if index == STEP_PROVIDER:
            self.action_button.setText(t("cloud.next_button"))
        elif self.selected_provider.auth_kind == "oauth":
            self.action_button.setText(t("cloud.oauth_button"))
        else:
            self.action_button.setText(t("cloud.setup_button"))

    def _on_back(self):
        self.stack.setCurrentIndex(STEP_PROVIDER)
        self._update_step_ui()

    def _on_action(self):
        if self.stack.currentIndex() == STEP_PROVIDER:
            item = self.provider_list.currentItem()
            if item is None:
                return
            self.selected_provider = get_provider(item.data(Qt.ItemDataRole.UserRole))
            self.chosen_local_folder = None
            self._build_details_step()
            self.stack.setCurrentIndex(STEP_DETAILS)
            self._update_step_ui()
            return

        auth_kind = self.selected_provider.auth_kind
        if auth_kind in ("credentials", "credentials_2fa"):
            self._submit_credentials()
        elif auth_kind == "oauth":
            self._submit_oauth()
        elif auth_kind == "local":
            self._submit_local()

    # ---------- Einreichen: Zugangsdaten (WebDAV/Proton Drive) ----------

    def _submit_credentials(self):
        name = self.name_edit.text().strip()
        user = self.user_edit.text().strip()
        password = self.password_edit.text()

        if not name or not user or not password:
            QMessageBox.warning(self, t("cloud.missing_fields_title"), t("cloud.missing_fields_text"))
            return

        if not rclone.is_rclone_installed():
            QMessageBox.warning(self, t("cloud.rclone_missing_title"), t("cloud.rclone_missing_text"))
            return

        if not self._confirm_update_if_name_taken(name):
            return

        if self.selected_provider.id == "webdav":
            url = self.url_edit.text().strip()
            if not url:
                QMessageBox.warning(self, t("cloud.missing_fields_title"), t("cloud.missing_fields_text"))
                return
            vendor = self.vendor_choices[self.vendor_combo.currentIndex()][1]
            url = rclone.normalize_webdav_url(url, vendor, user)
            self.url_edit.setText(url)
            create_fn = lambda: rclone.create_webdav_remote(name, url, vendor, user, password)
        else:
            twofa = self.twofa_edit.text().strip()
            mailbox_password = self.mailbox_password_edit.text()
            create_fn = lambda: rclone.create_protondrive_remote(
                name, user, password, twofa=twofa, mailbox_password=mailbox_password
            )

        self._run_worker(RemoteSetupWorker(name, create_fn, parent=self), name)

    # ---------- Einreichen: OAuth ----------

    def _submit_oauth(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, t("cloud.missing_fields_title"), t("cloud.missing_fields_text"))
            return

        if not rclone.is_rclone_installed():
            QMessageBox.warning(self, t("cloud.rclone_missing_title"), t("cloud.rclone_missing_text"))
            return

        if not self._confirm_update_if_name_taken(name):
            return

        self._run_worker(
            OAuthSetupWorker(name, self.selected_provider.id, parent=self), name
        )

    def _confirm_update_if_name_taken(self, name: str) -> bool:
        """rclone aktualisiert ein bestehendes Remote bei 'config create'
        einfach in-place (verifiziert), statt einen Fehler zu werfen --
        die App fragt daher nach, statt das Ändern einer bestehenden
        Verbindung künstlich zu blockieren."""
        if name not in rclone.list_remotes():
            return True
        return confirm_yes_no(self, t("cloud.name_taken_title"), t("cloud.name_taken_text", name=name))

    # ---------- Einreichen: lokaler Ordner/USB-Stick ----------

    def _submit_local(self):
        name = self.name_edit.text().strip() or t(self.selected_provider.label_key)

        if not self.chosen_local_folder:
            QMessageBox.warning(self, t("cloud.local_no_folder_title"), t("cloud.local_no_folder_text"))
            return

        if not rclone.is_local_folder_writable(self.chosen_local_folder):
            QMessageBox.warning(
                self, t("cloud.local_not_writable_title"), t("cloud.local_not_writable_text")
            )
            return

        remote_path = f"{self.chosen_local_folder.rstrip('/')}/{DEFAULT_REMOTE_PATH}"
        self._finish_success(name, remote="", remote_path=remote_path)

    # ---------- Gemeinsamer Hintergrund-Worker-Ablauf ----------

    def _run_worker(self, worker: QThread, name: str):
        self._set_form_enabled(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.status_label.setText(t("cloud.connecting"))

        self._worker = worker
        self._worker.step_progress.connect(self._on_step_progress)
        self._worker.finished_setup.connect(
            lambda success, message: self._on_worker_finished(success, message, name)
        )
        self._worker.start()

    def _on_step_progress(self, percent: int, message: str):
        self.progress_bar.setValue(percent)
        self.status_label.setText(message)

    def _set_form_enabled(self, enabled: bool):
        self.action_button.setEnabled(enabled)
        self.back_button.setEnabled(enabled)
        self.skip_button.setEnabled(enabled)

    def _on_worker_finished(self, success: bool, message: str, name: str):
        self._set_form_enabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText(message)

        if not success:
            return

        self._finish_success(name, remote=name, remote_path=DEFAULT_REMOTE_PATH)

    def _finish_success(self, name: str, remote: str, remote_path: str) -> None:
        # Beim Aktualisieren eines bereits bestehenden Remotes existiert meist
        # schon ein passendes Profil dafür -- kein zweites, doppeltes Profil
        # anlegen (remote="" bei lokalen Ordnern ist kein Kollisionsfall,
        # da mehrere USB-Profile diesen leeren Wert teilen).
        existing_profile = None
        if remote:
            existing_profile = next(
                (p for p in Settings.list_profiles() if p["remote"] == remote), None
            )

        if existing_profile is None:
            profile = Settings.add_profile(
                name=name, remote=remote, remote_path=remote_path,
                sync_interval=15, auto_sync=True,
            )
            self.repo.assign_unassigned_top_level_groups_to_profile(profile["id"])

        QMessageBox.information(self, t("cloud.done_title"), t("cloud.done_text", name=name))
        self.accept()
