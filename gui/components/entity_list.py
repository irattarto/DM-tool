"""Entity list pieces: painted rows with thumbnails, faction colours and the preview panel."""

import re
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, Optional

from PyQt6.QtCore import QEvent, QObject, QRect, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QIcon, QImageReader, QPainter, QPainterPath, QPalette, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QStyle,
    QStyledItemDelegate, QStyleOptionViewItem, QVBoxLayout,
)

from config.paths import resolve_image_path

# Item roles: the document dict stays in UserRole (as before); how a row is drawn lives next to it.
ROLE_DOC = Qt.ItemDataRole.UserRole
ROLE_ROW = Qt.ItemDataRole.UserRole + 1

ROW_HEIGHT = 56
GROUP_HEIGHT = 30
THUMB_SIZE = 44
PREVIEW_WIDTH = 260
_THUMB_PIXELS = 96          # decoded size of a row thumbnail (sharp on high-DPI screens)
_PREVIEW_PIXELS = 480       # decoded size of the preview picture
_CACHE_LIMIT = 600


def pin_rect(row_rect: QRect) -> QRect:
    """Where the pin star of a row is drawn and clicked."""
    return QRect(row_rect.right() - 34, row_rect.center().y() - 12, 24, 24)


def name_hue(name: str) -> int:
    """A stable hue (0-359) for a name, so a faction always keeps the same colour."""
    value = 7
    for char in name:
        value = (value * 31 + ord(char)) % 360
    return value


def is_dark(palette: QPalette) -> bool:
    return palette.color(QPalette.ColorRole.Window).lightness() < 128


def name_color(hue: int, dark: bool) -> QColor:
    """Text colour for a faction name: readable on both light and dark backgrounds."""
    return QColor.fromHsl(hue, 140, 173 if dark else 92)


def placeholder_color(hue: int, dark: bool) -> QColor:
    """Background of the placeholder shown when an entity has no image."""
    return QColor.fromHsl(hue, 97, 107 if dark else 112)


def initials(title: str) -> str:
    letters = [word[0] for word in title.split() if word and word[0].isalpha() and word[0].isupper()]
    return ''.join(letters[:2]) or (title[:1].upper() if title else '?')


