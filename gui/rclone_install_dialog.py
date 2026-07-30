from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton

from core import rclone


class RcloneInstallWorker(QThread):
    """Installiert rclone im Hintergrund, damit die grafische
    PolicyKit-Abfrage (pkexec) die Oberfläche nicht blockiert."""

    finished_install = pyqtSignal(bool, str)

    def run(self):
        try:
            rclone.install_rclone()
            self.finished_install.emit(True, "rclone wurde erfolgreich installiert.")
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
        self.setWindowTitle("rclone wird benötigt")
        self.resize(440, 220)
        self._worker = None

        layout = QVBoxLayout(self)

        self.info_label = QLabel(
            "GuideOSBookHub synchronisiert Lesezeichen über rclone, das auf "
            "diesem System nicht gefunden wurde.\n\n"
            "Ohne rclone funktioniert die App weiter als lokaler "
            "Lesezeichen-Manager, aber ohne Cloud-Synchronisation.\n\n"
            "Soll rclone jetzt installiert werden? Es erscheint eine "
            "grafische Rechte-Abfrage (PolicyKit), da dafür "
            "Administratorrechte nötig sind."
        )
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        buttons_row = QHBoxLayout()
        self.skip_button = QPushButton("Später")
        self.skip_button.clicked.connect(self.reject)
        self.install_button = QPushButton("Installieren")
        self.install_button.clicked.connect(self._on_install_clicked)
        buttons_row.addWidget(self.skip_button)
        buttons_row.addStretch()
        buttons_row.addWidget(self.install_button)
        layout.addLayout(buttons_row)

    def _on_install_clicked(self):
        self.install_button.setEnabled(False)
        self.skip_button.setEnabled(False)
        self.info_label.setText("Installation läuft, bitte die Rechte-Abfrage bestätigen...")

        self._worker = RcloneInstallWorker()
        self._worker.finished_install.connect(self._on_install_finished)
        self._worker.start()

    def _on_install_finished(self, success: bool, message: str):
        self.info_label.setText(message)
        self.skip_button.setEnabled(True)

        if success:
            self.install_button.setText("Fertig")
            self.install_button.clicked.disconnect()
            self.install_button.clicked.connect(self.accept)
            self.install_button.setEnabled(True)
        else:
            self.install_button.setText("Erneut versuchen")
            self.install_button.setEnabled(True)
