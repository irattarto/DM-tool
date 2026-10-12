"""Strip along the bottom of the window with the entries pinned for tonight's session."""

from typing import List

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QToolButton, QWidget

from gui.components.entity_list import ThumbnailLoader, picture_pixmap

CHIP_PICTURE = 26


class PinTray(QFrame):
    """"Tonight": one chip per pinned entry (picture, first word of the name, ×)."""

    open_requested = pyqtSignal(int)    # document id
    unpin_requested = pyqtSignal(int)   # document id

    def __init__(self, loader: ThumbnailLoader, parent=None):
        super().__init__(parent)
        self.loader = loader
        self.setObjectName("pinTray")
        self.setStyleSheet("#pinTray { background: palette(alternate-base); border-top: 1px solid palette(mid); }")
        outer = QHBoxLayout(self)
        outer.setContentsMargins(12, 5, 12, 5)
        outer.setSpacing(10)
        caption = QLabel("TONIGHT")
        caption.setEnabled(False)
        outer.addWidget(caption)

        self.chips_area = QWidget()
        self.chips_area.setObjectName("chips")
        self.chips_layout = QHBoxLayout(self.chips_area)
        self.chips_layout.setContentsMargins(0, 0, 0, 0)
        self.chips_layout.setSpacing(8)
        scroll = QScrollArea()
        scroll.setWidget(self.chips_area)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFixedHeight(CHIP_PICTURE + 18)
        scroll.setStyleSheet("QScrollArea { background: transparent; } QWidget#chips { background: transparent; }")
        outer.addWidget(scroll, 1)

    def set_pins(self, pins: List[dict]) -> None:
        """pins: [{'id', 'title', 'image', 'hue'}] in the order they were pinned."""
        while self.chips_layout.count():
            item = self.chips_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)  # gone from the strip at once, deleted when Qt gets to it
                widget.deleteLater()
        if not pins:
            hint = QLabel("Pin entries with the star on a row to keep them here.")
            hint.setEnabled(False)
            self.chips_layout.addWidget(hint)
        for pin in pins:
            self.chips_layout.addWidget(self._chip(pin))
        self.chips_layout.addStretch(1)

    def _chip(self, pin: dict) -> QWidget:
        chip = QFrame()
        chip.setObjectName("pinChip")
        chip.setStyleSheet("#pinChip { border: 1px solid palette(mid); border-radius: %dpx; background: palette(base); }"
                           % (CHIP_PICTURE // 2 + 3))
        layout = QHBoxLayout(chip)
        layout.setContentsMargins(3, 2, 4, 2)
        layout.setSpacing(6)

        picture = QLabel()
        picture.setPixmap(picture_pixmap(self.loader, pin.get('image'), pin['title'], pin.get('hue', 0),
                                         CHIP_PICTURE, CHIP_PICTURE / 2, self.palette(), self.font()))
        layout.addWidget(picture)

        first_word = pin['title'].split()[0] if pin['title'].split() else pin['title']
        name = QPushButton(first_word)
        name.setFlat(True)
        name.setCursor(Qt.CursorShape.PointingHandCursor)
        name.setToolTip(f"Open {pin['title']}")
        name.clicked.connect(lambda _checked=False, doc_id=pin['id']: self.open_requested.emit(doc_id))
        layout.addWidget(name)

        remove = QToolButton()
        remove.setText("×")
        remove.setAutoRaise(True)
        remove.setToolTip("Unpin")
        remove.clicked.connect(lambda _checked=False, doc_id=pin['id']: self.unpin_requested.emit(doc_id))
        layout.addWidget(remove)
        return chip
