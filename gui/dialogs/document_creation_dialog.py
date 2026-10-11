"""
Dialog for creating new documents from templates.
"""

from config.entity_types import get_registry
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox
)

from services.template_service import TemplateService
from utils.ui_helpers import show_warning
from gui.components.dialog_button_bar import DialogButtonBar


class DocumentCreationDialog(QDialog):
    """Dialog for creating new documents."""

    def __init__(self, template_service: TemplateService, parent=None):
        super().__init__(parent)
        self.template_service = template_service
        self.selected_template = None
        self.field_values = {}

        self.setWindowTitle("Create New Document")
        self.setModal(True)
        self.resize(500, 400)

        self._setup_ui()
        self._load_templates()

    def _setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)

        # Entity type selection
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Entity Type:"))
        self.entity_type_combo = QComboBox()
        for _key in get_registry().keys_for('create'):
            self.entity_type_combo.addItem(get_registry().label(_key), _key)
        self.entity_type_combo.currentIndexChanged.connect(self._on_entity_type_changed)
        type_layout.addWidget(self.entity_type_combo)
        layout.addLayout(type_layout)

        # Template selection
        template_layout = QHBoxLayout()
        template_layout.addWidget(QLabel("Template:"))
        self.template_combo = QComboBox()
        self.template_combo.currentTextChanged.connect(self._on_template_changed)
        template_layout.addWidget(self.template_combo)
        layout.addLayout(template_layout)

        # Title input
        title_layout = QHBoxLayout()
        title_layout.addWidget(QLabel("Title:"))
        self.title_edit = QLineEdit()
        title_layout.addWidget(self.title_edit)
        layout.addLayout(title_layout)

        # Spacer
        layout.addStretch()

        # Buttons - standardized bottom-right layout
        layout.addSpacing(15)  # Extra space before button bar
        button_bar = DialogButtonBar(alignment='right')
        buttons = button_bar.set_standard_buttons(['cancel', 'create'])

        self.create_btn = buttons['create']
        self.create_btn.clicked.connect(self._on_create)

        self.cancel_btn = buttons['cancel']
        self.cancel_btn.clicked.connect(self.reject)

        layout.addWidget(button_bar)

    def _load_templates(self):
        """Load available templates."""
        try:
            templates = self.template_service.get_templates()
            self.template_combo.clear()

            # Group templates by entity type
            templates_by_type = {}
            for template in templates:
                if template.entity_type not in templates_by_type:
                    templates_by_type[template.entity_type] = []
                templates_by_type[template.entity_type].append(template)

            # Add templates for current entity type
            current_type = self.entity_type_combo.currentData()
            if current_type in templates_by_type:
                for template in templates_by_type[current_type]:
                    self.template_combo.addItem(
                        template.template_name,
                        template
                    )

                if templates_by_type[current_type]:
                    self.template_combo.setCurrentIndex(0)
                    self._on_template_changed()

        except Exception as e:
            print(f"Error loading templates: {e}")

    def _on_entity_type_changed(self):
        """Handle entity type change."""
        self._load_templates()

    def _on_template_changed(self):
        """Handle template selection change."""
        current_text = self.template_combo.currentText()
        if not current_text:
            return

        try:
            # Get selected template
            current_index = self.template_combo.currentIndex()
            if current_index >= 0:
                template = self.template_combo.itemData(current_index)
                if template:
                    self.selected_template = template

                    # Update title suggestion
                    placeholders = template.get_placeholders()
                    if placeholders:
                        suggested_title = f"New {get_registry().label(template.entity_type)}"
                        self.title_edit.setText(suggested_title)

        except Exception as e:
            print(f"Error updating template preview: {e}")

    def _on_create(self):
        """Handle document creation."""
        if not self.selected_template:
            show_warning(self, "No Template", "Please select a template.")
            return

        title = self.title_edit.text().strip()
        if not title:
            show_warning(self, "No Title", "Please enter a title.")
            return

        # Accept dialog
        self.accept()
