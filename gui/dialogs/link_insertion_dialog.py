"""
Link Insertion Dialog for RPG Database Manager.

Provides a user-friendly interface for inserting links to entities or external URLs.
"""

from gui.theme import set_props
from config.entity_types import get_registry
from typing import Tuple

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QLineEdit, QComboBox, QTreeWidget, QTreeWidgetItem,
    QDialogButtonBox, QTextEdit, QHeaderView, QMessageBox
)
from PyQt6.QtCore import Qt

from models.database import DatabaseManager
from utils.logger import get_logger


class LinkInsertionDialog(QDialog):
    """
    Dialog for inserting links to entities or external URLs.

    Features two tabs:
    1. Entity Link: Search and select entities from the database
    2. External Link: Enter a web URL

    Returns a tuple of (link_text, link_url) when accepted.
    """

    def __init__(self, db_manager: DatabaseManager, current_module_id: int, parent=None, initial_text: str = ""):
        """
        Initialize the link insertion dialog.

        Args:
            db_manager: Database manager for querying entities
            current_module_id: Current campaign ID to filter entities
            parent: Parent widget
            initial_text: Optional text to pre-populate search and link text fields
        """
        super().__init__(parent)
        self.db = db_manager
        self.module_id = current_module_id
        self.logger = get_logger('link_insertion_dialog')

        # Store initial text for pre-population (strip whitespace)
        self.initial_text = initial_text.strip()

        # Result values
        self._link_text = ""
        self._link_url = ""

        self.setWindowTitle("Insert Link")
        self.setMinimumSize(600, 500)

        self._setup_ui()
        self._load_entities()

        # Pre-populate external link text and auto-select matching entity if initial text provided
        if self.initial_text:
            # Pre-fill external link text
            self.external_link_text.setText(self.initial_text)

            # Find and select matching entity without filtering
            self._select_matching_entity(self.initial_text)

    def _setup_ui(self):
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)

        # Create tab widget
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # Tab 1: Entity Link
        self._setup_entity_tab()

        # Tab 2: External Link
        self._setup_external_tab()

        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # Store reference to OK button for enabling/disabling
        self.ok_button = button_box.button(QDialogButtonBox.StandardButton.Ok)
        self.ok_button.setEnabled(False)  # Disabled until valid selection

    def _setup_entity_tab(self):
        """Setup the entity link tab."""
        entity_tab = QWidget()
        layout = QVBoxLayout(entity_tab)

        # Entity type filter
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Entity Type:"))

        self.entity_type_combo = QComboBox()
        self.entity_type_combo.addItem("All Types", "")
        for _key in get_registry().keys_for('tabs'):
            self.entity_type_combo.addItem(get_registry().plural(_key), _key)
        self.entity_type_combo.currentIndexChanged.connect(self._filter_entities)
        filter_layout.addWidget(self.entity_type_combo)

        # Search box
        filter_layout.addWidget(QLabel("Search:"))
        self.entity_search_box = QLineEdit()
        self.entity_search_box.setPlaceholderText("Type to search entities...")
        self.entity_search_box.textChanged.connect(self._filter_entities)
        filter_layout.addWidget(self.entity_search_box)

        layout.addLayout(filter_layout)

        # Entity list (tree widget with ID, Name, Type columns)
        self.entity_tree = QTreeWidget()
        self.entity_tree.setHeaderLabels(["ID", "Name", "Type"])
        self.entity_tree.setColumnWidth(0, 60)
        self.entity_tree.setColumnWidth(1, 300)
        self.entity_tree.setAlternatingRowColors(True)
        self.entity_tree.setSortingEnabled(True)
        self.entity_tree.sortByColumn(1, Qt.SortOrder.AscendingOrder)
        self.entity_tree.itemSelectionChanged.connect(self._on_entity_selected)
        self.entity_tree.itemDoubleClicked.connect(self._on_entity_double_clicked)
        layout.addWidget(self.entity_tree)

        # Preview area
        preview_label = QLabel("Preview:")
        layout.addWidget(preview_label)

        self.entity_preview = QTextEdit()
        self.entity_preview.setReadOnly(True)
        self.entity_preview.setMaximumHeight(100)
        self.entity_preview.setPlaceholderText("Select an entity to see a preview...")
        layout.addWidget(self.entity_preview)

        # Display text input
        display_layout = QHBoxLayout()
        display_layout.addWidget(QLabel("Link Text:"))
        self.entity_link_text = QLineEdit()
        self.entity_link_text.setPlaceholderText("Text to display for the link")
        self.entity_link_text.textChanged.connect(self._validate_entity_link)
        display_layout.addWidget(self.entity_link_text)
        layout.addLayout(display_layout)

        self.tab_widget.addTab(entity_tab, "Entity Link")

    def _setup_external_tab(self):
        """Setup the external URL link tab."""
        external_tab = QWidget()
        layout = QVBoxLayout(external_tab)

        # Instructions
        instructions = QLabel(
            "Create a link to an external webpage.\n"
            "The URL must start with http:// or https://"
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # URL input
        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("URL:"))
        self.external_url = QLineEdit()
        self.external_url.setPlaceholderText("https://example.com")
        self.external_url.textChanged.connect(self._validate_external_link)
        url_layout.addWidget(self.external_url)
        layout.addLayout(url_layout)

        # Display text input
        text_layout = QHBoxLayout()
        text_layout.addWidget(QLabel("Link Text:"))
        self.external_link_text = QLineEdit()
        self.external_link_text.setPlaceholderText("Text to display for the link")
        self.external_link_text.textChanged.connect(self._validate_external_link)
        text_layout.addWidget(self.external_link_text)
        layout.addLayout(text_layout)

        # Example
        example = QLabel(
            "\nExample:\n"
            "URL: https://www.dndbeyond.com\n"
            "Link Text: D&D Beyond\n"
            "Result: [D&D Beyond](https://www.dndbeyond.com)"
        )
        example.setWordWrap(True)
        set_props(example, role="code")
        layout.addWidget(example)

        layout.addStretch()

        self.tab_widget.addTab(external_tab, "External Link")

    def _load_entities(self):
        """Load all entities from the current campaign."""
        try:
            # Get all entity types
            entity_types = get_registry().keys_for('tabs')

            self.all_entities = []
            for entity_type in entity_types:
                documents = self.db.get_documents(self.module_id, entity_type)
                for doc in documents:
                    self.all_entities.append({
                        'id': doc['id'],
                        'title': doc['title'],
                        'type': entity_type,
                        'content': doc.get('content', '')[:200]  # First 200 chars for preview
                    })

            self.logger.info(f"Loaded {len(self.all_entities)} entities for link insertion")
            self._populate_entity_tree(self.all_entities)

        except Exception as e:
            self.logger.error(f"Error loading entities: {e}")
            QMessageBox.warning(
                self,
                "Load Error",
                f"Failed to load entities from database:\n{str(e)}"
            )

    def _populate_entity_tree(self, entities):
        """
        Populate the entity tree with the given entities.

        Args:
            entities: List of entity dicts with id, title, type
        """
        self.entity_tree.clear()

        for entity in entities:
            item = QTreeWidgetItem([
                str(entity['id']),
                entity['title'],
                entity['type'].upper()
            ])
            # Store full entity data for later retrieval
            item.setData(0, Qt.ItemDataRole.UserRole, entity)
            self.entity_tree.addTopLevelItem(item)

        # Resize columns to content
        self.entity_tree.header().resizeSections(QHeaderView.ResizeMode.ResizeToContents)

    def _filter_entities(self):
        """Filter entities based on type and search text."""
        entity_type = self.entity_type_combo.currentData()
        search_text = self.entity_search_box.text().lower()

        filtered = []
        for entity in self.all_entities:
            # Filter by type
            if entity_type and entity['type'] != entity_type:
                continue

            # Filter by search text
            if search_text and search_text not in entity['title'].lower():
                continue

            filtered.append(entity)

        self._populate_entity_tree(filtered)

    def _select_matching_entity(self, search_text: str):
        """
        Find and select an entity matching the search text without filtering.

        Args:
            search_text: Text to search for in entity titles
        """
        if not search_text:
            return

        search_lower = search_text.lower()

        # Search through all items in the tree
        for i in range(self.entity_tree.topLevelItemCount()):
            item = self.entity_tree.topLevelItem(i)
            entity = item.data(0, Qt.ItemDataRole.UserRole)

            # Check if entity title contains search text (case-insensitive)
            if entity and search_lower in entity['title'].lower():
                # Select and scroll to this item
                self.entity_tree.setCurrentItem(item)
                item.setSelected(True)
                self.entity_tree.scrollToItem(item)
                # Trigger selection changed to update preview and link text
                self._on_entity_selected()
                break

    def _on_entity_selected(self):
        """Handle entity selection in tree."""
        selected_items = self.entity_tree.selectedItems()
        if not selected_items:
            self.entity_preview.clear()
            self.entity_link_text.clear()
            self.ok_button.setEnabled(False)
            return

        item = selected_items[0]
        entity = item.data(0, Qt.ItemDataRole.UserRole)

        # Update preview
        preview_text = f"**{entity['title']}** ({entity['type'].upper()})\n\n"
        preview_text += entity['content'][:200]
        if len(entity['content']) > 200:
            preview_text += "..."
        self.entity_preview.setMarkdown(preview_text)

        # Auto-fill link text with entity name (if not already filled)
        if not self.entity_link_text.text():
            self.entity_link_text.setText(entity['title'])

        self._validate_entity_link()

    def _on_entity_double_clicked(self, item, column):
        """Handle double-click on entity - accept dialog."""
        if self.ok_button.isEnabled():
            self.accept()

    def _validate_entity_link(self):
        """Validate the entity link and enable/disable OK button."""
        selected_items = self.entity_tree.selectedItems()
        has_selection = len(selected_items) > 0
        has_text = bool(self.entity_link_text.text().strip())

        # Only enable if on entity tab, have selection, and have link text
        is_entity_tab = self.tab_widget.currentIndex() == 0
        self.ok_button.setEnabled(is_entity_tab and has_selection and has_text)

    def _validate_external_link(self):
        """Validate the external link and enable/disable OK button."""
        url = self.external_url.text().strip()
        text = self.external_link_text.text().strip()

        # Validate URL format
        is_valid_url = url.startswith('http://') or url.startswith('https://')
        has_text = bool(text)

        # Only enable if on external tab, have valid URL, and have link text
        is_external_tab = self.tab_widget.currentIndex() == 1
        self.ok_button.setEnabled(is_external_tab and is_valid_url and has_text)

    def _on_accept(self):
        """Handle OK button click - validate and prepare result."""
        current_tab = self.tab_widget.currentIndex()

        if current_tab == 0:  # Entity Link
            selected_items = self.entity_tree.selectedItems()
            if not selected_items:
                QMessageBox.warning(self, "No Selection", "Please select an entity.")
                return

            item = selected_items[0]
            entity = item.data(0, Qt.ItemDataRole.UserRole)

            self._link_text = self.entity_link_text.text().strip()
            self._link_url = f"rpg://{entity['type']}/{entity['id']}"

            self.logger.info(f"Created entity link: [{self._link_text}]({self._link_url})")

        else:  # External Link
            url = self.external_url.text().strip()
            if not (url.startswith('http://') or url.startswith('https://')):
                QMessageBox.warning(
                    self,
                    "Invalid URL",
                    "URL must start with http:// or https://"
                )
                return

            self._link_text = self.external_link_text.text().strip()
            self._link_url = url

            self.logger.info(f"Created external link: [{self._link_text}]({self._link_url})")

        if not self._link_text:
            QMessageBox.warning(self, "No Link Text", "Please enter text for the link.")
            return

        self.accept()

    def get_link(self) -> Tuple[str, str]:
        """
        Get the created link.

        Returns:
            Tuple of (link_text, link_url)
        """
        return (self._link_text, self._link_url)
