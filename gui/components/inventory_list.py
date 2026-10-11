"""
Inventory list component - reusable inventory list with filtering.
"""

from typing import List
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QListWidget, QListWidgetItem, QAbstractItemView, QComboBox, QLabel
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer

from models.inventory_item import InventoryItem
from utils.logger import get_logger


class InventoryListComponent(QWidget):
    """Reusable component for displaying and filtering inventory items."""

    # Signals
    item_selected = pyqtSignal(object)  # InventoryItem
    refresh_requested = pyqtSignal()
    new_item_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = get_logger('inventory_list_component')

        self.items: List[InventoryItem] = []
        self.filtered_items: List[InventoryItem] = []
        self.current_filter: str = 'all'

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Setup the inventory list UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(3)
        layout.setContentsMargins(3, 3, 3, 3)

        # Top row: Main action buttons
        top_controls_layout = QHBoxLayout()
        top_controls_layout.setSpacing(3)

        self.new_item_btn = QPushButton("New Item")
        top_controls_layout.addWidget(self.new_item_btn)

        self.refresh_btn = QPushButton("Refresh")
        top_controls_layout.addWidget(self.refresh_btn)

        top_controls_layout.addStretch()
        layout.addLayout(top_controls_layout)

        # Add a small spacer between rows
        layout.addSpacing(5)

        # Bottom row: Filter dropdown
        filter_controls_layout = QHBoxLayout()
        filter_controls_layout.setSpacing(3)

        filter_label = QLabel("Filter:")
        filter_controls_layout.addWidget(filter_label)

        self.filter_combo = QComboBox()
        self.filter_combo.addItem("All", "all")
        self.filter_combo.addItem("Weapons", "weapon")
        self.filter_combo.addItem("Armor", "armor")
        self.filter_combo.addItem("Magic", "magic")
        self.filter_combo.addItem("Consumables", "consumable")
        self.filter_combo.addItem("Quest", "quest")
        self.filter_combo.addItem("Misc", "misc")
        filter_controls_layout.addWidget(self.filter_combo, 1)

        layout.addLayout(filter_controls_layout)

        # Inventory list
        self.item_list = QListWidget(self)
        self.item_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.item_list.setMinimumHeight(200)
        layout.addWidget(self.item_list)

    def _connect_signals(self):
        """Connect internal signals."""
        self.new_item_btn.clicked.connect(self.new_item_requested.emit)
        self.refresh_btn.clicked.connect(self.refresh_requested.emit)

        self.filter_combo.currentIndexChanged.connect(self._on_filter_changed)

        self.item_list.itemClicked.connect(self._on_item_clicked)

    def _on_filter_changed(self):
        """Handle filter dropdown change."""
        filter_type = self.filter_combo.currentData()
        if filter_type:
            self.filter_items(filter_type)

    def _on_item_clicked(self, item: QListWidgetItem):
        """Handle item click - emit item_selected signal."""
        inventory_item = item.data(Qt.ItemDataRole.UserRole)
        if inventory_item:
            self.item_selected.emit(inventory_item)

    def set_items(self, items: List[InventoryItem]):
        """Set the list of all inventory items."""
        self.items = items
        self.filter_items(self.current_filter)

    def filter_items(self, filter_type: str):
        """Filter inventory items by type."""
        self.current_filter = filter_type

        if filter_type == 'all':
            self.filtered_items = self.items
        else:
            self.filtered_items = [i for i in self.items if i.item_type == filter_type]

        # Update combo box selection (without triggering signal)
        self.filter_combo.blockSignals(True)
        index = self.filter_combo.findData(filter_type)
        if index >= 0:
            self.filter_combo.setCurrentIndex(index)
        self.filter_combo.blockSignals(False)

        # Refresh the list display
        self._refresh_display()

    def _refresh_display(self):
        """Refresh the inventory list display with current filter."""
        # Save current selection before clearing
        selected_item_id = None
        current_item = self.item_list.currentItem()
        if current_item:
            item_data = current_item.data(Qt.ItemDataRole.UserRole)
            if item_data:
                selected_item_id = item_data.id

        # Save scroll position
        scroll_bar = self.item_list.verticalScrollBar()
        scroll_position = scroll_bar.value() if scroll_bar else 0

        self.item_list.clear()

        for inv_item in self.filtered_items:
            try:
                # Add type indicator to display text
                type_icon = {
                    "weapon": "⚔️",
                    "armor": "🛡️",
                    "magic": "✨",
                    "consumable": "🧪",
                    "quest": "📜",
                    "misc": "📦"
                }.get(inv_item.item_type, "📦")

                # Show equipped marker and quantity
                equipped_marker = " [E]" if inv_item.equipped else ""
                quantity_text = f" x{inv_item.quantity}" if inv_item.quantity > 1 else ""
                display_text = f"{type_icon} {inv_item.title}{quantity_text}{equipped_marker}"

                list_item = QListWidgetItem(display_text)
                list_item.setData(Qt.ItemDataRole.UserRole, inv_item)
                self.item_list.addItem(list_item)
            except Exception as item_error:
                self.logger.warning(f"Error adding inventory item to list: {item_error}")

        # Restore previous selection if it still exists
        # Use QTimer to ensure this happens after the list is fully rendered
        def restore_position():
            if selected_item_id is not None:
                for i in range(self.item_list.count()):
                    list_item = self.item_list.item(i)
                    item_data = list_item.data(Qt.ItemDataRole.UserRole)
                    if item_data and item_data.id == selected_item_id:
                        self.item_list.setCurrentItem(list_item)
                        self.item_list.scrollToItem(list_item)
                        self.logger.debug(f"Restored selection to inventory item ID {selected_item_id}")
                        break

            # Restore scroll position
            elif scroll_bar:
                # Only restore scroll if no item was selected (otherwise scrollToItem handles it)
                scroll_bar.setValue(scroll_position)
                self.logger.debug(f"Restored scroll position to {scroll_position}")

        # Delay restoration to ensure it happens after rendering
        QTimer.singleShot(0, restore_position)

    def select_item_by_id(self, item_id: int):
        """Select an inventory item by ID in the list."""
        for i in range(self.item_list.count()):
            list_item = self.item_list.item(i)
            inv_item = list_item.data(Qt.ItemDataRole.UserRole)
            if inv_item and inv_item.id == item_id:
                self.item_list.setCurrentItem(list_item)
                break

    def clear(self):
        """Clear the inventory list."""
        self.item_list.clear()
        self.items = []
        self.filtered_items = []
