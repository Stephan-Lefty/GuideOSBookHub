# GuideOSBookHub
# Copyright (C) 2026 Stephan R.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See the LICENSE file for details.

import sys
from importlib.resources import as_file, files

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from core import rclone
from gui.home_window import HomeWindow
from gui.rclone_install_dialog import RcloneInstallDialog
from gui.theme import apply_theme

# importlib.resources statt eines Pfads relativ zu __file__, da Letzteres
# nach einer echten (nicht-editable) pip/pipx-Installation ins Leere zeigt --
# icons/ liegt im Quell-Checkout, wird aber von setuptools nicht automatisch
# mitinstalliert. assets/ ist dagegen ein echtes Package mit package_data
# (siehe setup.py) und funktioniert in Quellverzeichnis und Installation
# gleichermaßen.
ICON_RESOURCE = files("assets") / "icon-256.png"


def main():

    app = QApplication(sys.argv)
    apply_theme(app)
    with as_file(ICON_RESOURCE) as icon_path:
        app.setWindowIcon(QIcon(str(icon_path)))

    if not rclone.is_rclone_installed():
        RcloneInstallDialog().exec()

    window = HomeWindow()

    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()