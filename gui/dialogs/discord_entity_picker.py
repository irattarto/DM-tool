"""Pick which entities (NPCs, locations, ...) to post to Discord as name + primary picture cards.

Entities without a primary picture are listed but disabled, so it is visible why they are skipped.
"""

from dataclasses import dataclass
from typing import Iterable, List

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout,
)

from gui.theme import set_props
from utils.natural_sort import natural_key


@dataclass
class EntityChoice:
    id: int
    name: str
    path: str = ""      # primary image file; empty when the entity has none


class DiscordEntityPickerDialog(QDialog):
    """A checklist of entities sorted by name; "Send..." continues to the preview-and-confirm dialog."""

    def __init__(self, choices: List[EntityChoice], label: str = "NPCs",
                 preselected_ids: Iterable[int] = (), parent=None):
        super().__init__(parent)
        self.label = label
        self.setWindowTitle(f"Send {label} to Discord")
        self.setModal(True)
        self.resize(480, 560)
        preselected = set(preselected_ids)
        self._choices = sorted(choices, key=lambda c: (natural_key(c.name), c.id))
        self._setup_ui(preselected)
        self._update_summary()

    def _setup_ui(self, preselected):
        layout = QVBoxLayout(self)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(f"Search {self.label}...")
        self.search_edit.textChanged.connect(self._apply_filter)
        layout.addWidget(self.search_edit)

        row = QHBoxLayout()
        select_all = QPushButton("Select all")
        select_all.clicked.connect(lambda: self._set_visible_checked(True))
        select_none = QPushButton("Select none")
        select_none.clicked.connect(lambda: self._set_visible_checked(False))
        row.addWidget(select_all)
        row.addWidget(select_none)
        row.addStretch()
        layout.addLayout(row)

        self.list_widget = QListWidget()
        self.list_widget.setIconSize(QSize(48, 48))
        for choice in self._choices:
            item = QListWidgetItem(choice.name or "(no name)")
            item.setData(Qt.ItemDataRole.UserRole, choice)
            if choice.path:
                pixmap = QPixmap(choice.path)
                if not pixmap.isNull():
                    item.setIcon(QIcon(pixmap.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio,
                                                     Qt.TransformationMode.SmoothTransformation)))
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked if choice.id in preselected else Qt.CheckState.Unchecked)
            else:
                item.setText(f"{choice.name or '(no name)'}  (no image, skipped)")
                item.setFlags(item.flags() & ~(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable))
            self.list_widget.addItem(item)
        self.list_widget.itemChanged.connect(lambda _item: self._update_summary())
        layout.addWidget(self.list_widget, 1)

        self.summary_label = QLabel("")
        self.summary_label.setTextFormat(Qt.TextFormat.PlainText)
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        self.send_btn = QPushButton("Send...")
        set_props(self.send_btn, variant="primary")
        self.send_btn.clicked.connect(self.accept)
        buttons.addWidget(self.send_btn)
        layout.addLayout(buttons)

    def _items(self):
        return [self.list_widget.item(i) for i in range(self.list_widget.count())]

    def _apply_filter(self, text: str):
        needle = text.strip().casefold()
        for item in self._items():
            item.setHidden(bool(needle) and needle not in item.data(Qt.ItemDataRole.UserRole).name.casefold())

    def _set_visible_checked(self, checked: bool):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for item in self._items():
            if not item.isHidden() and item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                item.setCheckState(state)

    def selected_choices(self) -> List[EntityChoice]:
        """The ticked entities, sorted by name."""
        return [item.data(Qt.ItemDataRole.UserRole) for item in self._items()
                if item.flags() & Qt.ItemFlag.ItemIsUserCheckable and item.checkState() == Qt.CheckState.Checked]

    def _update_summary(self):
        selected = len(self.selected_choices())
        skipped = sum(1 for c in self._choices if not c.path)
        text = f"{selected} will be sent"
        if skipped:
            text += f", {skipped} skipped (no primary image)"
        self.summary_label.setText(text + ".")
        self.send_btn.setEnabled(selected > 0)
