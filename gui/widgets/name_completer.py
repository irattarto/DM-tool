"""Tab completion of entry names while typing, for the text editors.

Grey text shows how the name goes on; Tab accepts it and turns the name into a link, Esc ignores it. When several
entries fit, a small list opens under the cursor (arrow keys, then Tab or Enter).
"""

from typing import Callable, List, Optional

from PyQt6.QtCore import QObject, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import QListWidget, QListWidgetItem, QTextEdit

from config.entity_types import get_registry
from gui.components.entity_list import initials, is_dark, name_hue, placeholder_color
from utils.name_matching import NameEntry, suggest


class NameCompleter(QObject):
    """Attached to a QTextEdit; the edit forwards its key presses, paint events and focus loss."""

    def __init__(self, edit: QTextEdit, entries: Callable[[], List[NameEntry]]):
        super().__init__(edit)
        self.edit = edit
        self._entries = entries
        self.enabled = True
        self.typed = 0                    # characters left of the cursor that the suggestion replaces
        self.matches: List[NameEntry] = []
        self._dismissed = False           # Esc was pressed: stay quiet until the text changes again
        self.popup = QListWidget(edit)
        self.popup.setWindowFlags(Qt.WindowType.ToolTip)
        self.popup.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.popup.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.popup.itemClicked.connect(lambda _item: self.accept())

    # --- state ---------------------------------------------------------------------------------------

    @property
    def active(self) -> bool:
        return bool(self.matches) and self.enabled

    def current(self) -> Optional[NameEntry]:
        if not self.matches:
            return None
        row = self.popup.currentRow() if self.popup.isVisible() else 0
        return self.matches[max(0, min(row, len(self.matches) - 1))]

    def clear(self) -> None:
        self.typed, self.matches = 0, []
        self.popup.hide()
        self.edit.viewport().update()

    def update_suggestions(self) -> None:
        """Look at the text left of the cursor and show what fits (called after every typed character)."""
        cursor = self.edit.textCursor()
        if not self.enabled or self._dismissed or cursor.hasSelection() or cursor.charFormat().isAnchor():
            self.clear()
            return
        before = cursor.block().text()[:cursor.positionInBlock()]
        self.typed, self.matches = suggest(before, self._entries())
        if not self.matches:
            self.clear()
            return
        if len(self.matches) > 1:
            self._show_popup()
        else:
            self.popup.hide()
        self.edit.viewport().update()

    # --- keys ----------------------------------------------------------------------------------------

    def handle_key(self, event) -> bool:
        """Consume the keys that drive a visible suggestion; True when the event was used."""
        if not self.active:
            return False
        key, modifiers = event.key(), event.modifiers()
        if modifiers not in (Qt.KeyboardModifier.NoModifier, Qt.KeyboardModifier.KeypadModifier):
            return False
        if key == Qt.Key.Key_Tab:
            self.accept()
            return True
        if key == Qt.Key.Key_Escape:
            self._dismissed = True
            self.clear()
            return True
        if self.popup.isVisible():
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.accept()
                return True
            if key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                step = 1 if key == Qt.Key.Key_Down else -1
                self.popup.setCurrentRow((self.popup.currentRow() + step) % self.popup.count())
                self.edit.viewport().update()
                return True
        return False

    def after_key(self, event) -> None:
        """Re-read the text after a key was handled by the editor."""
        key = event.key()
        if key in (Qt.Key.Key_Shift, Qt.Key.Key_Control, Qt.Key.Key_Alt, Qt.Key.Key_Meta, Qt.Key.Key_CapsLock):
            return
        if event.text() or key in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
            self._dismissed = False
        self.update_suggestions()

    # --- accepting -----------------------------------------------------------------------------------

    def accept(self) -> None:
        entry = self.current()
        if entry is None:
            return
        typed = self.typed
        cursor = self.edit.textCursor()
        base = QTextCharFormat(cursor.charFormat())
        cursor.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.KeepAnchor, typed)
        link = QTextCharFormat(base)
        link.setAnchor(True)
        link.setAnchorHref(entry.url)
        link.setForeground(self.edit.palette().link())
        link.setFontUnderline(True)
        cursor.insertText(entry.title, link)
        plain = QTextCharFormat(base)
        plain.setAnchor(False)
        plain.setAnchorHref("")
        plain.setFontUnderline(False)
        plain.clearForeground()
        self.edit.setTextCursor(cursor)
        self.edit.setCurrentCharFormat(plain)     # what is typed next is not part of the link
        self.clear()

    # --- drawing -------------------------------------------------------------------------------------

    def paint_ghost(self) -> None:
        """Draw the rest of the best name in grey after the cursor."""
        entry = self.current()
        if entry is None or not self.active:
            return
        rest = entry.title[self.typed:] if entry.folded.startswith(self._typed_text_folded()) else ''
        rect = self.edit.cursorRect()
        painter = QPainter(self.edit.viewport())
        font = self.edit.textCursor().charFormat().font() if self.edit.textCursor().charFormat().hasProperty(
            QTextCharFormat.Property.FontFamilies) else self.edit.font()
        painter.setFont(font)
        colour = QColor(self.edit.palette().text().color())
        colour.setAlpha(110)
        painter.setPen(colour)
        label = rest if rest else ""
        hint = "  ↹ Tab" if not label else "  ↹"
        x = rect.right() + 1
        y = rect.top() + painter.fontMetrics().ascent() + (rect.height() - painter.fontMetrics().height()) // 2
        if x < self.edit.viewport().width() - 20:
            painter.drawText(x, y, label + hint)
        painter.end()

    def _typed_text_folded(self) -> str:
        from utils.natural_sort import fold_text
        cursor = self.edit.textCursor()
        before = cursor.block().text()[:cursor.positionInBlock()]
        return fold_text(before[-self.typed:]) if self.typed else ''

    def _show_popup(self) -> None:
        dark = is_dark(self.edit.palette())
        label_for = get_registry().label
        self.popup.blockSignals(True)
        self.popup.clear()
        for entry in self.matches:
            item = QListWidgetItem(QIcon(_badge(entry, dark)), f"{entry.title}   ·   {label_for(entry.entity_type)}")
            self.popup.addItem(item)
        self.popup.setCurrentRow(0)
        self.popup.blockSignals(False)
        rect = self.edit.cursorRect()
        spot = self.edit.viewport().mapToGlobal(rect.bottomLeft())
        row_height = self.popup.sizeHintForRow(0) if self.popup.count() else 24
        self.popup.setFixedSize(max(260, self.popup.sizeHintForColumn(0) + 24),
                                row_height * min(len(self.matches), 8) + 6)
        self.popup.move(spot)
        self.popup.show()


def _badge(entry: NameEntry, dark: bool, size: int = 22) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(placeholder_color(name_hue(entry.title), dark))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(0, 0, size, size, 6, 6)
    painter.setPen(QColor('white'))
    font = painter.font()
    font.setPixelSize(int(size * 0.42))
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, initials(entry.title))
    painter.end()
    return pixmap
