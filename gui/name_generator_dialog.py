"""
Name Generator Dialog for RPG Database Manager.

Simple tool for generating character/entity names from embedded name lists.
"""

from gui.theme import set_props
from typing import List
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QListWidget, QListWidgetItem, QGroupBox, QFormLayout,
    QApplication
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from utils.ui_helpers import show_error, show_warning
from utils.logger import get_logger
from services.name_generation_service import NameGenerationService

# Import style manager
try:
    from gui.theme.style_manager import get_style_manager
except ImportError:
    def get_style_manager():
        return None




class NameGeneratorDialog(QDialog):
    """Dialog for generating character/entity names."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.name_service = NameGenerationService()
        self.logger = get_logger('name_generator_dialog')
        self.style_manager = get_style_manager()

        self.setWindowTitle("Name Generator")
        self.setModal(False)
        self.resize(500, 600)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self._setup_ui()
        self._apply_styles()

    def _setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("Name Generator")
        title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        # Settings group
        settings_group = QGroupBox("Name Settings")
        settings_layout = QFormLayout()

        # Style selector
        self.style_combo = QComboBox()
        self.style_combo.addItems([
            "fantasy",
            "english",
            "german",
            "hungarian",
            "nordic",
            "celtic",
            "asian"
        ])
        name_style_label = QLabel("Name Style:")
        name_style_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.style_combo.setToolTip("Choose the style/culture for generated names")
        settings_layout.addRow(name_style_label, self.style_combo)

        # Gender selector
        self.gender_combo = QComboBox()
        self.gender_combo.addItems(["any", "male", "female"])
        gender_label = QLabel("Gender:")
        gender_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.gender_combo.setToolTip("Optional: specify gender for names")
        settings_layout.addRow(gender_label, self.gender_combo)

        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)

        # Generate button
        self.generate_btn = QPushButton("Generate Names")
        self.generate_btn.clicked.connect(self._on_generate)
        layout.addWidget(self.generate_btn)

        # Results group
        results_group = QGroupBox("Generated Names")
        results_layout = QVBoxLayout()

        self.names_list = QListWidget()
        self.names_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.names_list.itemDoubleClicked.connect(self._on_name_double_clicked)
        results_layout.addWidget(self.names_list)

        # Hint label
        hint_label = QLabel("Tip: Select names and click 'Copy Selected' or double-click to copy one")
        hint_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        results_layout.addWidget(hint_label)

        results_group.setLayout(results_layout)
        layout.addWidget(results_group, stretch=1)

        # Bottom buttons
        button_layout = QHBoxLayout()

        self.copy_btn = QPushButton("Copy Selected Names")
        self.copy_btn.clicked.connect(self._on_copy_selected)
        self.copy_btn.setEnabled(False)
        button_layout.addWidget(self.copy_btn)

        button_layout.addStretch()

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.close)
        button_layout.addWidget(self.close_btn)

        layout.addLayout(button_layout)

        # Connect selection change to enable/disable copy button
        self.names_list.itemSelectionChanged.connect(self._on_selection_changed)

    def _apply_styles(self):
        """Apply visual styles to the dialog."""
        set_props(self.generate_btn, variant="primary")

    def _on_generate(self):
        """Generate names."""
        # Clear previous results
        self.names_list.clear()

        # Get settings
        name_style = self.style_combo.currentText()
        gender = self.gender_combo.currentText()

        try:
            names = self.name_service.generate_names(name_style, gender, count=10)
            self._on_names_generated(names)
        except Exception as e:
            self.logger.error(f"Name generation failed: {e}", exc_info=True)
            self._on_generation_error(f"Name generation failed: {e}")

    def _on_names_generated(self, names: List[str]):
        """Handle generated names."""
        self.logger.info(f"Generated {len(names)} names")

        # Add names to list
        for name in names:
            item = QListWidgetItem(name)
            self.names_list.addItem(item)

        # Re-enable generate button
        self.generate_btn.setEnabled(True)
        self.generate_btn.setText("Generate Names")


    def _on_generation_error(self, error_message: str):
        """Handle generation error."""
        self.logger.error(f"Name generation error: {error_message}")
        show_error(self, "Generation Error", error_message)

        # Re-enable generate button
        self.generate_btn.setEnabled(True)
        self.generate_btn.setText("Generate Names")


    def _on_selection_changed(self):
        """Handle selection change in names list."""
        has_selection = len(self.names_list.selectedItems()) > 0
        self.copy_btn.setEnabled(has_selection)

    def _on_copy_selected(self):
        """Copy selected names to clipboard."""
        selected_items = self.names_list.selectedItems()
        if not selected_items:
            return

        names = [item.text() for item in selected_items]
        names_text = '\n'.join(names)
        clipboard = QApplication.clipboard()
        clipboard.setText(names_text)

        count = len(names)
        if count == 1:
            self.logger.info(f"Copied name to clipboard: {names[0]}")
            show_warning(self, "Copied", f"Copied '{names[0]}' to clipboard")
        else:
            self.logger.info(f"Copied {count} names to clipboard")
            show_warning(self, "Copied", f"Copied {count} names to clipboard")

    def _on_name_double_clicked(self, item: QListWidgetItem):
        """Handle double-click on a name."""
        name = item.text()
        clipboard = QApplication.clipboard()
        clipboard.setText(name)

        self.logger.info(f"Copied name to clipboard: {name}")
        show_warning(self, "Copied", f"Copied '{name}' to clipboard")
