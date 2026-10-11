"""
Ability list component - reusable ability list with filtering.
"""

from typing import List
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QListWidget, QListWidgetItem, QAbstractItemView, QComboBox, QLabel
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer

from models.ability_item import AbilityItem
from utils.logger import get_logger


class AbilityListComponent(QWidget):
    """Reusable component for displaying and filtering ability items."""

    # Signals
    ability_selected = pyqtSignal(object)  # AbilityItem
    refresh_requested = pyqtSignal()
    new_ability_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = get_logger('ability_list_component')

        self.abilities: List[AbilityItem] = []
        self.filtered_abilities: List[AbilityItem] = []
        self.current_filter: str = 'all'

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Setup the ability list UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(3)
        layout.setContentsMargins(3, 3, 3, 3)

        # Top row: Main action buttons
        top_controls_layout = QHBoxLayout()
        top_controls_layout.setSpacing(3)

        self.new_ability_btn = QPushButton("New Ability")
        top_controls_layout.addWidget(self.new_ability_btn)

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
        self.filter_combo.addItem("Spells/Gifts/Disciplines", "spell")
        self.filter_combo.addItem("Rituals", "ritual")
        self.filter_combo.addItem("Backgrounds", "background")
        self.filter_combo.addItem("Merits/Flaws", "merit")
        self.filter_combo.addItem("Other", "other")
        filter_controls_layout.addWidget(self.filter_combo, 1)

        layout.addLayout(filter_controls_layout)

        # Ability list
        self.ability_list = QListWidget(self)
        self.ability_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.ability_list.setMinimumHeight(200)
        layout.addWidget(self.ability_list)

    def _connect_signals(self):
        """Connect internal signals."""
        self.new_ability_btn.clicked.connect(self.new_ability_requested.emit)
        self.refresh_btn.clicked.connect(self.refresh_requested.emit)

        self.filter_combo.currentIndexChanged.connect(self._on_filter_changed)

        self.ability_list.itemClicked.connect(self._on_item_clicked)

    def _on_filter_changed(self):
        """Handle filter dropdown change."""
        filter_type = self.filter_combo.currentData()
        if filter_type:
            self.filter_abilities(filter_type)

    def _on_item_clicked(self, item: QListWidgetItem):
        """Handle item click - emit ability_selected signal."""
        ability = item.data(Qt.ItemDataRole.UserRole)
        if ability:
            self.ability_selected.emit(ability)

    def set_abilities(self, abilities: List[AbilityItem]):
        """Set the list of all abilities."""
        self.abilities = abilities
        self.filter_abilities(self.current_filter)

    def filter_abilities(self, filter_type: str):
        """Filter abilities by type."""
        self.current_filter = filter_type

        if filter_type == 'all':
            self.filtered_abilities = self.abilities
        else:
            self.filtered_abilities = [a for a in self.abilities if a.ability_type == filter_type]

        # Update combo box selection (without triggering signal)
        self.filter_combo.blockSignals(True)
        index = self.filter_combo.findData(filter_type)
        if index >= 0:
            self.filter_combo.setCurrentIndex(index)
        self.filter_combo.blockSignals(False)

        # Refresh the list display
        self._refresh_display()

    def _refresh_display(self):
        """Refresh the ability list display with current filter."""
        # Save current selection before clearing
        selected_ability_id = None
        current_item = self.ability_list.currentItem()
        if current_item:
            ability_data = current_item.data(Qt.ItemDataRole.UserRole)
            if ability_data:
                selected_ability_id = ability_data.id

        # Save scroll position
        scroll_bar = self.ability_list.verticalScrollBar()
        scroll_position = scroll_bar.value() if scroll_bar else 0

        self.ability_list.clear()

        for ability in self.filtered_abilities:
            try:
                # Add type indicator to display text
                type_icon = {
                    "spell": "✨",
                    "ritual": "⭐",
                    "background": "🏛️",
                    "merit": "⚖️",
                    "other": "💠"
                }.get(ability.ability_type, "💠")

                display_text = f"{type_icon} {ability.title}"

                item = QListWidgetItem(display_text)
                item.setData(Qt.ItemDataRole.UserRole, ability)
                self.ability_list.addItem(item)
            except Exception as item_error:
                self.logger.warning(f"Error adding ability to list: {item_error}")

        # Restore previous selection if it still exists
        # Use QTimer to ensure this happens after the list is fully rendered
        def restore_position():
            if selected_ability_id is not None:
                for i in range(self.ability_list.count()):
                    item = self.ability_list.item(i)
                    ability_data = item.data(Qt.ItemDataRole.UserRole)
                    if ability_data and ability_data.id == selected_ability_id:
                        self.ability_list.setCurrentItem(item)
                        self.ability_list.scrollToItem(item)
                        self.logger.debug(f"Restored selection to ability ID {selected_ability_id}")
                        break

            # Restore scroll position
            elif scroll_bar:
                # Only restore scroll if no item was selected (otherwise scrollToItem handles it)
                scroll_bar.setValue(scroll_position)
                self.logger.debug(f"Restored scroll position to {scroll_position}")

        # Delay restoration to ensure it happens after rendering
        QTimer.singleShot(0, restore_position)

    def select_ability_by_id(self, ability_id: int):
        """Select an ability by ID in the list."""
        for i in range(self.ability_list.count()):
            item = self.ability_list.item(i)
            ability = item.data(Qt.ItemDataRole.UserRole)
            if ability and ability.id == ability_id:
                self.ability_list.setCurrentItem(item)
                break

    def clear(self):
        """Clear the ability list."""
        self.ability_list.clear()
        self.abilities = []
        self.filtered_abilities = []
