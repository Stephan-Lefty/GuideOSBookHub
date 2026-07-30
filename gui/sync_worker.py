from PyQt6.QtCore import QThread, pyqtSignal

from core import rclone
from core.database import Database
from core.repository import BookmarkRepository
from core.sync import SyncEngine


class SyncWorker(QThread):
    """Führt die Synchronisation eines oder mehrerer Profile in einem
    Hintergrund-Thread aus, damit blockierende rclone-Subprozessaufrufe die
    GUI nicht einfrieren. Öffnet eine eigene Datenbankverbindung, da
    sqlite3-Connections nicht threadübergreifend geteilt werden dürfen."""

    profile_finished = pyqtSignal(str, object)  # profile_name, SyncResult
    finished_all = pyqtSignal()

    def __init__(self, profiles: list[dict], parent=None):
        super().__init__(parent)
        self.profiles = profiles

    def run(self):
        db = Database()
        repo = BookmarkRepository(db)
        for profile in self.profiles:
            engine = SyncEngine(repo, profile["id"], profile["remote"], profile["remote_path"])
            result = engine.sync()
            self.profile_finished.emit(profile["name"], result)
        db.close()
        self.finished_all.emit()


class ConnectionTestWorker(QThread):
    """Prüft die Erreichbarkeit eines rclone-Remotes im Hintergrund."""

    finished_test = pyqtSignal(bool, str)

    def __init__(self, remote: str, parent=None):
        super().__init__(parent)
        self.remote = remote

    def run(self):
        try:
            rclone.check_remote_reachable(self.remote)
            self.finished_test.emit(True, "Verbindung erfolgreich.")
        except rclone.RcloneRemoteError as e:
            message = str(e) + (f"\n\n{e.stderr}" if e.stderr else "")
            self.finished_test.emit(False, message)
        except rclone.RcloneError as e:
            self.finished_test.emit(False, str(e))
