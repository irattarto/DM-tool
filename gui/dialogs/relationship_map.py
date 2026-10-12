"""Relationship map: an entry in the middle, what it is connected to around it. Click a node to open it."""

import math
from typing import Dict

from PyQt6.QtCore import QPointF, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (QCheckBox, QDialog, QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsScene,
                             QGraphicsSimpleTextItem, QGraphicsView, QHBoxLayout, QLabel, QPushButton, QVBoxLayout)

from config.entity_types import get_registry
from gui.components.entity_list import is_dark, name_hue, placeholder_color
from services.link_service import LinkGraph

NODE_RADIUS = 26
CENTER_RADIUS = 36
RING_ONE, RING_TWO = 200, 360
MAX_NODES = 24        # per ring: a crowded ring would only be a smear


class _Node(QGraphicsEllipseItem):
    def __init__(self, doc_id: int, radius: float, brush: QColor, on_click):
        super().__init__(-radius, -radius, radius * 2, radius * 2)
        self.doc_id = doc_id
        self._on_click = on_click
        self.setBrush(QBrush(brush))
        self.setPen(QPen(QColor(255, 255, 255, 160), 2))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setZValue(2)

    def mousePressEvent(self, event):
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_click(self.doc_id)


class RelationshipMapDialog(QDialog):
    """Draws the neighbours of an entry from the link graph (links in the texts and stored relationships)."""

    open_requested = pyqtSignal(int)

    def __init__(self, graph: LinkGraph, doc_id: int, parent=None):
        super().__init__(parent)
        self.graph = graph
        self.center_id = doc_id
        self.nodes: Dict[int, _Node] = {}
        self.setWindowTitle("Relationship map")
        self.resize(820, 640)
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.caption = QLabel()
        top.addWidget(self.caption, 1)
        self.second_ring = QCheckBox("Show the next ring")
        self.second_ring.toggled.connect(lambda *_: self._draw())
        top.addWidget(self.second_ring)
        self.open_button = QPushButton("Open entry")
        self.open_button.clicked.connect(lambda: self.open_requested.emit(self.center_id))
        top.addWidget(self.open_button)
        layout.addLayout(top)
        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        layout.addWidget(self.view, 1)
        layout.addWidget(QLabel("Click a person or place to centre the map on it, 'Open entry' to read it."))
        self._draw()

    def _recentre(self, doc_id: int) -> None:
        if doc_id != self.center_id:
            self.center_id = doc_id
            self._draw()

    def _colour(self, doc: dict) -> QColor:
        return placeholder_color(name_hue(doc['title']), is_dark(self.palette()))

    def _add_node(self, doc: dict, pos: QPointF, radius: float) -> _Node:
        node = _Node(doc['id'], radius, self._colour(doc), self._recentre)
        node.setPos(pos)
        node.setToolTip(f"{doc['title']} ({get_registry().label(doc['entity_type'])})")
        self.scene.addItem(node)
        label = QGraphicsSimpleTextItem(doc['title'] if len(doc['title']) <= 22 else doc['title'][:21] + "…")
        font = QFont(self.font())
        font.setPointSizeF(font.pointSizeF() * (1.1 if radius == CENTER_RADIUS else 0.9))
        label.setFont(font)
        label.setBrush(QBrush(self.palette().text().color()))
        label.setPos(pos.x() - label.boundingRect().width() / 2, pos.y() + radius + 3)
        label.setZValue(3)
        self.scene.addItem(label)
        initial = QGraphicsSimpleTextItem(''.join(w[0] for w in doc['title'].split()[:2]).upper() or '?')
        initial.setBrush(QBrush(QColor('white')))
        initial.setFont(font)
        initial.setPos(pos.x() - initial.boundingRect().width() / 2, pos.y() - initial.boundingRect().height() / 2)
        initial.setZValue(3)
        self.scene.addItem(initial)
        self.nodes[doc['id']] = node
        return node

    def _edge(self, a: QPointF, b: QPointF) -> None:
        line = QGraphicsLineItem(a.x(), a.y(), b.x(), b.y())
        line.setPen(QPen(self.palette().mid().color(), 1.6))
        line.setZValue(1)
        self.scene.addItem(line)

    def _draw(self) -> None:
        self.scene.clear()
        self.nodes = {}
        centre_doc = self.graph.docs.get(self.center_id)
        if centre_doc is None:
            return
        self.caption.setText(f"<b>{centre_doc['title']}</b> · {get_registry().label(centre_doc['entity_type'])}")
        origin = QPointF(0, 0)
        first = self.graph.neighbours(self.center_id)[:MAX_NODES]
        placed = {self.center_id}
        positions: Dict[int, QPointF] = {}
        for index, doc in enumerate(first):
            angle = 2 * math.pi * index / max(1, len(first)) - math.pi / 2
            positions[doc['id']] = QPointF(RING_ONE * math.cos(angle), RING_ONE * math.sin(angle))
            placed.add(doc['id'])
        for doc in first:
            self._edge(origin, positions[doc['id']])
        outer = []
        if self.second_ring.isChecked():
            seen = set(placed)
            for doc in first:
                for other in self.graph.neighbours(doc['id']):
                    if other['id'] not in seen and len(outer) < MAX_NODES * 2:
                        seen.add(other['id'])
                        outer.append((doc['id'], other))
            for index, (parent_id, doc) in enumerate(outer):
                angle = 2 * math.pi * index / max(1, len(outer)) - math.pi / 2
                point = QPointF(RING_TWO * math.cos(angle), RING_TWO * math.sin(angle))
                self._edge(positions[parent_id], point)
                positions[doc['id']] = point
        for doc in first:
            self._add_node(doc, positions[doc['id']], NODE_RADIUS)
        for _parent, doc in outer:
            self._add_node(doc, positions[doc['id']], NODE_RADIUS - 8)
        self._add_node(centre_doc, origin, CENTER_RADIUS)
        if not first:
            note = QGraphicsSimpleTextItem("Nothing is linked to this entry yet.")
            note.setBrush(QBrush(self.palette().text().color()))
            note.setPos(-90, CENTER_RADIUS + 30)
            self.scene.addItem(note)
        self.scene.setSceneRect(self.scene.itemsBoundingRect().adjusted(-40, -40, 40, 40))
        self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
