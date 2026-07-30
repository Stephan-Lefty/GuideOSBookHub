from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QComboBox, QCheckBox,
    QDialogButtonBox, QVBoxLayout
)

from core.models import Bookmark, Group


class AddEditBookmarkDialog(QDialog):

    def __init__(self, groups: list[Group], bookmark: Optional[Bookmark] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Lesezeichen bearbeiten" if bookmark else "Lesezeichen hinzufügen")
        self.bookmark = bookmark

        self.title_edit = QLineEdit(bookmark.title if bookmark else "")
        self.url_edit = QLineEdit(bookmark.url if bookmark else "")
        self.description_edit = QLineEdit(bookmark.description if bookmark else "")
        self.tags_edit = QLineEdit(bookmark.tags if bookmark else "")

        self.group_combo = QComboBox()
        self.group_combo.addItem("(kein Ordner)", None)
        for group in groups:
            self.group_combo.addItem(group.name, group.id)
        if bookmark and bookmark.group_id is not None:
            index = self.group_combo.findData(bookmark.group_id)
            if index >= 0:
                self.group_combo.setCurrentIndex(index)

        self.favorite_check = QCheckBox("Favorit")
        if bookmark:
            self.favorite_check.setChecked(bookmark.favorite)

        form = QFormLayout()
        form.addRow("Titel", self.title_edit)
        form.addRow("URL", self.url_edit)
        form.addRow("Beschreibung", self.description_edit)
        form.addRow("Tags (kommagetrennt)", self.tags_edit)
        form.addRow("Ordner", self.group_combo)
        form.addRow("", self.favorite_check)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _on_accept(self):
        if not self.title_edit.text().strip() or not self.url_edit.text().strip():
            return
        self.accept()

    def get_bookmark(self) -> Bookmark:
        group_id = self.group_combo.currentData()

        if self.bookmark:
            self.bookmark.title = self.title_edit.text().strip()
            self.bookmark.url = self.url_edit.text().strip()
            self.bookmark.description = self.description_edit.text().strip()
            self.bookmark.tags = self.tags_edit.text().strip()
            self.bookmark.group_id = group_id
            self.bookmark.favorite = self.favorite_check.isChecked()
            return self.bookmark

        return Bookmark(
            id=None,
            title=self.title_edit.text().strip(),
            url=self.url_edit.text().strip(),
            description=self.description_edit.text().strip(),
            tags=self.tags_edit.text().strip(),
            group_id=group_id,
            favorite=self.favorite_check.isChecked(),
        )
