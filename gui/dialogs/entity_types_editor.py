"""Editor for entity types: rename, reorder, hide and add custom types."""

import re
from typing import Dict, List

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QPushButton,
    QLabel, QHeaderView, QInputDialog, QMessageBox, QAbstractItemView,
)

from config.entity_types import get_registry, is_valid_key, RESERVED_KEYS, builtin_keys

COL_LABEL, COL_PLURAL, COL_KEY, COL_VISIBLE = range(4)


def slugify(label: str) -> str:
    """Turn a label into a candidate immutable key (lowercase letters, digits, underscores)."""
    slug = re.sub(r'[^a-z0-9]+', '_', label.strip().lower()).strip('_')
    return slug


class EntityTypesEditor(QWidget):
    """Edits the entity type list. Keys never change; only labels, order and visibility do."""

    types_changed = pyqtSignal()

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self._rows: List[Dict] = []
        self._dirty = False
        self._building = False
        self._setup_ui()
        self.reload()

    # --- UI -----------------------------------------------------------
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        info = QLabel(
            "Rename, reorder or hide entity types, or add your own (for example Monster or Deity). "
            "The key of a type never changes, so existing documents and links keep working. "
            "Built-in types can be hidden but not deleted; custom types can be deleted when no "
            "document uses them. Hiding a type keeps its documents."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Name", "Plural", "Key", "Visible"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(COL_LABEL, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_PLURAL, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_KEY, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_VISIBLE, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.table)

        buttons = QHBoxLayout()
        self.add_btn = QPushButton("Add Type...")
        self.up_btn = QPushButton("Move Up")
        self.down_btn = QPushButton("Move Down")
        self.delete_btn = QPushButton("Delete")
        self.add_btn.clicked.connect(self._on_add_clicked)
        self.up_btn.clicked.connect(lambda: self.move_selected(-1))
        self.down_btn.clicked.connect(lambda: self.move_selected(1))
        self.delete_btn.clicked.connect(self._on_delete_clicked)
        for button in (self.add_btn, self.up_btn, self.down_btn, self.delete_btn):
            buttons.addWidget(button)
        buttons.addStretch()
        layout.addLayout(buttons)

    # --- model --------------------------------------------------------
    def reload(self):
        """Load the current registry state."""
        self._rows = [dict(r) for r in get_registry().to_rows()]
        self._dirty = False
        self._render()

    def rows(self) -> List[Dict]:
        return [dict(r) for r in self._rows]

    def is_dirty(self) -> bool:
        return self._dirty

    def _render(self):
        self._building = True
        self.table.setRowCount(len(self._rows))
        for i, row in enumerate(self._rows):
            label = QTableWidgetItem(row['label_singular'])
            plural = QTableWidgetItem(row['label_plural'])
            key = QTableWidgetItem(row['key'] + ("" if not row.get('builtin') else "  (built-in)"))
            key.setFlags(key.flags() & ~Qt.ItemFlag.ItemIsEditable)
            visible = QTableWidgetItem()
            visible.setFlags(visible.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            visible.setCheckState(Qt.CheckState.Unchecked if row.get('hidden') else Qt.CheckState.Checked)
            for column, item in enumerate((label, plural, key, visible)):
                self.table.setItem(i, column, item)
        self._building = False

    def _on_item_changed(self, item: QTableWidgetItem):
        if self._building:
            return
        row = self._rows[item.row()]
        if item.column() == COL_LABEL:
            row['label_singular'] = item.text().strip() or row['label_singular']
        elif item.column() == COL_PLURAL:
            row['label_plural'] = item.text().strip() or row['label_plural']
        elif item.column() == COL_VISIBLE:
            row['hidden'] = item.checkState() != Qt.CheckState.Checked
        self._dirty = True

    def _unique_key(self, label: str) -> str:
        base = slugify(label) or "type"
        taken = {r['key'] for r in self._rows} | set(RESERVED_KEYS) | set(builtin_keys()) | {'session'}
        key, n = base, 2
        while key in taken or not is_valid_key(key):
            key = f"{base}_{n}"
            n += 1
        return key

    def add_type(self, label: str, plural: str = "") -> str:
        """Append a custom type and return its (immutable) key."""
        label = label.strip()
        if not label:
            raise ValueError("A name is required")
        key = self._unique_key(label)
        self._rows.append({
            'key': key, 'label_singular': label,
            'label_plural': plural.strip() or label + 's',
            'hidden': False, 'builtin': False,
        })
        self._dirty = True
        self._render()
        return key

    def move_selected(self, delta: int) -> None:
        row = self.table.currentRow()
        target = row + delta
        if row < 0 or not (0 <= target < len(self._rows)):
            return
        self._rows[row], self._rows[target] = self._rows[target], self._rows[row]
        self._dirty = True
        self._render()
        self.table.selectRow(target)

    def can_delete(self, row_index: int):
        """Return (allowed, reason)."""
        if not (0 <= row_index < len(self._rows)):
            return False, "Select a type first."
        row = self._rows[row_index]
        if row.get('builtin'):
            return False, "Built-in types cannot be deleted. Untick Visible to hide it instead."
        count = self.db.count_documents_of_type(row['key'])
        if count:
            return False, f"{count} document(s) still use this type. Delete or change them first, or hide the type."
        return True, ""

    def delete_row(self, row_index: int) -> bool:
        allowed, _ = self.can_delete(row_index)
        if not allowed:
            return False
        del self._rows[row_index]
        self._dirty = True
        self._render()
        return True

    # --- button handlers ----------------------------------------------
    def _on_add_clicked(self):
        label, ok = QInputDialog.getText(self, "Add Entity Type", "Name of the new type (singular):")
        if ok and label.strip():
            try:
                self.add_type(label)
            except ValueError as e:
                QMessageBox.warning(self, "Cannot add type", str(e))

    def _on_delete_clicked(self):
        index = self.table.currentRow()
        allowed, reason = self.can_delete(index)
        if not allowed:
            QMessageBox.information(self, "Cannot delete", reason)
            return
        self.delete_row(index)

    # --- apply --------------------------------------------------------
    def apply(self) -> bool:
        """Validate, save to the database and update the registry. Returns True if saved."""
        if not self._dirty:
            return False
        self.db.save_entity_types(self._rows)  # raises ValueError on invalid input
        get_registry().set_rows(self._rows)
        self._dirty = False
        self.types_changed.emit()
        return True
