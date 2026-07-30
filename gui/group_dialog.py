from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QComboBox, QLabel,
    QDialogButtonBox, QVBoxLayout
)

from core.models import Group
from core.settings import Settings

LOCAL_PROFILE_LABEL = "Lokal (kein Sync)"


class AddEditGroupDialog(QDialog):

    def __init__(self, all_groups: list[Group], group: Optional[Group] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ordner bearbeiten" if group else "Ordner hinzufügen")
        self.group = group
        self.all_groups = all_groups
        self.groups_by_id = {g.id: g for g in all_groups}

        excluded_ids = self._descendant_ids(group.id if group else None)
        if group:
            excluded_ids.add(group.id)

        self.name_edit = QLineEdit(group.name if group else "")

        self.parent_combo = QComboBox()
        self.parent_combo.addItem("(Top-Level)", None)
        for g in all_groups:
            if g.id in excluded_ids:
                continue
            self.parent_combo.addItem(g.name, g.id)
        if group and group.parent_id is not None:
            index = self.parent_combo.findData(group.parent_id)
            if index >= 0:
                self.parent_combo.setCurrentIndex(index)

        self.profile_combo = QComboBox()
        self.profile_combo.addItem(LOCAL_PROFILE_LABEL, None)
        for profile in Settings.list_profiles():
            self.profile_combo.addItem(profile["name"], profile["id"])
        if group and group.parent_id is None and group.profile_id:
            index = self.profile_combo.findData(group.profile_id)
            if index >= 0:
                self.profile_combo.setCurrentIndex(index)

        self.inherited_label = QLabel()
        self.inherited_label.setWordWrap(True)

        self.parent_combo.currentIndexChanged.connect(self._update_profile_visibility)

        form = QFormLayout()
        form.addRow("Name", self.name_edit)
        form.addRow("Übergeordneter Ordner", self.parent_combo)
        form.addRow("Sync-Profil", self.profile_combo)
        form.addRow("", self.inherited_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

        self._update_profile_visibility()

    def _descendant_ids(self, group_id: Optional[int]) -> set:
        if group_id is None:
            return set()
        children = {g.id for g in self.all_groups if g.parent_id == group_id}
        result = set(children)
        for child_id in children:
            result |= self._descendant_ids(child_id)
        return result

    def _top_level_profile_name(self, parent_id: Optional[int]) -> str:
        current = self.groups_by_id.get(parent_id)
        while current is not None and current.parent_id is not None:
            current = self.groups_by_id.get(current.parent_id)
        if current is None or not current.profile_id:
            return LOCAL_PROFILE_LABEL
        profile = Settings.get_profile(current.profile_id)
        return profile["name"] if profile else LOCAL_PROFILE_LABEL

    def _update_profile_visibility(self):
        is_top_level = self.parent_combo.currentData() is None
        self.profile_combo.setVisible(is_top_level)
        self.inherited_label.setVisible(not is_top_level)
        if not is_top_level:
            name = self._top_level_profile_name(self.parent_combo.currentData())
            self.inherited_label.setText(f"Erbt Sync-Profil vom übergeordneten Ordner: {name}")

    def _on_accept(self):
        if not self.name_edit.text().strip():
            return
        self.accept()

    def get_group(self) -> tuple[str, Optional[int], Optional[str]]:
        """Gibt (name, parent_id, profile_id) zurück. profile_id ist nur bei
        Top-Level-Ordnern relevant (siehe Vererbung in
        BookmarkRepository.items_for_profile)."""
        name = self.name_edit.text().strip()
        parent_id = self.parent_combo.currentData()
        profile_id = self.profile_combo.currentData() if parent_id is None else None
        return name, parent_id, profile_id
