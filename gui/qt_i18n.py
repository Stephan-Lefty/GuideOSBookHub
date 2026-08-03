from PyQt6.QtWidgets import QDialogButtonBox, QMessageBox

from core.i18n import t


def _standard_button_texts() -> dict:
    return {
        QDialogButtonBox.StandardButton.Ok: t("common.ok"),
        QDialogButtonBox.StandardButton.Cancel: t("common.cancel"),
        QDialogButtonBox.StandardButton.Close: t("common.close"),
    }


def germanize_button_box(buttons: QDialogButtonBox) -> None:
    """PyQt6 beschriftet Standard-Buttons (Ok/Cancel/Close) über Qts eigene
    Übersetzungsdateien, die auf vielen Systemen nicht installiert sind
    (z.B. fehlendes qt6-translations-l10n) und in AppImage/Flatpak/.deb
    ohnehin nicht garantiert mitkommen. Deshalb werden die Texte hier direkt
    (sprachabhängig über core/i18n.py) gesetzt, statt sich auf die
    Systemlokalisierung zu verlassen."""
    for standard, text in _standard_button_texts().items():
        button = buttons.button(standard)
        if button is not None:
            button.setText(text)


def confirm_yes_no(parent, title: str, text: str) -> bool:
    """Ersatz für QMessageBox.question(...) == QMessageBox.StandardButton.Yes,
    aus demselben Grund mit fest beschrifteten Ja/Nein-Buttons statt der
    (ohne Qt-Übersetzung englischen) Standard-Yes/No-Buttons."""
    box = QMessageBox(QMessageBox.Icon.Question, title, text, parent=parent)
    yes_button = box.addButton(t("common.yes"), QMessageBox.ButtonRole.YesRole)
    box.addButton(t("common.no"), QMessageBox.ButtonRole.NoRole)
    box.setDefaultButton(yes_button)
    box.exec()
    return box.clickedButton() == yes_button
