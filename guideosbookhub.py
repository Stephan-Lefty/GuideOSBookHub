import sys
from pathlib import Path

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from core import rclone
from gui.mainwindow import MainWindow
from gui.rclone_install_dialog import RcloneInstallDialog

ICON_PATH = Path(__file__).parent / "icons" / "icon-256.png"


def main():

    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(str(ICON_PATH)))

    if not rclone.is_rclone_installed():
        RcloneInstallDialog().exec()

    window = MainWindow()

    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()