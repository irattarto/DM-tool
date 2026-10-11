"""
Inventory widget for RPG Database Manager - Inventory item management for characters/NPCs.
"""

from typing import List, Optional

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QSplitter
from PyQt6.QtCore import pyqtSignal, Qt, QSettings

from models.inventory_item import InventoryItem
from models.database import DatabaseManager
from services.inventory_service import InventoryService
from gui.components.inventory_list import InventoryListComponent
from gui.components.inventory_form import InventoryFormComponent
from utils.logger import get_logger
from utils.ui_helpers import show_error, show_warning, show_question


class InventoryWidget(QWidget):
    """Widget for managing inventory items for a character/NPC."""

    # Signals
    item_created = pyqtSignal(int)  # item_id
    item_selected = pyqtSignal(int)  # item_id
    data_modified = pyqtSignal()  # Emitted when any item is created/updated/deleted

    def __init__(self, database_manager: DatabaseManager, module_id: int, parent_document_id: int):
        super().__init__()

        self.db_manager = database_manager
        self.inventory_service = InventoryService(database_manager)
        self.module_id = module_id
        self.parent_document_id = parent_document_id
        self.current_item: Optional[InventoryItem] = None
        self.items: List[InventoryItem] = []

        self.logger = get_logger('inventory_widget')

        self._setup_ui()
        self._connect_signals()
        self._load_items()

    def _setup_ui(self):
        """Setup the inventory widget UI."""
        layout = QHBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(5, 5, 5, 5)

        # Create splitter for resizable panels
        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left sidebar - inventory list component
        self.inventory_list_component = InventoryListComponent(self)
        self.inventory_list_component.setMinimumWidth(200)
        self.splitter.addWidget(self.inventory_list_component)

        # Right area - inventory form component
        self.inventory_form_component = InventoryFormComponent(self)
        self.splitter.addWidget(self.inventory_form_component)

        # Load saved splitter sizes or use defaults
        settings = QSettings("RPG Database Manager", "RPG Database Manager")
        saved_sizes = settings.value("inventory_widget_splitter", None)
        if saved_sizes:
            try:
                # Convert saved string list to int list
                sizes = [int(x) for x in saved_sizes]
                self.splitter.setSizes(sizes)
            except (ValueError, TypeError):
                # If conversion fails, use default sizes
                self.splitter.setSizes([350, 650])
        else:
            # Set initial sizes (list: 350px, form: remainder)
            self.splitter.setSizes([350, 650])

        # Connect splitter moved signal to save position
        self.splitter.splitterMoved.connect(self._save_splitter_position)

        layout.addWidget(self.splitter)

    def _save_splitter_position(self):
        """Save the current splitter position to settings."""
        settings = QSettings("RPG Database Manager", "RPG Database Manager")
        settings.setValue("inventory_widget_splitter", self.splitter.sizes())

    def _connect_signals(self):
        """Connect widget signals."""
        # Connect list component signals
        self.inventory_list_component.item_selected.connect(self._on_item_selected)
        self.inventory_list_component.refresh_requested.connect(self._load_items)
        self.inventory_list_component.new_item_requested.connect(self._on_new_item)

        # Connect form component signals
        self.inventory_form_component.data_changed.connect(self._on_form_data_changed)

    def _load_items(self):
        """Load inventory items for the current character/NPC."""
        try:
            self.logger.debug(f"Loading inventory items for parent_document_id: {self.parent_document_id}")

            self.items = self.inventory_service.get_inventory_items(
                module_id=self.module_id,
                parent_document_id=self.parent_document_id
            )
            self.logger.debug(f"Loaded {len(self.items)} inventory items")

            # Use the list component to display items
            self.inventory_list_component.set_items(self.items)

        except Exception as e:
            self.logger.error(f"Error loading inventory items: {e}")
            show_error(self, "Error", f"Failed to load inventory items: {e}")

    def _on_item_selected(self, item: InventoryItem):
        """Handle item selection from component."""
        if item:
            # Check if current item has unsaved changes
            if self.inventory_form_component.is_dirty():
                # Store target item info before save dialog
                target_item_id = item.id

                response = show_question(
                    self,
                    "Unsaved Changes",
                    "The current item has unsaved changes. Do you want to save them before switching?"
                )
                if response:
                    # Save current item
                    self._on_save_item()
                    # After save, continue to switch to the target item
                    self._select_item_by_id(target_item_id)
                    return
                # If user chose not to save, mark as clean and continue with switch
                self.inventory_form_component.mark_clean()

            self.current_item = item
            self.inventory_form_component.load_item(item)
            self.item_selected.emit(item.id)

    def _on_form_data_changed(self):
        """Handle form data changes."""
        # Data is automatically updated in the component's current_item

    def _on_new_item(self):
        """Handle new item creation."""
        # Check for unsaved changes
        if self.inventory_form_component.is_dirty():
            response = show_question(
                self,
                "Unsaved Changes",
                "Do you want to save the current item before creating a new one?"
            )
            if response:
                self._on_save_item()

        # Create new inventory item object
        new_item = InventoryItem(
            module_id=self.module_id,
            parent_document_id=self.parent_document_id,
            title="New Item",
            content="",
            item_type="misc",
            quantity=1,
            equipped=False
        )

        # Load into form
        self.current_item = new_item
        self.inventory_form_component.load_item(new_item)
        self.inventory_form_component.set_status("Creating new item - remember to save!")

    def _on_save_item(self):
        """Handle save item request."""
        if not self.current_item:
            show_warning(self, "No Item", "No item selected to save.")
            return

        try:
            # Get current form data
            title, content, item_type, quantity, equipped = self.inventory_form_component.get_item_data()

            if not title.strip():
                show_warning(self, "Missing Title", "Please enter an item name.")
                return

            # Update current item object
            self.current_item.title = title
            self.current_item.content = content
            self.current_item.item_type = item_type
            self.current_item.quantity = quantity
            self.current_item.equipped = equipped

            # Save to database
            if self.current_item.id:
                # Update existing item
                success = self.inventory_service.update_inventory_item(
                    item_id=self.current_item.id,
                    title=title,
                    content=content,
                    item_type=item_type,
                    quantity=quantity,
                    equipped=equipped
                )
                if success:
                    self.inventory_form_component.mark_clean()
                    self.inventory_form_component.set_status("Item saved successfully")
                    self._load_items()
                    self.data_modified.emit()
                    # Reselect the saved item
                    self._select_item_by_id(self.current_item.id)
                else:
                    show_error(self, "Save Failed", "Failed to update inventory item.")
            else:
                # Create new item
                item_id = self.inventory_service.create_inventory_item(
                    module_id=self.module_id,
                    parent_document_id=self.parent_document_id,
                    title=title,
                    content=content,
                    item_type=item_type,
                    quantity=quantity,
                    equipped=equipped
                )
                if item_id:
                    self.current_item.id = item_id
                    self.inventory_form_component.mark_clean()
                    self.inventory_form_component.set_status("Item created successfully")
                    self._load_items()
                    self.data_modified.emit()
                    self.item_created.emit(item_id)
                    # Select the newly created item
                    self._select_item_by_id(item_id)
                else:
                    show_error(self, "Save Failed", "Failed to create inventory item.")

        except Exception as e:
            self.logger.error(f"Error saving inventory item: {e}")
            show_error(self, "Error", f"Failed to save inventory item: {e}")

    def _show_context_menu(self, pos):
        """Show the text context menu."""
        from PyQt6.QtGui import QAction

        # Use FormattedTextEdit's context menu (includes Paste Without Formatting)
        menu = self.inventory_form_component.item_content.createStandardContextMenu()

        # Add paste without formatting from FormattedTextEdit
        menu.addSeparator()
        paste_plain_action = QAction("Paste Without Formatting", self)
        paste_plain_action.setShortcut("Ctrl+Shift+V")
        paste_plain_action.triggered.connect(self.inventory_form_component.item_content.paste_without_formatting)
        menu.addAction(paste_plain_action)

        # Show the menu at the cursor position
        menu.exec(self.inventory_form_component.item_content.mapToGlobal(pos))

    def _select_item_by_id(self, item_id: int):
        """Select an item by ID in the list."""
        self.inventory_list_component.select_item_by_id(item_id)

    def refresh_data(self):
        """Refresh all inventory data."""
        self._load_items()
