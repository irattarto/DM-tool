"""
Ability widget for RPG Database Manager - Ability item management for characters/NPCs.
"""

from typing import List, Optional

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QSplitter
from PyQt6.QtCore import pyqtSignal, Qt, QSettings

from models.ability_item import AbilityItem
from models.database import DatabaseManager
from services.ability_service import AbilityService
from gui.components.ability_list import AbilityListComponent
from gui.components.ability_form import AbilityFormComponent
from utils.logger import get_logger
from utils.ui_helpers import show_error, show_warning, show_question


class AbilityWidget(QWidget):
    """Widget for managing ability items for a character/NPC."""

    # Signals
    ability_created = pyqtSignal(int)  # ability_id
    ability_selected = pyqtSignal(int)  # ability_id
    data_modified = pyqtSignal()  # Emitted when any ability is created/updated/deleted

    def __init__(self, database_manager: DatabaseManager, module_id: int, parent_document_id: int):
        super().__init__()

        self.db_manager = database_manager
        self.ability_service = AbilityService(database_manager)
        self.module_id = module_id
        self.parent_document_id = parent_document_id
        self.current_ability: Optional[AbilityItem] = None
        self.abilities: List[AbilityItem] = []

        self.logger = get_logger('ability_widget')

        self._setup_ui()
        self._connect_signals()
        self._load_abilities()

    def _setup_ui(self):
        """Setup the ability widget UI."""
        layout = QHBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(5, 5, 5, 5)

        # Create splitter for resizable panels
        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left sidebar - ability list component
        self.ability_list_component = AbilityListComponent(self)
        self.ability_list_component.setMinimumWidth(200)
        self.splitter.addWidget(self.ability_list_component)

        # Right area - ability form component
        self.ability_form_component = AbilityFormComponent(self)
        self.splitter.addWidget(self.ability_form_component)

        # Load saved splitter sizes or use defaults
        settings = QSettings("RPG Database Manager", "RPG Database Manager")
        saved_sizes = settings.value("ability_widget_splitter", None)
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
        settings.setValue("ability_widget_splitter", self.splitter.sizes())

    def _connect_signals(self):
        """Connect widget signals."""
        # Connect list component signals
        self.ability_list_component.ability_selected.connect(self._on_ability_selected)
        self.ability_list_component.refresh_requested.connect(self._load_abilities)
        self.ability_list_component.new_ability_requested.connect(self._on_new_ability)

        # Connect form component signals
        self.ability_form_component.data_changed.connect(self._on_form_data_changed)

    def _load_abilities(self):
        """Load abilities for the current character/NPC."""
        try:
            self.logger.debug(f"Loading abilities for parent_document_id: {self.parent_document_id}")

            self.abilities = self.ability_service.get_abilities(
                module_id=self.module_id,
                parent_document_id=self.parent_document_id
            )
            self.logger.debug(f"Loaded {len(self.abilities)} abilities")

            # Use the list component to display abilities
            self.ability_list_component.set_abilities(self.abilities)

        except Exception as e:
            self.logger.error(f"Error loading abilities: {e}")
            show_error(self, "Error", f"Failed to load abilities: {e}")

    def _on_ability_selected(self, ability: AbilityItem):
        """Handle ability selection from component."""
        if ability:
            # Check if current ability has unsaved changes
            if self.ability_form_component.is_dirty():
                # Store target ability info before save dialog
                target_ability_id = ability.id

                response = show_question(
                    self,
                    "Unsaved Changes",
                    "The current ability has unsaved changes. Do you want to save them before switching?"
                )
                if response:
                    # Save current ability
                    self._on_save_ability()
                    # After save, continue to switch to the target ability
                    self._select_ability_by_id(target_ability_id)
                    return
                # If user chose not to save, mark as clean and continue with switch
                self.ability_form_component.mark_clean()

            self.current_ability = ability
            self.ability_form_component.load_ability(ability)
            self.ability_selected.emit(ability.id)

    def _on_form_data_changed(self):
        """Handle form data changes."""
        # Data is automatically updated in the component's current_ability

    def _on_new_ability(self):
        """Handle new ability creation."""
        # Check for unsaved changes
        if self.ability_form_component.is_dirty():
            response = show_question(
                self,
                "Unsaved Changes",
                "Do you want to save the current ability before creating a new one?"
            )
            if response:
                self._on_save_ability()

        # Create new ability object
        new_ability = AbilityItem(
            module_id=self.module_id,
            parent_document_id=self.parent_document_id,
            title="New Ability",
            content="",
            ability_type="skill"
        )

        # Load into form
        self.current_ability = new_ability
        self.ability_form_component.load_ability(new_ability)
        self.ability_form_component.set_status("Creating new ability - remember to save!")

    def _on_save_ability(self):
        """Handle save ability request."""
        if not self.current_ability:
            show_warning(self, "No Ability", "No ability selected to save.")
            return

        try:
            # Get current form data
            title, content, ability_type = self.ability_form_component.get_ability_data()

            if not title.strip():
                show_warning(self, "Missing Title", "Please enter an ability name.")
                return

            # Update current ability object
            self.current_ability.title = title
            self.current_ability.content = content
            self.current_ability.ability_type = ability_type

            # Save to database
            if self.current_ability.id:
                # Update existing ability
                success = self.ability_service.update_ability(
                    ability_id=self.current_ability.id,
                    title=title,
                    content=content,
                    ability_type=ability_type
                )
                if success:
                    self.ability_form_component.mark_clean()
                    self.ability_form_component.set_status("Ability saved successfully")
                    self._load_abilities()
                    self.data_modified.emit()
                    # Reselect the saved ability
                    self._select_ability_by_id(self.current_ability.id)
                else:
                    show_error(self, "Save Failed", "Failed to update ability.")
            else:
                # Create new ability
                ability_id = self.ability_service.create_ability(
                    module_id=self.module_id,
                    parent_document_id=self.parent_document_id,
                    title=title,
                    content=content,
                    ability_type=ability_type
                )
                if ability_id:
                    self.current_ability.id = ability_id
                    self.ability_form_component.mark_clean()
                    self.ability_form_component.set_status("Ability created successfully")
                    self._load_abilities()
                    self.data_modified.emit()
                    self.ability_created.emit(ability_id)
                    # Select the newly created ability
                    self._select_ability_by_id(ability_id)
                else:
                    show_error(self, "Save Failed", "Failed to create ability.")

        except Exception as e:
            self.logger.error(f"Error saving ability: {e}")
            show_error(self, "Error", f"Failed to save ability: {e}")

    def _show_context_menu(self, pos):
        """Show the text context menu."""
        from PyQt6.QtGui import QAction

        # Use FormattedTextEdit's context menu (includes Paste Without Formatting)
        menu = self.ability_form_component.ability_content.createStandardContextMenu()

        # Add paste without formatting from FormattedTextEdit
        menu.addSeparator()
        paste_plain_action = QAction("Paste Without Formatting", self)
        paste_plain_action.setShortcut("Ctrl+Shift+V")
        paste_plain_action.triggered.connect(self.ability_form_component.ability_content.paste_without_formatting)
        menu.addAction(paste_plain_action)

        # Show the menu at the cursor position
        menu.exec(self.ability_form_component.ability_content.mapToGlobal(pos))

    def _select_ability_by_id(self, ability_id: int):
        """Select an ability by ID in the list."""
        self.ability_list_component.select_ability_by_id(ability_id)

    def refresh_data(self):
        """Refresh all ability data."""
        self._load_abilities()
