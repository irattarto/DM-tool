"""A small message at the bottom of the window with an Undo button that goes away by itself."""

from PyQt6.QtCore import QEvent, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton


class UndoToast(QFrame):
    """Shows "<text> [Undo]" for a few seconds, centred near the bottom of its parent window."""

    undo_clicked = pyqtSignal()
    expired = pyqtSignal()

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("undoToast")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 10, 8)
        layout.setSpacing(16)
        self.label = QLabel()
        layout.addWidget(self.label)
        self.undo_button = QPushButton("Undo")
        self.undo_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.undo_button.clicked.connect(self._on_undo)
        layout.addWidget(self.undo_button)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_timeout)
        parent.installEventFilter(self)
        self.hide()

    def show_message(self, text: str, milliseconds: int = 10000) -> None:
        palette = self.palette()
        background = palette.color(QPalette.ColorRole.Text).name()
        foreground = palette.color(QPalette.ColorRole.Window).name()
        self.setStyleSheet(
            f"#undoToast {{ background: {background}; border-radius: 8px; border: none; }}"
            f"#undoToast QLabel {{ color: {foreground}; }}"
            f"#undoToast QPushButton {{ color: {foreground}; background: transparent; border: 1px solid {foreground};"
            f" border-radius: 4px; padding: 3px 12px; font-weight: 600; }}")
        self.label.setText(text)
        self.adjustSize()
        self._reposition()
        self.show()
        self.raise_()
        self._timer.start(milliseconds)

    def dismiss(self) -> None:
        self._timer.stop()
        self.hide()

    def is_active(self) -> bool:
        return self.isVisible()

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.Type.Resize and self.isVisible():
            self._reposition()
        return False

    def _reposition(self) -> None:
        parent = self.parentWidget()
        if parent is not None:
            self.move((parent.width() - self.width()) // 2, parent.height() - self.height() - 48)

    def _on_undo(self) -> None:
        self.dismiss()
        self.undo_clicked.emit()

    def _on_timeout(self) -> None:
        self.hide()
        self.expired.emit()
