"""Ctrl+K palette: search every entry of the campaign and run the app's actions."""

from typing import Callable, Dict, List, Sequence, Tuple

from PyQt6.QtCore import QEvent, QRect, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPalette
from PyQt6.QtWidgets import (
    QAbstractItemView, QDialog, QFrame, QLineEdit, QListWidget, QListWidgetItem, QStyle, QStyledItemDelegate,
    QVBoxLayout,
)

from gui.components.entity_list import ThumbnailLoader, draw_picture, is_dark, name_hue

ROLE_RESULT = Qt.ItemDataRole.UserRole
MAX_ENTITY_RESULTS = 8
RECENT_ENTRIES = 5
ROW_HEIGHT = 44
HEADER_HEIGHT = 26
PALETTE_WIDTH = 580


class _ResultDelegate(QStyledItemDelegate):
    def __init__(self, loader: ThumbnailLoader, parent=None):
        super().__init__(parent)
        self.loader = loader

    def sizeHint(self, option, index) -> QSize:
        kind = (index.data(ROLE_RESULT) or {}).get('kind')
        return QSize(option.rect.width(), HEADER_HEIGHT if kind == 'header' else ROW_HEIGHT)

    def paint(self, painter: QPainter, option, index) -> None:
        result = index.data(ROLE_RESULT) or {}
        palette = option.palette
        text = palette.color(QPalette.ColorGroup.Active, QPalette.ColorRole.Text)
        muted = QColor(text)
        muted.setAlpha(150)
        rect = option.rect
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if result.get('kind') == 'header':
            font = QFont(option.font)
            font.setPointSizeF(max(7.0, option.font.pointSizeF() * 0.8))
            font.setWeight(QFont.Weight.DemiBold)
            painter.setFont(font)
            painter.setPen(muted)
            painter.drawText(rect.adjusted(16, 6, -16, 0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                             result['title'].upper())
            painter.restore()
            return

        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        if selected:
            fill = QColor(palette.color(QPalette.ColorGroup.Active, QPalette.ColorRole.Highlight))
            fill.setAlpha(60)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fill)
            painter.drawRoundedRect(rect.adjusted(6, 1, -6, -1), 6, 6)

        left = rect.left() + 16
        if result.get('kind') == 'entity':
            thumb = QRect(left, rect.top() + (rect.height() - 32) // 2, 32, 32)
            document = result['doc']
            draw_picture(painter, thumb, 6, self.loader.pixmap(result.get('image')), document.get('title', ''),
                         result.get('hue', 0), is_dark(palette), option.font)
            left = thumb.right() + 12

        title_font = QFont(option.font)
        title_font.setWeight(QFont.Weight.DemiBold)
        right = rect.right() - 16
        hint = result.get('hint', '')
        hint_width = 0
        if hint or selected:
            hint_text = hint or 'Enter'
            hint_width = QFontMetrics(option.font).horizontalAdvance(hint_text) + 14
            hint_rect = QRect(right - hint_width, rect.center().y() - 10, hint_width, 20)
            painter.setPen(muted)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(hint_rect, 4, 4)
            painter.setFont(option.font)
            painter.drawText(hint_rect, Qt.AlignmentFlag.AlignCenter, hint_text)

        text_width = max(40, right - hint_width - 10 - left)
        subtitle = result.get('subtitle', '')
        painter.setFont(title_font)
        painter.setPen(text)
        title = QFontMetrics(title_font).elidedText(result['title'], Qt.TextElideMode.ElideRight, text_width)
        if subtitle:
            painter.drawText(QRect(left, rect.top() + 5, text_width, 18), Qt.AlignmentFlag.AlignVCenter, title)
            painter.setFont(option.font)
            painter.setPen(muted)
            painter.drawText(QRect(left, rect.top() + 23, text_width, 16), Qt.AlignmentFlag.AlignVCenter,
                             QFontMetrics(option.font).elidedText(subtitle, Qt.TextElideMode.ElideRight, text_width))
        else:
            painter.drawText(QRect(left, rect.top(), text_width, rect.height()), Qt.AlignmentFlag.AlignVCenter, title)
        painter.restore()


class CommandPalette(QDialog):
    """Type to find an entry or an action; Up/Down to choose, Enter to open, Esc to close."""

    entity_chosen = pyqtSignal(dict)

    def __init__(self, parent, documents: Sequence[dict], type_labels: Dict[str, str], loader: ThumbnailLoader,
                 image_lookup: Callable[[List[int]], Dict[int, dict]],
                 actions: Sequence[Tuple[str, str, Callable[[], None]]]):
        """documents: the campaign's entries; actions: (title, shortcut hint, callback)."""
        super().__init__(parent, Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("commandPalette")
        self.setModal(True)
        self.setFixedWidth(PALETTE_WIDTH)
        self._documents = list(documents)
        self._type_labels = type_labels
        self._loader = loader
        self._image_lookup = image_lookup
        self._actions = list(actions)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search entries and actions…")
        self.search_edit.setMinimumHeight(40)
        self.search_edit.setFrame(False)
        self.search_edit.textChanged.connect(self._refresh)
        self.search_edit.installEventFilter(self)
        layout.addWidget(self.search_edit)
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(divider)

        self.results = QListWidget()
        self.results.setFrameShape(QFrame.Shape.NoFrame)
        self.results.setItemDelegate(_ResultDelegate(loader, self.results))
        self.results.setMouseTracking(True)
        self.results.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.results.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.results.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.results.itemClicked.connect(self._activate)
        layout.addWidget(self.results)
        self.setStyleSheet("#commandPalette { border: 1px solid palette(mid); }")
        self.setFixedHeight(HEADER_HEIGHT * 2 + ROW_HEIGHT * 9 + 60)
        self._refresh('')

    # --- results -------------------------------------------------------------------------------------

    def _matches(self, query: str) -> List[dict]:
        needle = query.casefold()
        ranked = []
        for document in self._documents:
            title = document.get('title', '')
            lowered = title.casefold()
            if lowered.startswith(needle):
                rank = 0
            elif needle in lowered:
                rank = 1
            elif needle in (document.get('content') or '').casefold():
                rank = 2
            else:
                continue
            ranked.append((rank, lowered, document))
        ranked.sort(key=lambda entry: (entry[0], entry[1]))
        return [document for _rank, _title, document in ranked[:MAX_ENTITY_RESULTS]]

    def _entity_results(self, documents: List[dict]) -> List[dict]:
        images = self._image_lookup([document['id'] for document in documents])
        results = []
        for document in documents:
            results.append({'kind': 'entity', 'title': document.get('title', ''), 'doc': document,
                            'subtitle': self._type_labels.get(document.get('entity_type', ''), ''),
                            'image': images.get(document['id']),
                            'hue': name_hue(document.get('title', ''))})
        return results

    def _refresh(self, query: str) -> None:
        query = query.strip()
        results: List[dict] = []
        if query:
            entries = self._entity_results(self._matches(query))
            if entries:
                results.append({'kind': 'header', 'title': 'Entries'})
                results.extend(entries)
            actions = [a for a in self._actions if query.casefold() in a[0].casefold()]
        else:
            recent = sorted(self._documents, key=lambda d: d.get('modified_date') or '', reverse=True)[:RECENT_ENTRIES]
            if recent:
                results.append({'kind': 'header', 'title': 'Recently edited'})
                results.extend(self._entity_results(recent))
            actions = self._actions
        if actions:
            results.append({'kind': 'header', 'title': 'Actions'})
            results.extend({'kind': 'action', 'title': title, 'hint': hint, 'callback': callback}
                           for title, hint, callback in actions)

        self.results.clear()
        first_selectable = None
        for result in results:
            item = QListWidgetItem()
            item.setData(ROLE_RESULT, result)
            if result['kind'] == 'header':
                item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.results.addItem(item)
            if first_selectable is None and result['kind'] != 'header':
                first_selectable = item
        if first_selectable is not None:
            self.results.setCurrentItem(first_selectable)
        elif not results:
            empty = QListWidgetItem()
            empty.setData(ROLE_RESULT, {'kind': 'header', 'title': 'No results'})
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            self.results.addItem(empty)

    def result_titles(self) -> List[str]:
        """Titles of the selectable results, top to bottom (used by tests)."""
        titles = []
        for row in range(self.results.count()):
            result = self.results.item(row).data(ROLE_RESULT)
            if result['kind'] != 'header':
                titles.append(result['title'])
        return titles

    # --- keyboard ------------------------------------------------------------------------------------

    def eventFilter(self, obj, event) -> bool:
        if obj is self.search_edit and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                self._move(1 if key == Qt.Key.Key_Down else -1)
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                item = self.results.currentItem()
                if item is not None:
                    self._activate(item)
                return True
        return super().eventFilter(obj, event)

    def _move(self, step: int) -> None:
        row = self.results.currentRow()
        count = self.results.count()
        while 0 <= row + step < count:
            row += step
            if self.results.item(row).data(ROLE_RESULT)['kind'] != 'header':
                self.results.setCurrentRow(row)
                return

    def _activate(self, item: QListWidgetItem) -> None:
        result = item.data(ROLE_RESULT)
        if not result or result['kind'] == 'header':
            return
        self.accept()
        if result['kind'] == 'entity':
            self.entity_chosen.emit(result['doc'])
        else:
            QTimer.singleShot(0, result['callback'])

    def showEvent(self, event) -> None:
        super().showEvent(event)
        parent = self.parentWidget()
        if parent is not None:
            top_left = parent.mapToGlobal(parent.rect().topLeft())
            self.move(top_left.x() + (parent.width() - self.width()) // 2, top_left.y() + 70)
        self.search_edit.setFocus(Qt.FocusReason.OtherFocusReason)
        self.search_edit.deselect()  # typing continues after the text, it does not replace it
