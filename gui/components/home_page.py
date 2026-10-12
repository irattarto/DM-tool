"""Home page of a campaign: counts per type, recent activity, factions and recent sessions."""

from typing import List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

from gui.components.entity_list import ThumbnailLoader, name_color, name_hue, is_dark, picture_pixmap

TILE_WIDTH = 170


class _ClickFrame(QFrame):
    """A frame that can be clicked, with a hover highlight."""

    clicked = pyqtSignal()

    def __init__(self, name: str, parent=None):
        super().__init__(parent)
        self.setObjectName(name)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class HomePage(QScrollArea):
    """Design "B": a dashboard of what is in the campaign. Everything here comes from data the app already keeps."""

    go_to = pyqtSignal(str)        # key of a sidebar page
    open_entry = pyqtSignal(dict)  # a document
    health_requested = pyqtSignal()   # the "Needs attention" card was clicked

    def __init__(self, loader: ThumbnailLoader, parent=None):
        super().__init__(parent)
        self.loader = loader
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._tiles: List[QWidget] = []
        self._tile_grid: Optional[QGridLayout] = None
        self._layout = QVBoxLayout()

    # --- building ----------------------------------------------------------------------------------

    def show_data(self, data: dict) -> None:
        """data: {'name', 'status', 'tiles', 'recent', 'factions', 'sessions'} (see ShellMixin._refresh_home)."""
        # A fresh page every time; it is handed to the scroll area at the end, when everything is on it,
        # so the scroll area sees its real minimum size
        root = QWidget()
        root.setObjectName("homeRoot")
        self._layout = QVBoxLayout(root)
        self._layout.setContentsMargins(24, 20, 24, 20)
        self._layout.setSpacing(16)
        self._tiles = []

        title = QLabel(data.get('name') or "No campaign")
        title_font = QFont(self.font())
        title_font.setPointSizeF(title_font.pointSizeF() * 1.9)
        title_font.setWeight(QFont.Weight.DemiBold)
        title.setFont(title_font)
        self._layout.addWidget(title)
        status = QLabel(data.get('status', ''))
        status.setEnabled(False)
        self._layout.addWidget(status)

        tile_host = QWidget()
        self._tile_grid = QGridLayout(tile_host)
        self._tile_grid.setContentsMargins(0, 0, 0, 0)
        self._tile_grid.setSpacing(10)
        for tile in data.get('tiles', []):
            self._tiles.append(self._make_tile(tile))
        self._layout.addWidget(tile_host)
        self._arrange_tiles()

        columns = QHBoxLayout()
        columns.setSpacing(14)
        columns.addWidget(self._card("Recent activity", [self._recent_row(r) for r in data.get('recent', [])],
                                     "Nothing has been written yet."), 3)
        side = QVBoxLayout()
        side.setSpacing(14)
        faction_rows = [self._faction_row(f) for f in data.get('factions', [])]
        if faction_rows:
            side.addWidget(self._card("Factions", faction_rows, ""))
        side.addWidget(self._card("Recent sessions", [self._session_row(s) for s in data.get('sessions', [])],
                                  "No sessions yet."))
        attention = [self._text_row(line) for line in data.get('attention', [])]
        if attention:
            side.addWidget(self._card("Needs attention", attention, ""))
        unused = [self._unused_row(e) for e in data.get('unused', [])]
        if unused:
            side.addWidget(self._card("Not used for a while", unused, ""))
        side.addStretch(1)
        columns.addLayout(side, 2)
        self._layout.addLayout(columns)
        self._layout.addStretch(1)
        self.setWidget(root)  # removes the previous page with everything on it
        self._arrange_tiles()

    def _card(self, heading: str, rows: List[QWidget], empty_text: str) -> QFrame:
        card = QFrame()
        card.setObjectName("homeCard")
        card.setStyleSheet("#homeCard { border: 1px solid palette(mid); border-radius: 8px; background: palette(base); }")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(2)
        caption = QLabel(heading.upper())
        caption.setEnabled(False)
        layout.addWidget(caption)
        for row in rows:
            layout.addWidget(row)
        if not rows and empty_text:
            empty = QLabel(empty_text)
            empty.setEnabled(False)
            layout.addWidget(empty)
        return card

    def _row_frame(self, height: int) -> _ClickFrame:
        row = _ClickFrame("homeRow")
        row.setStyleSheet("#homeRow { border-radius: 6px; } #homeRow:hover { background: palette(alternate-base); }")
        row.setMinimumHeight(height)  # rows keep their height however little room the page has
        row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        return row

    def _picture_label(self, entry: dict, size: int, radius: float) -> QLabel:
        label = QLabel()
        label.setPixmap(picture_pixmap(self.loader, entry.get('image'), entry['doc']['title'], entry.get('hue', 0),
                                       size, radius, self.palette(), self.font()))
        return label

    def _recent_row(self, entry: dict) -> QWidget:
        row = self._row_frame(48)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(10)
        layout.addWidget(self._picture_label(entry, 36, 7))
        text = QVBoxLayout()
        text.setSpacing(0)
        name = QLabel(entry['doc']['title'])
        bold = QFont(self.font())
        bold.setWeight(QFont.Weight.DemiBold)
        name.setFont(bold)
        text.addWidget(name)
        detail = QLabel(f"{entry['type_label']} · edited {entry['when']}")
        detail.setEnabled(False)
        text.addWidget(detail)
        layout.addLayout(text, 1)
        row.clicked.connect(lambda doc=entry['doc']: self.open_entry.emit(doc))
        return row

    def _faction_row(self, entry: dict) -> QWidget:
        row = self._row_frame(30)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(4, 4, 4, 4)
        name = QLabel(entry['doc']['title'])
        color = name_color(name_hue(entry['doc']['title']), is_dark(self.palette()))
        name.setStyleSheet(f"color: {color.name()}; font-weight: 600;")
        layout.addWidget(name, 1)
        count = QLabel(entry['label'])
        count.setEnabled(False)
        layout.addWidget(count)
        row.clicked.connect(lambda doc=entry['doc']: self.open_entry.emit(doc))
        return row

    def _session_row(self, entry: dict) -> QWidget:
        row = self._row_frame(30)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(QLabel(entry['title']), 1)
        when = QLabel(entry['date'])
        when.setEnabled(False)
        layout.addWidget(when)
        row.clicked.connect(lambda: self.go_to.emit('sessions'))
        return row

    def _text_row(self, text: str) -> QWidget:
        row = self._row_frame(28)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(QLabel(text), 1)
        row.clicked.connect(self.health_requested.emit)
        return row

    def _unused_row(self, entry: dict) -> QWidget:
        row = self._row_frame(30)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(QLabel(entry['doc']['title']), 1)
        seen = QLabel(entry['label'])
        seen.setEnabled(False)
        layout.addWidget(seen)
        row.clicked.connect(lambda doc=entry['doc']: self.open_entry.emit(doc))
        return row

    def _make_tile(self, tile: dict) -> QWidget:
        frame = _ClickFrame("homeTile")
        frame.setStyleSheet("#homeTile { border: 1px solid palette(mid); border-radius: 10px; background: palette(base); }"
                            "#homeTile:hover { border-color: palette(highlight); }")
        frame.setFixedWidth(TILE_WIDTH)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(0)
        number = QLabel(str(tile['count']))
        number_font = QFont(self.font())
        number_font.setPointSizeF(number_font.pointSizeF() * 2.0)
        number_font.setWeight(QFont.Weight.DemiBold)
        number.setFont(number_font)
        layout.addWidget(number)
        label = QLabel(tile['label'])
        label.setEnabled(False)
        layout.addWidget(label)
        pictures = QHBoxLayout()
        pictures.setContentsMargins(0, 6, 0, 0)
        pictures.setSpacing(4)
        for entry in tile.get('pictures', []):
            pictures.addWidget(self._picture_label(entry, 26, 13))
        pictures.addStretch(1)
        layout.addLayout(pictures)
        frame.clicked.connect(lambda key=tile['key']: self.go_to.emit(key))
        return frame

    def _arrange_tiles(self) -> None:
        """Lay the tiles out in as many columns as fit."""
        if self._tile_grid is None:
            return
        while self._tile_grid.count():
            self._tile_grid.takeAt(0)
        columns = max(1, (self.viewport().width() - 48 + 10) // (TILE_WIDTH + 10))
        for index, tile in enumerate(self._tiles):
            self._tile_grid.addWidget(tile, index // columns, index % columns)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._arrange_tiles()
