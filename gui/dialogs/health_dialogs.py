"""Dialogs of the automatic helpers: new names found in a text, and the campaign health check."""

from typing import Dict, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QMessageBox, QPushButton,
                             QScrollArea, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from config.entity_types import get_registry
from services.health_service import HealthIssue

SKIP, IGNORE = '', '__ignore__'


class NewNamesDialog(QDialog):
    """Names in a text that match no entry: choose what each one is (or skip it, or never ask again)."""

    def __init__(self, names: List[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("New names found")
        self.setModal(True)
        self.combos: Dict[str, QComboBox] = {}
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("These names are not entries yet. Choose a type to create an entry and link the name,<br>"
                                "or leave 'Skip'. 'Never' stops asking about that name."))
        holder = QWidget()
        rows = QVBoxLayout(holder)
        registry = get_registry()
        kinds = [k for k in registry.keys_for('create') if k not in ('session', 'character')]
        for name in names:
            row = QHBoxLayout()
            row.addWidget(QLabel(f"<b>{name}</b>"), 1)
            combo = QComboBox()
            combo.addItem("Skip", SKIP)
            for kind in kinds:
                combo.addItem(registry.label(kind), kind)
            combo.addItem("Never", IGNORE)
            self.combos[name] = combo
            row.addWidget(combo)
            rows.addLayout(row)
        rows.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(holder)
        layout.addWidget(scroll, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Create")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.resize(460, min(120 + 36 * len(names), 520))

    def choices(self) -> Dict[str, str]:
        """name -> entity type key, SKIP or IGNORE."""
        return {name: combo.currentData() for name, combo in self.combos.items()}


class HealthCheckDialog(QDialog):
    """What needs attention in the campaign; double-click opens an entry, duplicates can be merged."""

    open_requested = pyqtSignal(int)
    merge_requested = pyqtSignal(int, int)      # keep id, drop id

    def __init__(self, issues: List[HealthIssue], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Campaign health check")
        self.resize(640, 520)
        layout = QVBoxLayout(self)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["What", "Type"])
        self.tree.setColumnWidth(0, 420)
        self.tree.itemDoubleClicked.connect(self._open_item)
        self.tree.currentItemChanged.connect(lambda *_: self._update_buttons())
        layout.addWidget(self.tree, 1)
        self.summary = QLabel()
        layout.addWidget(self.summary)
        buttons = QHBoxLayout()
        self.open_button = QPushButton("Open")
        self.open_button.clicked.connect(lambda: self._open_item(self.tree.currentItem()))
        self.merge_button = QPushButton("Merge...")
        self.merge_button.setToolTip("Fold one of the two entries into the other and remove the extra one")
        self.merge_button.clicked.connect(self._merge)
        buttons.addWidget(self.open_button)
        buttons.addWidget(self.merge_button)
        buttons.addStretch(1)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        layout.addLayout(buttons)
        self.set_issues(issues)

    def set_issues(self, issues: List[HealthIssue]) -> None:
        registry = get_registry()
        self.tree.clear()
        grouped: Dict[str, QTreeWidgetItem] = {}
        for issue in issues:
            if issue.kind == 'duplicate':
                group = grouped.get('duplicate') or QTreeWidgetItem(["Possible duplicates"])
                grouped['duplicate'] = group
                row = QTreeWidgetItem([f"{issue.documents[0]['title']}  ≈  {issue.documents[1]['title']}",
                                       registry.label(issue.documents[0]['entity_type'])])
                row.setData(0, Qt.ItemDataRole.UserRole, [d['id'] for d in issue.documents])
                group.addChild(row)
                continue
            group = QTreeWidgetItem([issue.title])
            grouped[issue.kind] = group
            for doc in sorted(issue.documents, key=lambda d: d['title'].casefold()):
                row = QTreeWidgetItem([doc['title'], registry.label(doc['entity_type'])])
                row.setData(0, Qt.ItemDataRole.UserRole, [doc['id']])
                group.addChild(row)
        for group in grouped.values():
            if group.text(0) == "Possible duplicates":
                group.setText(0, f"Possible duplicates ({group.childCount()})")
            self.tree.addTopLevelItem(group)
            group.setExpanded(group.childCount() <= 12)
        self.summary.setText("Nothing needs attention." if not issues else f"{len(grouped)} kinds of things to look at.")
        self._update_buttons()

    def _ids(self, item: Optional[QTreeWidgetItem]) -> List[int]:
        return (item.data(0, Qt.ItemDataRole.UserRole) or []) if item is not None else []

    def _update_buttons(self) -> None:
        ids = self._ids(self.tree.currentItem())
        self.open_button.setEnabled(bool(ids))
        self.merge_button.setEnabled(len(ids) == 2)

    def _open_item(self, item, _column: int = 0) -> None:
        ids = self._ids(item)
        if ids:
            self.open_requested.emit(ids[0])

    def _merge(self) -> None:
        ids = self._ids(self.tree.currentItem())
        if len(ids) != 2:
            return
        first, second = self.tree.currentItem().text(0).split("  ≈  ")
        box = QMessageBox(self)
        box.setWindowTitle("Merge entries")
        box.setText("Which entry should be kept?\nThe other one is folded into it: its text is added at the end, "
                    "links and pictures move over, then it is removed.")
        keep_first = box.addButton(f"Keep '{first}'", QMessageBox.ButtonRole.AcceptRole)
        keep_second = box.addButton(f"Keep '{second}'", QMessageBox.ButtonRole.AcceptRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        if box.clickedButton() is keep_first:
            self.merge_requested.emit(ids[0], ids[1])
        elif box.clickedButton() is keep_second:
            self.merge_requested.emit(ids[1], ids[0])
