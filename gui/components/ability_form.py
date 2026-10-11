"""
Ability form component - reusable ability details form.
"""

from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QComboBox, QGroupBox, QLabel
)
from PyQt6.QtCore import pyqtSignal

from models.ability_item import AbilityItem
from utils.logger import get_logger
from gui.widgets.formatted_text_edit import FormattedTextEdit


class AbilityFormComponent(QWidget):
    """Reusable component for ability details form."""

    # Signals
    data_changed = pyqtSignal()  # Emitted when any field changes

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = get_logger('ability_form_component')

        self.current_ability: Optional[AbilityItem] = None
        self._updating_display = False  # Prevent loops
        self._is_dirty = False  # Track if ability has unsaved changes

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Setup the form UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        layout.setContentsMargins(5, 5, 5, 5)

        # Ability details group
        details_group = QGroupBox("Ability Details")
        details_layout = QFormLayout(details_group)

        self.ability_title_edit = QLineEdit()
        self.ability_title_edit.setPlaceholderText("Enter ability name...")
        details_layout.addRow("Name:", self.ability_title_edit)

        self.ability_type_combo = QComboBox()
        self.ability_type_combo.addItems(['spell', 'ritual', 'background', 'merit', 'other'])
        details_layout.addRow("Type:", self.ability_type_combo)

        layout.addWidget(details_group)

        # Ability description
        layout.addWidget(QLabel("Description:"))
        self.ability_content = FormattedTextEdit()
        self.ability_content.setMinimumHeight(300)

        # Add formatting toolbar (from FormattedTextEdit)
        format_toolbar = self.ability_content.create_format_toolbar()
        layout.addWidget(format_toolbar)
        layout.addWidget(self.ability_content)

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
        self.ability_title_edit.textChanged.connect(self._on_title_changed)
        self.ability_content.textChanged.connect(self._on_content_changed)
        self.ability_type_combo.currentTextChanged.connect(self._on_type_changed)

        # Note: Save/Delete button signals removed - use window-level buttons instead

    def _on_title_changed(self):
        """Handle title changes."""
        if self.current_ability and not self._updating_display:
            self.current_ability.title = self.ability_title_edit.text()
            self._is_dirty = True
            self.data_changed.emit()

    def _on_content_changed(self):
        """Handle content changes."""
        if self.current_ability and not self._updating_display:
            self.current_ability.content = self.ability_content.get_content()
            self._is_dirty = True
            self.data_changed.emit()

    def _on_type_changed(self):
        """Handle type changes."""
        if self.current_ability and not self._updating_display:
            self.current_ability.ability_type = self.ability_type_combo.currentText()
            self._is_dirty = True
            self.data_changed.emit()

    def load_ability(self, ability: AbilityItem):
        """Load an ability into the form."""
        self._updating_display = True
        self.current_ability = ability

        if ability:
            self.ability_title_edit.setText(ability.title or "")
            self.ability_content.set_content(ability.content or "")
            self.ability_type_combo.setCurrentText(ability.ability_type or "skill")

            # Enable form
            self.ability_title_edit.setEnabled(True)
            self.ability_content.setEnabled(True)
            self.ability_type_combo.setEnabled(True)

            self.status_label.setText(f"Editing: {ability.title}")
        else:
            # Clear and disable form
            self.ability_title_edit.clear()
            self.ability_content.clear()
            self.ability_type_combo.setCurrentIndex(0)

            self.ability_title_edit.setEnabled(False)
            self.ability_content.setEnabled(False)
            self.ability_type_combo.setEnabled(False)

            self.status_label.setText("No ability selected")

        self._is_dirty = False
        self._updating_display = False

    def get_ability_data(self) -> tuple:
        """Get current form data as tuple (title, content, ability_type)."""
        return (
            self.ability_title_edit.text(),
            self.ability_content.get_content(),
            self.ability_type_combo.currentText()
        )

    def is_dirty(self) -> bool:
        """Check if the form has unsaved changes."""
        return self._is_dirty

    def mark_clean(self):
        """Mark the form as saved (no unsaved changes)."""
        self._is_dirty = False

    def clear(self):
        """Clear the form."""
        self.load_ability(None)
        self._is_dirty = False

    def set_status(self, message: str):
        """Set the status label text."""
        self.status_label.setText(message)
