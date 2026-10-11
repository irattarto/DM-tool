"""
Dialog for creating and editing document templates.
"""

import re

from config.entity_types import get_registry
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QCheckBox, QTextEdit, QPushButton
)
from PyQt6.QtCore import Qt

from models.document import DocumentTemplate
from services.template_service import TemplateService
from utils.logger import get_logger
from utils.ui_helpers import show_error, show_warning, show_info, show_question


class TemplateEditorDialog(QDialog):
    """Dialog for creating and editing document templates."""

    def __init__(self, template_service: TemplateService, existing_template: DocumentTemplate = None, parent=None):
        super().__init__(parent)
        self.template_service = template_service
        self.existing_template = existing_template
        self.selected_template = None
        self.logger = get_logger('template_editor_dialog')

        if existing_template:
            self.setWindowTitle(f"Edit Template: {existing_template.template_name}")
        else:
            self.setWindowTitle("Create New Template")

        self.setModal(True)
        self.resize(600, 500)

        self._setup_ui()
        if existing_template:
            self._load_template_data(existing_template)

    def _setup_ui(self):
        """Setup the template editor UI."""
        layout = QVBoxLayout(self)

        # Template name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Template Name:"))
        self.name_edit = QLineEdit()
        name_layout.addWidget(self.name_edit)
        layout.addLayout(name_layout)

        # Entity type
        entity_layout = QHBoxLayout()
        entity_layout.addWidget(QLabel("Entity Type:"))
        self.entity_combo = QComboBox()
        for _key in get_registry().keys_for('create'):
            self.entity_combo.addItem(get_registry().label(_key), _key)
        entity_layout.addWidget(self.entity_combo)
        layout.addLayout(entity_layout)

        # Set as default checkbox
        self.default_checkbox = QCheckBox("Set as default template for this entity type")
        layout.addWidget(self.default_checkbox)

        # Template content
        layout.addWidget(QLabel("Template Content:"))
        self.content_edit = QTextEdit()

        # Custom context menu (paste without formatting)
        self.content_edit.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.content_edit.customContextMenuRequested.connect(self._show_template_context_menu)

        layout.addWidget(self.content_edit)

        # Template preview removed as requested

        # Buttons
        button_layout = QHBoxLayout()

        self.test_btn = QPushButton("Test Placeholders")
        self.test_btn.clicked.connect(self._test_placeholders)
        button_layout.addWidget(self.test_btn)

        button_layout.addStretch()

        self.save_btn = QPushButton("Save Template")
        self.save_btn.clicked.connect(self._on_save)
        button_layout.addWidget(self.save_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        layout.addLayout(button_layout)

    def _load_template_data(self, template: DocumentTemplate):
        """Load existing template data into form."""
        self.name_edit.setText(template.template_name)
        _idx = self.entity_combo.findData(template.entity_type)
        if _idx < 0:  # template for a type that is not (or no longer) in the registry
            self.entity_combo.addItem(get_registry().label(template.entity_type), template.entity_type)
            _idx = self.entity_combo.count() - 1
        self.entity_combo.setCurrentIndex(_idx)
        self.default_checkbox.setChecked(template.is_default)
        self.content_edit.setPlainText(template.template_content)


    def _test_placeholders(self):
        """Test and show all placeholders in the template."""
        content = self.content_edit.toPlainText()

        placeholders = re.findall(r'\[([^\]]+)\]', content)

        if placeholders:
            unique_placeholders = list(set(placeholders))
            placeholder_text = "Found placeholders:\n" + "\n".join(f"• [{p}]" for p in unique_placeholders)

            show_info(self, "Template Placeholders", placeholder_text
            )
        else:
            show_info(self, "No Placeholders", "No placeholders found in template.")

    def _on_save(self):
        """Save the template."""
        name = self.name_edit.text().strip()
        if not name:
            show_warning(self, "Invalid Input", "Please enter a template name.")
            return

        entity_type = self.entity_combo.currentData()
        if not entity_type:
            show_warning(self, "Invalid Input", "Please select an entity type.")
            return

        content = self.content_edit.toPlainText()
        if not content.strip():
            show_warning(self, "Invalid Input", "Please enter template content.")
            return

        try:
            # Validate template
            issues = self.template_service.validate_template(content)
            if issues:
                if not show_question(
                    self,
                    "Template Issues",
                    "The following issues were found:\n\n" + "\n".join(f"• {issue}" for issue in issues) +
                    "\n\nDo you want to save anyway?"
                ):
                    return

            # Save template
            template_id = self.template_service.save_template(
                template_name=name,
                entity_type=entity_type,
                template_content=content,
                is_default=self.default_checkbox.isChecked()
            )

            if template_id:
                show_info(self, "Success", f"Template '{name}' saved successfully.")
                self.accept()
            else:
                show_error(self, "Error", "Failed to save template.")

        except Exception as e:
            show_error(self, "Error", f"Failed to save template: {e}")

    def _paste_without_formatting(self):
        """Paste clipboard content as plain text without formatting."""
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtGui import QTextCharFormat

        clipboard = QApplication.clipboard()
        plain_text = clipboard.text()
        if plain_text:
            cursor = self.content_edit.textCursor()

            # Create a plain text format (no formatting)
            plain_format = QTextCharFormat()

            # Apply plain format and insert text
            cursor.setCharFormat(plain_format)
            cursor.insertText(plain_text)

            # Update the cursor position
            self.content_edit.setTextCursor(cursor)

    def _show_template_context_menu(self, position):
        """Show context menu for the template content editor."""
        # Create the default context menu
        menu = self.content_edit.createStandardContextMenu()

        # Add paste without formatting option after the standard menu
        menu.addSeparator()
        paste_plain_action = menu.addAction("Paste Without Formatting")
        paste_plain_action.setShortcut("Ctrl+Shift+V")
        paste_plain_action.triggered.connect(self._paste_without_formatting)

        # Show the menu at the cursor position
        menu.exec(self.content_edit.mapToGlobal(position))
