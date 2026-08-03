from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton

from core import rclone
from core.i18n import t


class RcloneInstallWorker(QThread):
    """Installiert rclone im Hintergrund, damit die grafische
    PolicyKit-Abfrage (pkexec) die Oberfläche nicht blockiert."""

    finished_install = pyqtSignal(bool, str)

    def run(self):
        try:
            rclone.install_rclone()
            self.finished_install.emit(True, t("rclone_install.success"))
        except rclone.RcloneRemoteError as e:
            message = str(e) + (f"\n\n{e.stderr}" if e.stderr else "")
            self.finished_install.emit(False, message)
        except rclone.RcloneError as e:
            self.finished_install.emit(False, str(e))


class RcloneInstallDialog(QDialog):
    """Wird gezeigt, wenn rclone auf dem System fehlt. Es passiert nichts
    automatisch im Hintergrund -- der Nutzer muss aktiv auf 'Installieren'
    klicken, danach erscheint die native PolicyKit-Rechteabfrage (pkexec)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("rclone_install.window_title"))
        self.resize(440, 220)
        self._worker = None

        layout = QVBoxLayout(self)

        self.info_label = QLabel(t("rclone_install.info"))
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        buttons_row = QHBoxLayout()
        self.skip_button = QPushButton(t("rclone_install.later_button"))
        self.skip_button.clicked.connect(self.reject)
        self.install_button = QPushButton(t("rclone_install.install_button"))
        self.install_button.clicked.connect(self._on_install_clicked)
        buttons_row.addWidget(self.skip_button)
        buttons_row.addStretch()
        buttons_row.addWidget(self.install_button)
        layout.addLayout(buttons_row)

    def _on_install_clicked(self):
        self.install_button.setEnabled(False)
        self.skip_button.setEnabled(False)
        self.info_label.setText(t("rclone_install.installing"))

        self._worker = RcloneInstallWorker()
        self._worker.finished_install.connect(self._on_install_finished)
        self._worker.start()

    def _on_install_finished(self, success: bool, message: str):
        self.info_label.setText(message)
        self.skip_button.setEnabled(True)

        if success:
            self.install_button.setText(t("rclone_install.done_button"))
            self.install_button.clicked.disconnect()
            self.install_button.clicked.connect(self.accept)
            self.install_button.setEnabled(True)
        else:
            self.install_button.setText(t("rclone_install.retry_button"))
            self.install_button.setEnabled(True)
