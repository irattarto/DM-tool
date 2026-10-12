"""History of an entry: its earlier versions, with a preview and Restore."""

from typing import List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QSplitter,
                             QTextBrowser, QVBoxLayout)


class HistoryDialog(QDialog):
    """Earlier versions (newest first). Restore puts the chosen one into the editor; the editor still needs a Save."""

    def __init__(self, title: str, versions: List[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"History: {title}")
        self.resize(780, 520)
        self.restored: Optional[dict] = None
        self._versions = versions
        layout = QVBoxLayout(self)
        if not versions:
            layout.addWidget(QLabel("There are no earlier versions yet. Each save keeps the text it replaces "
                                    "(the last 20)."))
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.list = QListWidget()
        self.list.setMaximumWidth(260)
        for version in versions:
            item = QListWidgetItem(f"{version['saved_date']}\n{version['title']}")
            self.list.addItem(item)
        self.list.currentRowChanged.connect(self._show)
        splitter.addWidget(self.list)
        self.preview = QTextBrowser()
        splitter.addWidget(self.preview)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)
        buttons = QHBoxLayout()
        self.restore_button = QPushButton("Restore this version")
        self.restore_button.setToolTip("Put this text back into the editor (save to keep it)")
        self.restore_button.clicked.connect(self._restore)
        buttons.addWidget(self.restore_button)
        buttons.addStretch(1)
        close = QPushButton("Close")
        close.clicked.connect(self.reject)
        buttons.addWidget(close)
        layout.addLayout(buttons)
        if versions:
            self.list.setCurrentRow(0)
        else:
            self.restore_button.setEnabled(False)

    def _show(self, row: int) -> None:
        if 0 <= row < len(self._versions):
            self.preview.setMarkdown(self._versions[row].get('content') or '')
        self.restore_button.setEnabled(0 <= row < len(self._versions))

    def _restore(self) -> None:
        row = self.list.currentRow()
        if 0 <= row < len(self._versions):
            self.restored = self._versions[row]
            self.accept()