def excerpt(content: str, limit: int = 200) -> str:
    """The first words of a document's text without Markdown marks, for the preview."""
    text = re.sub(r'^\s*(?:name|race|faction)\s*:.*$', '', content or '', flags=re.MULTILINE | re.IGNORECASE)
    text = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', text)
    text = re.sub(r'^\s*#+\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'[*_`>|]+', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(' ', 1)[0].rstrip(' ,.;:') + '…'


class ThumbnailLoader:
    """Loads small square pictures for the lists and keeps recent ones in memory.

    Uses the small cached thumbnail of the image when it exists and falls back to the
    original file, so a long list never decodes full-size pictures.
    """

    def __init__(self, image_service):
        self.image_service = image_service
        self._cache: "OrderedDict[tuple, Optional[QPixmap]]" = OrderedDict()

    def pixmap(self, image: Optional[Dict[str, Any]], pixels: int = _THUMB_PIXELS) -> Optional[QPixmap]:
        """A square crop (kept towards the top, where faces are) of an image record's picture."""
        if not image:
            return None
        key = (image.get('id'), pixels)
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        pixmap = self._load(image, pixels)
        self._cache[key] = pixmap
        while len(self._cache) > _CACHE_LIMIT:
            self._cache.popitem(last=False)
        return pixmap

    def clear(self) -> None:
        self._cache.clear()

    def _source_path(self, image: Dict[str, Any], pixels: int) -> Optional[str]:
        if pixels <= 200 and image.get('filename'):
            cached = self.image_service.get_thumbnail_path(Path(image['filename']).stem)
            if cached:
                return str(cached)
        path = resolve_image_path(image)
        return path if path and Path(path).exists() else None

    def _load(self, image: Dict[str, Any], pixels: int) -> Optional[QPixmap]:
        path = self._source_path(image, pixels)
        if not path:
            return None
        reader = QImageReader(path)
        reader.setAutoTransform(True)
        source = reader.size()
        if not source.isValid() or min(source.width(), source.height()) <= 0:
            return None
        scale = pixels / min(source.width(), source.height())
        reader.setScaledSize(QSize(max(pixels, round(source.width() * scale)),
                                   max(pixels, round(source.height() * scale))))
        picture = reader.read()
        if picture.isNull():
            return None
        left = max(0, (picture.width() - pixels) // 2)
        top = max(0, int((picture.height() - pixels) * 0.2))
        return QPixmap.fromImage(picture.copy(left, top, min(pixels, picture.width()), min(pixels, picture.height())))


def draw_picture(painter: QPainter, rect: QRect, radius: float, pixmap: Optional[QPixmap],
                 title: str, hue: int, dark: bool, font: QFont) -> None:
    """Draw a rounded picture, or initials on the faction colour when there is no image."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    path = QPainterPath()
    path.addRoundedRect(QRectF(rect), radius, radius)
    painter.setClipPath(path)
    if pixmap is not None and not pixmap.isNull():
        painter.drawPixmap(rect, pixmap)
    else:
        painter.fillRect(rect, placeholder_color(hue, dark))
        painter.setPen(QColor('white'))
        initials_font = QFont(font)
        initials_font.setPointSizeF(max(8.0, rect.height() * 0.3))
        initials_font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(initials_font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, initials(title))
    painter.restore()


def picture_pixmap(loader: "ThumbnailLoader", image: Optional[Dict[str, Any]], title: str, hue: int, size: int,
                   radius: float, palette: QPalette, font: QFont) -> QPixmap:
    """A rounded picture (or initials on the faction colour) as a sharp pixmap for labels and buttons."""
    ratio = 2
    pixmap = QPixmap(size * ratio, size * ratio)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    draw_picture(painter, QRect(0, 0, size * ratio, size * ratio), radius * ratio, loader.pixmap(image), title, hue,
                 is_dark(palette), font)
    painter.end()
    pixmap.setDevicePixelRatio(ratio)
    return pixmap


class EntityRowDelegate(QStyledItemDelegate):
    """Paints a document row: thumbnail, name, race · faction and module; also group headers."""

    def __init__(self, loader: ThumbnailLoader, parent=None):
        super().__init__(parent)
        self.loader = loader

    def sizeHint(self, option, index) -> QSize:
        info = index.data(ROLE_ROW)
        height = GROUP_HEIGHT if info and info.get('is_group') else ROW_HEIGHT
        return QSize(option.rect.width(), height)

    def paint(self, painter: QPainter, option, index) -> None:
        info = index.data(ROLE_ROW)
        if not info:
            super().paint(painter, option, index)
            return

        # Background (alternating rows, hover, selection) comes from the application style
        styled = QStyleOptionViewItem(option)
        self.initStyleOption(styled, index)
        styled.text = ''
        styled.icon = QIcon()
        styled.features &= ~QStyleOptionViewItem.ViewItemFeature.HasDisplay
        styled.features &= ~QStyleOptionViewItem.ViewItemFeature.HasDecoration
        widget = option.widget
        style = widget.style() if widget else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, styled, painter, widget)

        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        palette = option.palette
        text_role = QPalette.ColorRole.HighlightedText if selected else QPalette.ColorRole.Text
        primary = palette.color(QPalette.ColorGroup.Active, text_role)
        secondary = QColor(primary)
        secondary.setAlpha(165)
        dark = is_dark(palette)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = option.rect
        if info.get('is_group'):
            self._paint_group(painter, option, info, primary, secondary)
        else:
            self._paint_row(painter, option, index, info, primary, secondary, dark, rect, selected)
        painter.restore()

    def _paint_group(self, painter, option, info, primary, secondary) -> None:
        rect = option.rect.adjusted(12, 0, -12, 0)
        font = QFont(option.font)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.setPen(primary)
        arrow = '▾' if option.state & QStyle.StateFlag.State_Open else '▸'
        label = f"{arrow}  {info['title']}"
        painter.drawText(rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, label)
        label_width = QFontMetrics(font).horizontalAdvance(label)
        painter.setFont(option.font)
        painter.setPen(secondary)
        painter.drawText(rect.adjusted(label_width + 8, 0, 0, 0),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, str(info['count']))

    def _paint_row(self, painter, option, index, info, primary, secondary, dark, rect, selected) -> None:
        document = index.data(ROLE_DOC) or {}
        title = document.get('title', '')
        hue = info.get('hue', 0)

        thumb_rect = QRect(rect.left() + 12, rect.top() + (rect.height() - THUMB_SIZE) // 2, THUMB_SIZE, THUMB_SIZE)
        draw_picture(painter, thumb_rect, 7, self.loader.pixmap(info.get('image')), title, hue, dark, option.font)

        text_left = thumb_rect.right() + 14
        right_edge = rect.right() - 42  # the pin star sits at the far right

        # Pin star: shown while hovering, and always for pinned entries
        pinned = bool(info.get('pinned'))
        if pinned or option.state & QStyle.StateFlag.State_MouseOver:
            star_font = QFont(option.font)
            star_font.setPointSizeF(option.font.pointSizeF() * 1.35)
            painter.setFont(star_font)
            accent = option.palette.color(QPalette.ColorGroup.Active, QPalette.ColorRole.Highlight)
            painter.setPen(primary if selected else (accent if pinned else secondary))
            painter.drawText(pin_rect(rect), Qt.AlignmentFlag.AlignCenter, '★' if pinned else '☆')

        # Module on the right: small label above its name (nothing when the entry has no module)
        module = info.get('module') or ''
        module_left = right_edge
        if module:
            small = QFont(option.font)
            small.setPointSizeF(max(7.0, option.font.pointSizeF() * 0.78))
            module_width = min(int(rect.width() * 0.34), QFontMetrics(option.font).horizontalAdvance(module) + 4)
            module_width = max(module_width, 60)
            module_rect = QRect(right_edge - module_width, rect.top() + 9, module_width, rect.height() - 18)
            module_left = module_rect.left()
            painter.setFont(small)
            painter.setPen(secondary)
            painter.drawText(module_rect, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight, 'MODULE')
            painter.setFont(option.font)
            painter.setPen(primary if selected else secondary)
            painter.drawText(module_rect, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight,
                             QFontMetrics(option.font).elidedText(module, Qt.TextElideMode.ElideRight, module_width))

        text_width = max(40, module_left - 14 - text_left)
        name_font = QFont(option.font)
        name_font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(name_font)
        painter.setPen(primary)
        name_rect = QRect(text_left, rect.top() + 8, text_width, 20)
        painter.drawText(name_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         QFontMetrics(name_font).elidedText(title, Qt.TextElideMode.ElideRight, text_width))

        # Second line: race · faction (the faction name in its own colour)
        sub_rect = QRect(text_left, rect.top() + 29, text_width, 18)
        painter.setFont(option.font)
        metrics = QFontMetrics(option.font)
        x = sub_rect.left()
        race = info.get('race') or ''
        faction = info.get('faction') or ''
        if race:
            race_text = metrics.elidedText(race, Qt.TextElideMode.ElideRight, sub_rect.width())
            painter.setPen(secondary)
            painter.drawText(QRect(x, sub_rect.top(), sub_rect.width(), sub_rect.height()),
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, race_text)
            x += metrics.horizontalAdvance(race_text)
        if faction:
            if race:
                painter.setPen(secondary)
                painter.drawText(QRect(x, sub_rect.top(), 20, sub_rect.height()),
                                 Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, ' · ')
                x += metrics.horizontalAdvance(' · ')
            remaining = sub_rect.right() - x
            if remaining > 20:
                faction_font = QFont(option.font)
                faction_font.setWeight(QFont.Weight.Medium)
                painter.setFont(faction_font)
                painter.setPen(primary if selected else name_color(name_hue(faction), dark))
                painter.drawText(QRect(x, sub_rect.top(), remaining, sub_rect.height()),
                                 Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                                 QFontMetrics(faction_font).elidedText(faction, Qt.TextElideMode.ElideRight, remaining))


class RowHoverFilter(QObject):
    """Tells when the mouse leaves a list, so the preview can go back to the selected row."""

    left = pyqtSignal()

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.Type.Leave:
            self.left.emit()
        return False


class PinClickFilter(QObject):
    """Turns a click on a row's pin star into a signal, so the click does not also select the row."""

    pin_clicked = pyqtSignal(object)  # the clicked QTreeWidgetItem

    def __init__(self, tree):
        super().__init__(tree)
        self.tree = tree

    def eventFilter(self, obj, event) -> bool:
        press = event.type() == QEvent.Type.MouseButtonPress
        if (press or event.type() == QEvent.Type.MouseButtonDblClick) and event.button() == Qt.MouseButton.LeftButton:
            point = event.position().toPoint()
            item = self.tree.itemAt(point)
            if item is not None and item.data(0, ROLE_DOC) and pin_rect(self.tree.visualItemRect(item)).contains(point):
                if press:
                    self.pin_clicked.emit(item)
                return True  # a quick second click on the star must not open the entry either
        return False


class _PictureLabel(QLabel):
    """Square picture area of the preview: image, or initials on the faction colour."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._pixmap: Optional[QPixmap] = None
        self._title = ''
        self._hue = 0

    def set_content(self, pixmap: Optional[QPixmap], title: str, hue: int) -> None:
        self._pixmap, self._title, self._hue = pixmap, title, hue
        self.update()

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return width

    def sizeHint(self) -> QSize:
        return QSize(PREVIEW_WIDTH - 24, PREVIEW_WIDTH - 24)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        side = min(self.width(), self.height())
        rect = QRect(0, 0, side, side)
        draw_picture(painter, rect, 9, self._pixmap, self._title, self._hue, is_dark(self.palette()), self.font())


class EntityPreviewPanel(QFrame):
    """Side panel with the large picture, the details and a short text excerpt of a document."""

    open_requested = pyqtSignal(dict)
    discord_requested = pyqtSignal(dict)
    pin_requested = pyqtSignal(dict)

    def __init__(self, loader: ThumbnailLoader, with_discord: bool = False, parent=None):
        super().__init__(parent)
        self.loader = loader
        self._document: Optional[dict] = None
        self.setObjectName("entityPreview")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setMinimumWidth(PREVIEW_WIDTH)
        self.setMaximumWidth(PREVIEW_WIDTH + 60)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.hint = QLabel("Select or hover a row to preview it here.")
        self.hint.setWordWrap(True)
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.hint)

        self.picture = _PictureLabel()
        layout.addWidget(self.picture)

        self.title_label = QLabel()
        title_font = QFont(self.font())
        title_font.setPointSizeF(title_font.pointSizeF() * 1.25)
        title_font.setWeight(QFont.Weight.DemiBold)
        self.title_label.setFont(title_font)
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        self.details = QGridLayout()
        self.details.setHorizontalSpacing(12)
        self.details.setVerticalSpacing(3)
        self.details.setColumnStretch(1, 1)
        layout.addLayout(self.details)

        self.excerpt_label = QLabel()
        self.excerpt_label.setWordWrap(True)
        italic = QFont(self.font())
        italic.setItalic(True)
        self.excerpt_label.setFont(italic)
        layout.addWidget(self.excerpt_label)

        layout.addStretch(1)

        buttons = QHBoxLayout()
        self.open_button = QPushButton("Open")
        self.open_button.clicked.connect(lambda: self._document and self.open_requested.emit(self._document))
        buttons.addWidget(self.open_button)
        self.pin_button = QPushButton("Pin for tonight")
        self.pin_button.clicked.connect(lambda: self._document and self.pin_requested.emit(self._document))
        buttons.addWidget(self.pin_button)
        layout.addLayout(buttons)
        self.discord_button = None
        if with_discord:
            self.discord_button = QPushButton("Send to Discord...")
            self.discord_button.clicked.connect(lambda: self._document and self.discord_requested.emit(self._document))
            layout.addWidget(self.discord_button)
        self.show_empty()

    def show_empty(self) -> None:
        self._document = None
        self._set_content_visible(False)

    def show_document(self, document: dict, info: dict, rows) -> None:
        """Show a document. `rows` are the (label, value, colour or None) detail lines."""
        self._document = document
        self._set_content_visible(True)
        self.pin_button.setText("Unpin" if info.get('pinned') else "Pin for tonight")
        title = document.get('title', '')
        self.picture.set_content(self.loader.pixmap(info.get('image'), _PREVIEW_PIXELS), title, info.get('hue', 0))
        self.title_label.setText(title)

        while self.details.count():
            item = self.details.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)  # gone at once, deleted when Qt gets to it
                widget.deleteLater()
        for row, (label, value, color) in enumerate(rows):
            key = QLabel(label)
            key.setEnabled(False)
            val = QLabel(value or '–')
            val.setWordWrap(True)
            if color is not None and value:
                val.setStyleSheet(f"color: {color.name()}; font-weight: 600;")
            self.details.addWidget(key, row, 0, Qt.AlignmentFlag.AlignTop)
            self.details.addWidget(val, row, 1)

        text = excerpt(document.get('content', ''))
        self.excerpt_label.setText(f"“{text}”" if text else '')
        self.excerpt_label.setVisible(bool(text))

    def _set_content_visible(self, visible: bool) -> None:
        self.hint.setVisible(not visible)
        for widget in (self.picture, self.title_label, self.open_button, self.pin_button, self.excerpt_label):
            widget.setVisible(visible)
        if self.discord_button is not None:
            self.discord_button.setVisible(visible)
        if not visible:
            while self.details.count():
                item = self.details.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.setParent(None)
                    widget.deleteLater()
