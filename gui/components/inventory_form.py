"""
Inventory form component - reusable inventory item details form.
"""

from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QComboBox, QSpinBox, QCheckBox,
    QGroupBox, QLabel
)
from PyQt6.QtCore import pyqtSignal

from models.inventory_item import InventoryItem
from utils.logger import get_logger
from gui.widgets.formatted_text_edit import FormattedTextEdit


class InventoryFormComponent(QWidget):
    """Reusable component for inventory item details form."""

    # Signals
    data_changed = pyqtSignal()  # Emitted when any field changes

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = get_logger('inventory_form_component')

        self.current_item: Optional[InventoryItem] = None
        self._updating_display = False  # Prevent loops
        self._is_dirty = False  # Track if item has unsaved changes

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Setup the form UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        layout.setContentsMargins(5, 5, 5, 5)

        # Inventory item details group
        details_group = QGroupBox("Item Details")
        details_layout = QFormLayout(details_group)

        self.item_title_edit = QLineEdit()
        self.item_title_edit.setPlaceholderText("Enter item name...")
        details_layout.addRow("Name:", self.item_title_edit)

        self.item_type_combo = QComboBox()
        self.item_type_combo.addItems(['weapon', 'armor', 'magic', 'consumable', 'quest', 'misc'])
        details_layout.addRow("Type:", self.item_type_combo)

        self.quantity_spin = QSpinBox()
        self.quantity_spin.setMinimum(1)
        self.quantity_spin.setMaximum(9999)
        self.quantity_spin.setValue(1)
        details_layout.addRow("Quantity:", self.quantity_spin)

        self.equipped_checkbox = QCheckBox("Equipped")
        details_layout.addRow("", self.equipped_checkbox)

        layout.addWidget(details_group)

        # Item description
        layout.addWidget(QLabel("Description:"))
        self.item_content = FormattedTextEdit()
        self.item_content.setMinimumHeight(250)

        # Add formatting toolbar (from FormattedTextEdit)
        format_toolbar = self.item_content.create_format_toolbar()
        layout.addWidget(format_toolbar)
        layout.addWidget(self.item_content)

        # Context menu is now handled by FormattedTextEdit.contextMenuEvent()

        # Bottom status bar
        bottom_layout = QHBoxLayout()

        # Status label
        self.status_label = QLabel("Ready")
        bottom_layout.addWidget(self.status_label)

        bottom_layout.addStretch()

        layout.addLayout(bottom_layout)

        # Note: Save/Delete buttons removed - use window-level buttons instead

    def _connect_signals(self):
        """Connect internal signals."""
        self.item_title_edit.textChanged.connect(self._on_title_changed)
        self.item_content.textChanged.connect(self._on_content_changed)
        self.item_type_combo.currentTextChanged.connect(self._on_type_changed)
        self.quantity_spin.valueChanged.connect(self._on_quantity_changed)
        self.equipped_checkbox.stateChanged.connect(self._on_equipped_changed)

        # Note: Save/Delete button signals removed - use window-level buttons instead

    def _on_title_changed(self):
        """Handle title changes."""
        if self.current_item and not self._updating_display:
            self.current_item.title = self.item_title_edit.text()
            self._is_dirty = True
            self.data_changed.emit()

    def _on_content_changed(self):
        """Handle content changes."""
        if self.current_item and not self._updating_display:
            self.current_item.content = self.item_content.get_content()
            self._is_dirty = True
            self.data_changed.emit()

    def _on_type_changed(self):
        """Handle type changes."""
        if self.current_item and not self._updating_display:
            self.current_item.item_type = self.item_type_combo.currentText()
            self._is_dirty = True
            self.data_changed.emit()

    def _on_quantity_changed(self):
        """Handle quantity changes."""
        if self.current_item and not self._updating_display:
            self.current_item.quantity = self.quantity_spin.value()
            self._is_dirty = True
            self.data_changed.emit()

    def _on_equipped_changed(self):
        """Handle equipped status changes."""
        if self.current_item and not self._updating_display:
            self.current_item.equipped = self.equipped_checkbox.isChecked()
            self._is_dirty = True
            self.data_changed.emit()

    def load_item(self, item: InventoryItem):
        """Load an inventory item into the form."""
        self._updating_display = True
        self.current_item = item

        if item:
            self.item_title_edit.setText(item.title or "")
            self.item_content.set_content(item.content or "")
            self.item_type_combo.setCurrentText(item.item_type or "misc")
            self.quantity_spin.setValue(item.quantity or 1)
            self.equipped_checkbox.setChecked(item.equipped or False)

            # Enable form
            self.item_title_edit.setEnabled(True)
            self.item_content.setEnabled(True)
            self.item_type_combo.setEnabled(True)
            self.quantity_spin.setEnabled(True)
            self.equipped_checkbox.setEnabled(True)

            self.status_label.setText(f"Editing: {item.title}")
        else:
            # Clear and disable form
            self.item_title_edit.clear()
            self.item_content.clear()
            self.item_type_combo.setCurrentIndex(0)
            self.quantity_spin.setValue(1)
            self.equipped_checkbox.setChecked(False)

            self.item_title_edit.setEnabled(False)
            self.item_content.setEnabled(False)
            self.item_type_combo.setEnabled(False)
            self.quantity_spin.setEnabled(False)
            self.equipped_checkbox.setEnabled(False)

            self.status_label.setText("No item selected")

        self._is_dirty = False
        self._updating_display = False

    def get_item_data(self) -> tuple:
        """Get current form data as tuple (title, content, item_type, quantity, equipped)."""
        return (
            self.item_title_edit.text(),
            self.item_content.get_content(),
            self.item_type_combo.currentText(),
            self.quantity_spin.value(),
            self.equipped_checkbox.isChecked()
        )

    def is_dirty(self) -> bool:
        """Check if the form has unsaved changes."""
        return self._is_dirty

    def mark_clean(self):
        """Mark the form as saved (no unsaved changes)."""
        self._is_dirty = False

    def clear(self):
        """Clear the form."""
        self.load_item(None)
        self._is_dirty = False

    def set_status(self, message: str):
        """Set the status label text."""
        self.status_label.setText(message)
