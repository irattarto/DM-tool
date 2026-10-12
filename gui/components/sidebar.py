"""Sidebar navigation: grouped entries, each with a small drawn icon and a count."""

import math
from typing import Dict, List, Optional

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPalette, QPolygonF
from PyQt6.QtWidgets import QAbstractItemView, QFrame, QListWidget, QListWidgetItem, QStyle, QStyledItemDelegate

ROLE_ENTRY = Qt.ItemDataRole.UserRole
SIDEBAR_WIDTH = 190
ITEM_HEIGHT = 32
GROUP_HEIGHT = 30

# Icon shape per entity type; any other type (custom types) gets the rounded square
ICON_FOR_TYPE = {
    'home': 'house', 'sessions': 'play', 'templates': 'page', 'character': 'circle', 'npc': 'circle', 'faction': 'shield',
    'location': 'diamond', 'item': 'square', 'event': 'star', 'quest': 'flag', 'setting': 'ring', 'module': 'page',
}


def draw_icon(painter: QPainter, rect: QRectF, shape: str, color: QColor) -> None:
    """A simple geometric icon inside `rect`."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color)
    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
    cx, cy = x + w / 2, y + h / 2
    if shape == 'circle':
        painter.drawEllipse(rect)
    elif shape == 'ring':
        painter.setPen(color)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(rect.adjusted(1, 1, -1, -1))
    elif shape == 'shield':
        path = QPainterPath()
        path.moveTo(x, y + h * 0.12)
        path.lineTo(cx, y)
        path.lineTo(x + w, y + h * 0.12)
        path.lineTo(x + w, y + h * 0.55)
        path.quadTo(x + w, y + h * 0.9, cx, y + h)
        path.quadTo(x, y + h * 0.9, x, y + h * 0.55)
        path.closeSubpath()
        painter.drawPath(path)
    elif shape == 'diamond':
        painter.drawPolygon(QPolygonF([QPointF(cx, y), QPointF(x + w, cy), QPointF(cx, y + h), QPointF(x, cy)]))
    elif shape == 'flag':
        painter.drawPolygon(QPolygonF([QPointF(x + w * 0.15, y), QPointF(x + w * 0.85, y),
                                       QPointF(x + w * 0.85, y + h * 0.7), QPointF(cx, y + h),
                                       QPointF(x + w * 0.15, y + h * 0.7)]))
    elif shape == 'house':
        painter.drawPolygon(QPolygonF([QPointF(cx, y), QPointF(x + w, y + h * 0.45), QPointF(x + w * 0.88, y + h * 0.45),
                                       QPointF(x + w * 0.88, y + h), QPointF(x + w * 0.12, y + h),
                                       QPointF(x + w * 0.12, y + h * 0.45), QPointF(x, y + h * 0.45)]))
    elif shape == 'play':
        painter.drawPolygon(QPolygonF([QPointF(x + w * 0.15, y), QPointF(x + w, cy), QPointF(x + w * 0.15, y + h)]))
    elif shape == 'page':
        painter.drawPolygon(QPolygonF([QPointF(x + w * 0.15, y), QPointF(x + w * 0.65, y), QPointF(x + w * 0.9, y + h * 0.25),
                                       QPointF(x + w * 0.9, y + h), QPointF(x + w * 0.15, y + h)]))
    elif shape == 'star':
        points = []
        for i in range(10):
            radius = w / 2 if i % 2 == 0 else w / 4.2
            angle = -math.pi / 2 + i * math.pi / 5
            points.append(QPointF(cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
        painter.drawPolygon(QPolygonF(points))
    else:  # 'square' and anything else
        painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 3, 3)
    painter.restore()


class _SidebarDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index) -> QSize:
        entry = index.data(ROLE_ENTRY) or {}
        return QSize(option.rect.width(), GROUP_HEIGHT if entry.get('kind') == 'group' else ITEM_HEIGHT)

    def paint(self, painter: QPainter, option, index) -> None:
        entry = index.data(ROLE_ENTRY) or {}
        palette = option.palette
        text = palette.color(QPalette.ColorGroup.Active, QPalette.ColorRole.Text)
        muted = QColor(text)
        muted.setAlpha(150)
        rect = option.rect
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if entry.get('kind') == 'group':
            font = QFont(option.font)
            font.setPointSizeF(max(7.0, option.font.pointSizeF() * 0.8))
            font.setWeight(QFont.Weight.DemiBold)
            font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 110)
            painter.setFont(font)
            painter.setPen(muted)
            painter.drawText(rect.adjusted(14, 8, -8, 0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                             entry.get('label', '').upper())
            painter.restore()
            return

        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        accent = palette.color(QPalette.ColorGroup.Active, QPalette.ColorRole.Highlight)
        box = rect.adjusted(6, 2, -6, -2)
        if selected:
            fill = QColor(accent)
            fill.setAlpha(60)
            painter.setBrush(fill)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(box), 6, 6)
        elif hovered:
            fill = QColor(text)
            fill.setAlpha(22)
            painter.setBrush(fill)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(box), 6, 6)

        foreground = accent if selected else text
        icon_rect = QRectF(box.left() + 9, box.center().y() - 7, 14, 14)
        icon_color = QColor(foreground)
        icon_color.setAlpha(255 if selected else 140)
        draw_icon(painter, icon_rect, entry.get('icon', 'square'), icon_color)

        font = QFont(option.font)
        if selected:
            font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.setPen(foreground)
        count = entry.get('count')
        count_width = 34 if count is not None else 0
        painter.drawText(box.adjusted(32, 0, -count_width - 6, 0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         entry.get('label', ''))
        if count is not None:
            small = QFont(option.font)
            small.setPointSizeF(max(7.0, option.font.pointSizeF() * 0.85))
            painter.setFont(small)
            painter.setPen(muted)
            painter.drawText(box.adjusted(0, 0, -10, 0), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                             str(count))
        painter.restore()


class Sidebar(QListWidget):
    """Grouped navigation list. Emits `view_selected(key)` when an entry is chosen."""

    view_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFixedWidth(SIDEBAR_WIDTH)
        self.setItemDelegate(_SidebarDelegate(self))
        self.setMouseTracking(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setStyleSheet("QListWidget#sidebar { background: palette(alternate-base); border: none; "
                           "border-right: 1px solid palette(mid); outline: none; }"
                           "QListWidget#sidebar::item { border: none; }")
        self.currentItemChanged.connect(self._on_current_changed)
        self._items: Dict[str, QListWidgetItem] = {}

    def set_entries(self, entries: List[dict], current_key: Optional[str] = None) -> None:
        """Replace the entries. Each is {'kind': 'group'|'view', 'key', 'label', 'icon', 'count'}."""
        self.blockSignals(True)
        self.clear()
        self._items = {}
        for entry in entries:
            item = QListWidgetItem()
            item.setData(ROLE_ENTRY, entry)
            if entry['kind'] == 'group':
                item.setFlags(Qt.ItemFlag.NoItemFlags)
            else:
                self._items[entry['key']] = item
            self.addItem(item)
        self.blockSignals(False)
        if current_key:
            self.select_key(current_key)

    def select_key(self, key: str) -> None:
        """Highlight an entry without announcing it."""
        item = self._items.get(key)
        if item is not None:
            self.blockSignals(True)
            self.setCurrentItem(item)
            self.blockSignals(False)
            self.viewport().update()

    def set_count(self, key: str, count: Optional[int]) -> None:
        item = self._items.get(key)
        if item is not None:
            entry = dict(item.data(ROLE_ENTRY))
            entry['count'] = count
            item.setData(ROLE_ENTRY, entry)

    def keys(self) -> List[str]:
        return list(self._items)

    def _on_current_changed(self, current, _previous) -> None:
        entry = current.data(ROLE_ENTRY) if current is not None else None
        if entry and entry.get('kind') == 'view':
            self.view_selected.emit(entry['key'])
