"""Quick capture: one line typed while playing goes into the current session, with the names in it linked."""

from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QLabel, QLineEdit, QVBoxLayout


class QuickCaptureDialog(QDialog):
    """A small window with one line. Enter adds it to the session, Escape cancels."""

    def __init__(self, session_title: str, preview: Callable[[str], str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Quick capture")
        self.setModal(True)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.resize(560, 120)
        self._preview = preview
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Add a line to <b>{session_title}</b>"))
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("What just happened? Names of entries are linked automatically. Enter adds, Esc cancels.")
        self.edit.textChanged.connect(self._update_preview)
        self.edit.returnPressed.connect(self._accept_if_text)
        layout.addWidget(self.edit)
        self.hint = QLabel(" ")
        self.hint.setEnabled(False)
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)

    def text(self) -> str:
        return self.edit.text().strip()

    def _update_preview(self, text: str) -> None:
        self.hint.setText(self._preview(text.strip()) if text.strip() else " ")

    def _accept_if_text(self) -> None:
        if self.text():
            self.accept()
