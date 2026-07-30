from pathlib import Path
from datetime import datetime
import shutil


BACKUP_DIR = (
    Path.home()
    / ".guideosbookhub"
    / "backups"
)

BACKUP_DIR.mkdir(
    parents=True,
    exist_ok=True
)


class BackupManager:

    def create_backup(self, database_file):

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        target_file = (
            BACKUP_DIR
            /
            f"guideosbookhub_{timestamp}.db"
        )

        shutil.copy2(
            database_file,
            target_file
        )

        return target_file