"""Dialogs of the automatic helpers: new names found in a text, and the campaign health check."""

from typing import Dict, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
                             QPushButton, QScrollArea, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from config.entity_types import get_registry
from services.health_service import HealthIssue
from utils.name_matching import NameCandidate

SKIP, IGNORE, LINK, CREATE = 'skip', 'never', 'link', 'create'


class NewNamesDialog(QDialog):
    """Names in a text that are not links yet. Each can be linked to an existing entry it may mean, turned into a new
    entry, skipped, or never offered again; the name itself can be edited first (what part is the link or the title)."""

    def __init__(self, candidates: List[NameCandidate], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Names found in the text")
        self.setModal(True)
        self.candidates = candidates
        self.edits: List[QLineEdit] = []
        self.combos: List[QComboBox] = []
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("These names are not links yet. Edit a name to change which part becomes the link or "
                                "the title,<br>then choose what to do. 'Skip' leaves it for now, 'Never' stops asking."))
        holder = QWidget()
        rows = QVBoxLayout(holder)
        registry = get_registry()
        kinds = [k for k in registry.keys_for('create') if k not in ('session', 'character')]
        for candidate in candidates:
            row = QHBoxLayout()
            edit = QLineEdit(candidate.text)
            edit.setMinimumWidth(180)
            self.edits.append(edit)
            row.addWidget(edit, 1)
            combo = QComboBox()
            combo.setMinimumWidth(260)
            combo.addItem("Skip", (SKIP, None, None))
            for entry in candidate.matches[:8]:
                combo.addItem(f"Link to: {entry.title} ({registry.label(entry.entity_type)})",
                              (LINK, entry.doc_id, entry.entity_type))
            for kind in kinds:
                combo.addItem(f"Create new {registry.label(kind)}", (CREATE, None, kind))
            combo.addItem("Never", (IGNORE, None, None))
            if len(candidate.matches) == 1 or (candidate.matches and candidate.exact):
                combo.setCurrentIndex(1)                      # one entry it can mean (or the full title): link it
            self.combos.append(combo)
            row.addWidget(combo)
            rows.addLayout(row)
        rows.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(holder)
        layout.addWidget(scroll, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Apply")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.resize(640, min(130 + 38 * len(candidates), 560))

    def choices(self) -> List[dict]:
        """One dict per name: text (as found), name (as edited), action (skip/never/link/create), doc_id, kind."""
        result = []
        for candidate, edit, combo in zip(self.candidates, self.edits, self.combos):
            action, doc_id, kind = combo.currentData()
            result.append({'text': candidate.text, 'name': edit.text().strip() or candidate.text,
                           'action': action, 'doc_id': doc_id, 'kind': kind})
        return result


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
