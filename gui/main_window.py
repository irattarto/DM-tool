"""
Main window for RPG Database Manager desktop application.
"""

import json
from typing import Dict, Optional
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QListWidget,
    QListWidgetItem, QLineEdit, QPushButton,
    QLabel, QStatusBar, QMessageBox, QFileDialog,
    QTabWidget, QDialog, QInputDialog,
    QMenu, QGroupBox, QFormLayout, QTreeWidget, QTreeWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt, QPoint, QTimer
from PyQt6.QtGui import QAction

from config.settings import Settings
from config.entity_types import get_registry, CAP_FACTION_LINK, CAP_RACE_COLUMN
from gui.theme import set_props
from config.version import APP_NAME, APP_VERSION, get_version_string
from models.database import DatabaseManager
from models.document import Document
from services.parsing_service import ParsingService
from services.template_service import TemplateService
from services.image_service import ImageService
from services.session_service import SessionService
from utils.logger import get_logger
from utils.ui_helpers import show_error, show_warning, show_info, show_question
from utils.entity_metadata_extractor import extract_npc_metadata, extract_faction_metadata, format_date
from gui.settings_dialog import SettingsDialog
from gui.module_manager_dialog import ModuleManagerDialog
from gui.database_cleanup_dialog import DatabaseCleanupDialog
from gui.dialogs import (
    DocumentViewerWindow, TemplateEditorDialog
)


class MainWindow(QMainWindow):
    """
    Main window for the RPG Database Manager application.
    """

    def __init__(self, settings: Settings, database_manager: DatabaseManager):
        """
        Initialize main window.

        Args:
            settings: Application settings
            database_manager: Database manager instance
        """
        super().__init__()

        self.settings = settings
        self.db = database_manager
        self.logger = get_logger('main_window')

        # Initialize services
        self.parsing_service = ParsingService()
        self.template_service = TemplateService(database_manager)
        self.image_service = ImageService()
        self.image_service.cleanup_orphan_thumbnails()
        self.session_service = SessionService(database_manager)

        # Apply stored entity type customisations (labels, order, visibility, custom types)
        try:
            get_registry().load_overrides(self.db.get_entity_types())
        except Exception as e:
            self.logger.warning(f"Could not load entity type settings, using defaults: {e}")

        # Current state
        self.current_module_id: Optional[int] = None

        # Entity list sort state tracking (column, order) per entity type
        self.entity_sort_state: Dict[str, tuple[int, Qt.SortOrder]] = {}

        # Setup UI
        self._setup_window()
        self._create_menus()
        self._create_toolbar()
        self._setup_tab_widget()

        # Connect tab change signal to load templates when Templates tab is activated
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

        # Show module selection dialog first
        self.logger.debug("Showing campaign selection dialog...")
        self._show_module_selection_dialog()

        # Apply settings
        self._apply_settings()

    def _setup_window(self):
        """Setup window properties."""
        self.setWindowTitle(get_version_string())
        self.setMinimumSize(1000, 700)

        # Restore window geometry from settings
        if self.settings.window.size.isValid():
            self.resize(self.settings.window.size)
        position = self.settings.window.position
        if position != QPoint(0, 0):
            # Ignore a saved position that is off every screen (monitor unplugged, resolution change)
            from PyQt6.QtGui import QGuiApplication
            frame = self.frameGeometry()
            frame.moveTo(position)
            if any(screen.availableGeometry().intersects(frame) for screen in QGuiApplication.screens()):
                self.move(position)
        if self.settings.window.is_maximized:
            self.setWindowState(self.windowState() | Qt.WindowState.WindowMaximized)
        if self.settings.window.is_fullscreen:
            self._was_maximized_before_fullscreen = self.settings.window.is_maximized
            self.setWindowState(self.windowState() | Qt.WindowState.WindowFullScreen)

    def _set_fullscreen(self, enabled: bool):
        """Toggle fullscreen; leaving it returns to the previous normal/maximised state."""
        if enabled == self.isFullScreen():
            return
        if enabled:
            self._was_maximized_before_fullscreen = self.isMaximized()
            self.showFullScreen()
        elif getattr(self, '_was_maximized_before_fullscreen', False):
            self.showMaximized()
        else:
            self.showNormal()

    def changeEvent(self, event):
        super().changeEvent(event)
        # Keep the menu check in sync when the window manager changes the state (e.g. Esc/Alt+Enter)
        action = getattr(self, 'fullscreen_action', None)
        if action is not None and action.isChecked() != self.isFullScreen():
            action.blockSignals(True)
            action.setChecked(self.isFullScreen())
            action.blockSignals(False)

    def _create_menus(self):
        """Create menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        new_module_action = QAction("&New Campaign", self)
        new_module_action.triggered.connect(self._on_new_module)
        file_menu.addAction(new_module_action)

        open_module_action = QAction("&Change Campaign", self)
        open_module_action.triggered.connect(self._on_open_module)
        file_menu.addAction(open_module_action)

        manage_modules_action = QAction("&Manage Campaigns", self)
        manage_modules_action.triggered.connect(self._on_manage_modules)
        file_menu.addAction(manage_modules_action)

        file_menu.addSeparator()

        self.import_html_module_action = QAction("&Import HTML Module...", self)
        self.import_html_module_action.setStatusTip(
            "Import an adventure module (HTML) into the current campaign as a module with sessions, NPCs, locations and items")
        self.import_html_module_action.triggered.connect(self._on_import_html_module)
        file_menu.addAction(self.import_html_module_action)

        file_menu.addSeparator()

        database_action = QAction("&Database", self)
        database_action.triggered.connect(self._on_database)
        file_menu.addAction(database_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Edit menu
        edit_menu = menubar.addMenu("&Edit")

        preferences_action = QAction("&Preferences", self)
        preferences_action.triggered.connect(self._on_settings)
        edit_menu.addAction(preferences_action)

        # View menu
        view_menu = menubar.addMenu("&View")
        self.fullscreen_action = QAction("&Full Screen", self)
        self.fullscreen_action.setShortcut("F11")
        self.fullscreen_action.setCheckable(True)
        self.fullscreen_action.setChecked(self.isFullScreen())
        self.fullscreen_action.toggled.connect(self._set_fullscreen)
        view_menu.addAction(self.fullscreen_action)

        # Tools menu
        tools_menu = menubar.addMenu("&Tools")

        # Name Generator
        name_generator_action = QAction("&Name Generator", self)
        name_generator_action.setStatusTip("Generate character/entity names from embedded name lists")
        name_generator_action.triggered.connect(self._on_name_generator)
        tools_menu.addAction(name_generator_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

    def _create_toolbar(self):
        """Create main toolbar."""
        toolbar = self.addToolBar("Main")
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)

        # Module management
        self.module_label = QLabel("Current Campaign: None")
        self.module_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        toolbar.addWidget(self.module_label)

        toolbar.addSeparator()

        # Document creation is now handled in individual entity tabs

        # Update module label when module changes
        self.module_label.setText(f"Current Campaign: {self.current_module_id or 'None'}")
        # The main layout is now handled by the tab widget in _setup_tab_widget
        # Status bar is created there too

    def _on_session_created(self, session_id: int):
        """Handle session creation."""
        self.status_bar.showMessage(f"Created session (ID: {session_id})")

    def _update_session_widget_module(self, module_id: int):
        """Update the session widget with a new campaign ID."""
        if hasattr(self, 'session_widget') and self.session_widget is not None:
            self.session_widget.set_module_id(module_id)

    def _on_session_document_selected(self, session_id: int):
        """Handle session document selection - the session widget handles display internally."""
        # The session widget now handles displaying session content internally
        # No need to open a popup window since the content is shown in the main interface
        self.logger.debug(f"Session {session_id} selected - content displayed in session widget")


    def _setup_tab_widget(self):
        """Setup the main tab widget for different application areas."""
        # Create central tab widget
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)

        # Sessions tab (first tab for quick access during gameplay)
        self.sessions_tab = QWidget()
        self._setup_sessions_tab()
        self.tab_widget.addTab(self.sessions_tab, "Sessions")

        # Entity-specific tabs (built from the entity type registry)
        self._setup_entity_tabs()

        # Templates tab
        self.templates_tab = QWidget()
        self._setup_templates_tab()
        self.tab_widget.addTab(self.templates_tab, "Templates")


        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    def _setup_entity_tabs(self):
        """Setup (or rebuild) one list tab per visible entity type, right after Sessions."""
        registry = get_registry()
        self.entity_types = {key: registry.plural(key) for key in registry.keys_for('tabs')}

        # Remember which generic entity tab is selected so a rebuild keeps the user's place
        selected_key = None
        old_tabs = getattr(self, 'entity_tabs', {})
        current_widget = self.tab_widget.currentWidget()
        for key, tab in old_tabs.items():
            if tab is current_widget:
                selected_key = key

        insert_at = self.tab_widget.indexOf(self.sessions_tab) + 1
        for tab in old_tabs.values():
            index = self.tab_widget.indexOf(tab)
            if index >= 0:
                self.tab_widget.removeTab(index)
            tab.deleteLater()

        self.entity_tabs = {}
        self.entity_lists = {}
        self.entity_search_widgets = {}

        for offset, (entity_type, display_name) in enumerate(self.entity_types.items()):
            tab = QWidget()
            self.entity_tabs[entity_type] = tab
            self.tab_widget.insertTab(insert_at + offset, tab, display_name)
            self._setup_entity_tab(tab, entity_type)

        if selected_key in self.entity_tabs:
            self.tab_widget.setCurrentWidget(self.entity_tabs[selected_key])

    def _on_entity_types_changed(self):
        """Entity types were edited in Settings: rebuild tabs and refresh dependent widgets."""
        self._setup_entity_tabs()

        if self.current_module_id:
            self._load_documents()

    def _entity_columns(self, entity_type: str):
        """Column labels and default widths for an entity type's list, from its capabilities."""
        registry = get_registry()
        if registry.has_capability(entity_type, CAP_FACTION_LINK):
            labels, widths = (['Name', 'Race', 'Faction', 'Created Date', 'Modified Date'],
                              [200, 120, 150, 150, 150])
        elif registry.has_capability(entity_type, CAP_RACE_COLUMN):
            labels, widths = ['Name', 'Race', 'Created Date', 'Modified Date'], [250, 120, 150, 150]
        else:
            labels, widths = ['Name', 'Created Date', 'Modified Date'], [300, 150, 150]
        if entity_type != 'module':
            # appended last so saved sort/width preferences (by column index) keep working
            labels, widths = labels + ['Module'], widths + [150]
        return labels, widths

    def _module_title_for(self, doc: dict) -> str:
        """Title of the adventure module an entity was imported from, or ''."""
        try:
            module_doc_id = json.loads(doc['metadata']).get('module_doc_id') if doc.get('metadata') else None
        except (TypeError, ValueError, AttributeError):
            return ''
        if module_doc_id is None:
            return ''
        cache = self.__dict__.setdefault('_module_title_cache', {})
        if module_doc_id not in cache:
            module_doc = self.db.get_document(module_doc_id)
            cache[module_doc_id] = module_doc['title'] if module_doc else ''
        return cache[module_doc_id]

    def _fill_entity_row(self, item: QTreeWidgetItem, doc: dict, entity_type: str,
                         valid_faction_names: set) -> None:
        """Fill one list row; the columns depend on the type's capabilities."""
        registry = get_registry()
        created_date = format_date(doc.get('created_date'))
        modified_date = format_date(doc.get('modified_date'))
        item.setText(0, doc.get('title', 'Untitled'))

        if registry.has_capability(entity_type, CAP_FACTION_LINK):
            # Faction: metadata faction_id first, then validated text extraction
            faction_name = ''
            if doc.get('metadata'):
                try:
                    faction_id = json.loads(doc['metadata']).get('faction_id')
                    if faction_id is not None:
                        faction_doc = self.db.get_document(faction_id)
                        if faction_doc:
                            faction_name = faction_doc['title']
                except Exception as e:
                    self.logger.warning(f"Failed to parse metadata for {entity_type}: {e}")

            extracted = extract_npc_metadata(doc.get('content', ''))
            if not faction_name:
                extracted_faction = extracted.get('faction')
                if extracted_faction and extracted_faction.lower() in valid_faction_names:
                    faction_name = extracted_faction

            values = [extracted.get('race') or '', faction_name, created_date, modified_date]
        elif registry.has_capability(entity_type, CAP_RACE_COLUMN):
            race = extract_faction_metadata(doc.get('content', '')).get('race') or ''
            values = [race, created_date, modified_date]
        else:
            values = [created_date, modified_date]
        if entity_type != 'module':
            values.append(self._module_title_for(doc))

        for column, value in enumerate(values, start=1):
            item.setText(column, value)

    def _setup_entity_tab(self, tab: QWidget, entity_type: str):
        """Setup a specific entity type tab."""
        layout = QVBoxLayout(tab)

        # Toolbar for this entity type
        toolbar_layout = QHBoxLayout()

        # Filter (for this entity type only)
        filter_layout = QHBoxLayout()
        filter_label = QLabel(f"Filter {get_registry().label(entity_type)}:")
        filter_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        filter_layout.addWidget(filter_label)

        search_edit = QLineEdit()
        search_edit.setPlaceholderText(f"Search {entity_type}...")
        search_edit.textChanged.connect(lambda text, et=entity_type: self._on_entity_search(text, et))
        filter_layout.addWidget(search_edit)

        toolbar_layout.addLayout(filter_layout)

        # Post name + primary picture cards to Discord (kept on the left, away from Delete)
        from gui.discord_actions import DISCORD_ENTITY_TYPES
        if entity_type in DISCORD_ENTITY_TYPES:
            discord_btn = QPushButton("Send to Discord...")
            discord_btn.setToolTip(f"Choose {get_registry().label(entity_type)} to post to a Discord channel "
                                   "(name and primary picture)")
            discord_btn.clicked.connect(lambda checked, et=entity_type: self._on_send_entities_to_discord(et))
            toolbar_layout.addWidget(discord_btn)
            self.entity_discord_buttons = getattr(self, 'entity_discord_buttons', {})
            self.entity_discord_buttons[entity_type] = discord_btn

        toolbar_layout.addStretch()

        # New document buttons for this entity type
        new_with_template_btn = QPushButton(f"New {get_registry().label(entity_type)}")
        new_with_template_btn.setToolTip(f"Create new {entity_type} with default template")
        new_with_template_btn.clicked.connect(lambda checked, et=entity_type: self._on_new_entity_document(et, use_template=True))
        toolbar_layout.addWidget(new_with_template_btn)

        new_blank_btn = QPushButton(f"New Blank {get_registry().label(entity_type)}")
        new_blank_btn.setToolTip(f"Create blank {entity_type} document")
        new_blank_btn.clicked.connect(lambda checked, et=entity_type: self._on_new_entity_document(et, use_template=False))
        toolbar_layout.addWidget(new_blank_btn)

        # Delete button
        delete_btn = QPushButton("Delete")
        delete_btn.setToolTip(f"Delete selected {entity_type}")
        delete_btn.clicked.connect(lambda checked, et=entity_type: self._on_delete_entity_document(et))
        toolbar_layout.addWidget(delete_btn)

        layout.addLayout(toolbar_layout)

        # Document tree for this entity type (multi-column list)
        doc_tree = QTreeWidget()
        doc_tree.setRootIsDecorated(False)  # No tree hierarchy, just a flat list
        doc_tree.setAlternatingRowColors(True)  # Better readability

        # Columns come from the type's capabilities
        column_labels, default_widths = self._entity_columns(entity_type)
        doc_tree.setColumnCount(len(column_labels))
        doc_tree.setHeaderLabels(column_labels)

        # Enable sorting
        doc_tree.setSortingEnabled(True)

        # Load sort preference from settings or use default
        saved_column, saved_order_str = self.settings.get_entity_sort_preference(entity_type)
        saved_order = Qt.SortOrder.AscendingOrder if saved_order_str == 'asc' else Qt.SortOrder.DescendingOrder

        # Set sort based on saved preference
        doc_tree.sortByColumn(saved_column, saved_order)

        # Initialize sort state for this entity type
        self.entity_sort_state[entity_type] = (saved_column, saved_order)

        # Connect to sort indicator changed signal to track user's sort preference
        header = doc_tree.header()
        header.sortIndicatorChanged.connect(lambda col, order, et=entity_type: self._on_sort_changed(et, col, order))

        # Configure column resizing - Interactive allows user resizing
        for column in range(len(column_labels)):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)

        # Restore saved column widths or use defaults
        saved_widths = self.settings.get_column_widths(f'entity_{entity_type}')
        widths = saved_widths if saved_widths and len(saved_widths) == len(column_labels) else default_widths
        for column, width in enumerate(widths):
            header.resizeSection(column, width)

        # Connect to save column widths when resized
        header.sectionResized.connect(lambda idx, old, new, et=entity_type: self._on_entity_column_resized(et, idx, old, new))

        # Connect double-click
        doc_tree.itemDoubleClicked.connect(lambda item, col, et=entity_type: self._on_entity_tree_item_selected(item, et))

        if entity_type in DISCORD_ENTITY_TYPES:
            doc_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            doc_tree.customContextMenuRequested.connect(
                lambda pos, et=entity_type: self._on_entity_context_menu(et, pos))

        self.entity_lists[entity_type] = doc_tree
        layout.addWidget(doc_tree)

        # Store search widget for this entity type
        self.entity_search_widgets = getattr(self, 'entity_search_widgets', {})
        self.entity_search_widgets[entity_type] = search_edit


    def _setup_sessions_tab(self):
        """Setup the sessions tab."""
        layout = QVBoxLayout(self.sessions_tab)

        # Create session widget immediately to avoid blank display on first start
        from gui.session_widget import SessionWidget
        module_id = self.current_module_id if self.current_module_id is not None else 1
        self.session_widget = SessionWidget(self.session_service, module_id, self.template_service, self.settings)
        self.session_widget.session_created.connect(self._on_session_created)
        self.session_widget.session_selected.connect(self._on_session_document_selected)
        layout.addWidget(self.session_widget)


    def _setup_templates_tab(self):
        """Setup the templates editing tab."""
        layout = QVBoxLayout(self.templates_tab)

        # Templates toolbar
        templates_toolbar = QHBoxLayout()

        # Show all templates (no filtering needed)
        templates_label = QLabel("All Templates:")
        templates_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        templates_toolbar.addWidget(templates_label)
        templates_toolbar.addStretch()

        # Template management buttons
        self.new_template_btn = QPushButton("New Template")
        self.new_template_btn.clicked.connect(self._on_new_template)
        templates_toolbar.addWidget(self.new_template_btn)

        self.edit_template_btn = QPushButton("Edit Template")
        self.edit_template_btn.clicked.connect(self._on_edit_template)
        templates_toolbar.addWidget(self.edit_template_btn)

        self.delete_template_btn = QPushButton("Delete Template")
        self.delete_template_btn.clicked.connect(self._on_delete_template)
        templates_toolbar.addWidget(self.delete_template_btn)

        layout.addLayout(templates_toolbar)

        # Templates list
        self.templates_list = QListWidget()
        self.templates_list.itemDoubleClicked.connect(self._on_template_selected)
        layout.addWidget(self.templates_list)



    def _load_templates(self):
        """Load templates for the templates tab."""
        try:
            self.logger.debug("Loading templates from database...")
            # Load all templates (no filtering)
            templates = self.template_service.get_templates()
            self.logger.debug(f"Found {len(templates)} templates")

            for i, template in enumerate(templates):
                self.logger.debug(f"Template {i+1}: {template.template_name} ({template.entity_type}, default={template.is_default})")

            self.templates_list.clear()
            for template in templates:
                item_text = f"{get_registry().label(template.entity_type)}: {template.template_name}"
                if template.is_default:
                    item_text += " (Default)"

                item = QListWidgetItem(item_text)
                item.setData(Qt.ItemDataRole.UserRole, template)
                self.templates_list.addItem(item)

            if not templates:
                self.logger.warning("No templates found in database")
                self.templates_list.addItem("No templates found - use 'New Template' to create some")

        except Exception as e:
            self.logger.error(f"Error loading templates: {e}")
            self.templates_list.clear()
            self.templates_list.addItem(f"Error loading templates: {e}")


    def _on_new_template(self):
        """Handle new template creation."""
        try:
            dialog = TemplateEditorDialog(self.template_service, parent=self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self._load_templates()  # Refresh the template list
                self.status_bar.showMessage("Template created successfully")
        except Exception as e:
            show_error(self, "Error", f"Failed to create template: {e}")

    def _on_edit_template(self):
        """Handle template editing."""
        current_item = self.templates_list.currentItem()
        if not current_item:
            show_info(self, "No Selection", "Please select a template to edit.")
            return

        try:
            template = current_item.data(Qt.ItemDataRole.UserRole)
            if template:
                dialog = TemplateEditorDialog(self.template_service, template, parent=self)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    self._load_templates()  # Refresh the template list
                    self.status_bar.showMessage(f"Template '{template.template_name}' updated successfully")
        except Exception as e:
            show_error(self, "Error", f"Failed to edit template: {e}")

    def _on_template_selected(self):
        """Handle template selection (double-click)."""
        current_item = self.templates_list.currentItem()
        if not current_item:
            return

        try:
            template = current_item.data(Qt.ItemDataRole.UserRole)
            if template:
                # Open template for editing
                dialog = TemplateEditorDialog(self.template_service, template, parent=self)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    self._load_templates()  # Refresh the template list
                    self.status_bar.showMessage(f"Template '{template.template_name}' updated successfully")
        except Exception as e:
            show_error(self, "Error", f"Failed to edit template: {e}")

    def _on_delete_template(self):
        """Handle template deletion."""
        current_item = self.templates_list.currentItem()
        if not current_item:
            show_info(self, "No Selection", "Please select a template to delete.")
            return

        try:
            template = current_item.data(Qt.ItemDataRole.UserRole)
            if template:
                # Check if it's a default template
                if template.is_default:
                    show_warning(
                        self,
                        "Cannot Delete Default Template",
                        f"Template '{template.template_name}' is a default template and cannot be deleted."
                    )
                    return

                # Confirm deletion
                if show_question(
                    self,
                    "Confirm Deletion",
                    f"Are you sure you want to delete template '{template.template_name}'?\n\nThis action cannot be undone."
                ):
                    # Delete template using template service
                    success = self.template_service.delete_template(template.id)

                    if success:
                        show_info(
                            self,
                            "Template Deleted",
                            f"Template '{template.template_name}' has been deleted successfully."
                        )
                        # Refresh the template list
                        self._load_templates()
                        self.status_bar.showMessage(f"Template '{template.template_name}' deleted successfully")
                    else:
                        show_error(
                            self,
                            "Deletion Failed",
                            f"Failed to delete template '{template.template_name}'.\n\n"
                            "Please check the logs for more details."
                        )
        except Exception as e:
            show_error(self, "Error", f"Failed to delete template: {e}")


    def _connect_signals(self):
        """Connect widget signals."""
        # Signals are now connected in the individual tab setup methods

    def _show_module_selection_dialog(self):
        """Show campaign selection dialog at startup."""
        try:
            self.logger.debug("Checking available campaigns...")
            modules = self.db.get_modules()
            self.logger.debug(f"Found {len(modules)} existing campaigns")

            if not modules:
                # No existing modules - ask user to create the first one
                self._create_initial_module()
                return

            # Check if there's a last used module ID in settings
            last_module_id = self.settings.get_last_module_id()
            self.logger.debug(f"Last used campaign ID from settings: {last_module_id}")

            if last_module_id is not None:
                # Try to find the module in the list
                last_module = next((m for m in modules if m['id'] == last_module_id), None)

                if last_module:
                    # Module exists - auto-load it without showing dialog
                    self.logger.info(f"Auto-loading last used campaign: {last_module['name']} (ID: {last_module_id})")
                    self.current_module_id = last_module_id
                    self._update_window_title()
                    self._load_documents()
                    self._update_session_widget_module(self.current_module_id)
                    self.status_bar.showMessage(f"Loaded campaign: {last_module['name']}")
                    return
                else:
                    # Last module ID doesn't exist anymore - clear it and show dialog
                    self.logger.warning(f"Last used campaign ID {last_module_id} not found - showing selection dialog")
                    self.settings.set_last_module_id(None)

            # No last module or it doesn't exist - show selection dialog
            self._show_module_choice_dialog(modules)

        except Exception as e:
            self.logger.error(f"Error in campaign selection dialog: {e}")
            show_error(self, "Error", f"Failed to load campaigns: {e}")

    def _create_initial_module(self):
        """Create the initial campaign when none exist."""
        module_name, ok = QInputDialog.getText(
            self,
            "Create First Campaign",
            "No campaigns found. Please enter a name for your first campaign:",
            text="My Campaign"
        )

        if ok and module_name.strip():
            try:
                module_id = self.db.create_module(module_name.strip())
                self.current_module_id = module_id

                # Save the initial module ID to settings for auto-load next time
                self.settings.set_last_module_id(module_id)

                self._update_window_title()
                self._load_documents()
                self.status_bar.showMessage(f"Created and loaded campaign: {module_name}")
                self.logger.debug(f"Created initial campaign: {module_name} (ID: {module_id})")
            except Exception as e:
                self.logger.error(f"Error creating initial campaign: {e}")
                show_error(self, "Error", f"Failed to create campaign: {e}")
        else:
            # User cancelled or entered empty name - try again or exit
            if show_question(
                self,
                "Campaign Required",
                "A campaign is required to use RPG Database Manager.\n\nWould you like to try again?"
            ):
                self._create_initial_module()
            else:
                self.logger.info("User declined to create campaign - closing application")
                self.close()

    def _show_module_choice_dialog(self, modules):
        """Show dialog allowing user to select existing campaign or create new one."""
        # Create custom dialog for module selection
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Campaign")
        dialog.setModal(True)
        dialog.resize(400, 300)

        layout = QVBoxLayout(dialog)

        # Instructions
        layout.addWidget(QLabel("Choose a campaign to work with:"))

        # Module list
        module_list = QListWidget()
        for module in modules:
            item_text = f"{module['name']} (ID: {module['id']})"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, module)
            module_list.addItem(item)

        if modules:
            module_list.setCurrentRow(0)  # Select first module by default

        # Connect double-click to select and start
        module_list.itemDoubleClicked.connect(lambda: self._on_module_selected(dialog, module_list))

        layout.addWidget(module_list)

        # Buttons
        button_layout = QHBoxLayout()

        select_btn = QPushButton("Select Campaign")
        select_btn.clicked.connect(lambda: self._on_module_selected(dialog, module_list))
        button_layout.addWidget(select_btn)

        new_btn = QPushButton("Create New Campaign")
        new_btn.clicked.connect(lambda: self._on_create_new_module_dialog(dialog, module_list))
        button_layout.addWidget(new_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

        # Show dialog and handle result
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Module selection handled in the button callbacks
            pass
        else:
            # User cancelled - ask if they want to exit
            if show_question(
                self,
                "Exit Application",
                "No campaign selected. Do you want to exit?"
            ):
                self.close()
            else:
                # Try showing the dialog again
                self._show_module_choice_dialog(modules)

    def _on_module_selected(self, dialog, module_list):
        """Handle campaign selection from dialog."""
        current_item = module_list.currentItem()
        if current_item:
            module = current_item.data(Qt.ItemDataRole.UserRole)
            self.current_module_id = module['id']

            # Save the selected module ID to settings for auto-load next time
            self.settings.set_last_module_id(module['id'])

            self._update_window_title()
            self._load_documents()
            self._update_session_widget_module(self.current_module_id)
            self.status_bar.showMessage(f"Loaded campaign: {module['name']}")
            self.logger.debug(f"Selected existing campaign: {module['name']} (ID: {module['id']})")
            dialog.accept()

    def _on_create_new_module_dialog(self, dialog, module_list):
        """Handle create new campaign from dialog."""
        module_name, ok = QInputDialog.getText(
            dialog,
            "Create New Campaign",
            "Enter name for new campaign:"
        )

        if ok and module_name.strip():
            try:
                module_id = self.db.create_module(module_name.strip())
                self.current_module_id = module_id

                # Save the new module ID to settings for auto-load next time
                self.settings.set_last_module_id(module_id)

                self._update_window_title()
                self._load_documents()
                self._update_session_widget_module(self.current_module_id)
                self.status_bar.showMessage(f"Created and loaded campaign: {module_name}")
                self.logger.debug(f"Created new campaign: {module_name} (ID: {module_id})")
                dialog.accept()
            except Exception as e:
                self.logger.error(f"Error creating new campaign: {e}")
                show_error(dialog, "Error", f"Failed to create campaign: {e}")
        # If user cancelled or entered empty name, dialog stays open

    def _load_modules(self):
        """Load available campaigns."""
        try:
            self.logger.debug("Loading campaigns...")
            modules = self.db.get_modules()
            self.logger.debug(f"Found {len(modules)} campaigns: {[m['name'] for m in modules]}")

            # Update window title to show current module
            if modules:
                if self.current_module_id is None:
                    self.current_module_id = modules[0]['id']
                    self.logger.debug(f"Set current_module_id to: {self.current_module_id}")
                self._update_window_title()
                self.logger.debug(f"Loading documents for campaign {self.current_module_id}")
                self._load_documents()
            else:
                self.logger.debug("No campaigns found")
                self.status_bar.showMessage("No campaigns found. Create a new campaign to get started.")

        except Exception as e:
            self.logger.error(f"Error loading campaigns: {e}")
            show_error(self, "Error", f"Failed to load campaigns: {e}")

    def _load_documents(self):
        """Load documents for current campaign."""
        if not self.current_module_id:
            return

        try:
            # Load documents for each entity type
            for entity_type in self.entity_types.keys():
                self._load_entity_documents(entity_type)



        except Exception as e:
            self.logger.error(f"Error loading documents: {e}")

    def _load_entity_documents(self, entity_type: str):
        """Load documents for a specific entity type."""
        if not self.current_module_id:
            return

        try:
            self.logger.debug(f"Loading {entity_type} documents for campaign {self.current_module_id}")
            self._module_title_cache = {}
            documents = self.db.get_documents(self.current_module_id, entity_type)
            self.logger.debug(f"Loaded {len(documents)} {entity_type} documents")

            # For NPCs, get valid faction names for validation
            valid_faction_names = set()
            if get_registry().has_capability(entity_type, CAP_FACTION_LINK):
                factions = self.db.get_documents(self.current_module_id, 'faction')
                valid_faction_names = {f['title'].lower() for f in factions}
                self.logger.debug(f"Loaded {len(valid_faction_names)} valid faction names for NPC validation")

            # Update the appropriate tree widget
            if entity_type in self.entity_lists:
                doc_tree = self.entity_lists[entity_type]

                # Save current selection and scroll position before clearing
                selected_doc_id = None
                current_item = doc_tree.currentItem()
                if current_item:
                    doc_data = current_item.data(0, Qt.ItemDataRole.UserRole)
                    if doc_data:
                        selected_doc_id = doc_data.get('id')

                # Save scroll position
                scroll_bar = doc_tree.verticalScrollBar()
                scroll_position = scroll_bar.value() if scroll_bar else 0

                # Temporarily disable sorting for faster insertion
                doc_tree.setSortingEnabled(False)
                doc_tree.clear()

                for doc in documents:
                    item = QTreeWidgetItem()
                    self._fill_entity_row(item, doc, entity_type, valid_faction_names)

                    # Store full document data in item
                    item.setData(0, Qt.ItemDataRole.UserRole, doc)

                    doc_tree.addTopLevelItem(item)

                # Re-enable sorting and restore previous sort state
                doc_tree.setSortingEnabled(True)

                # Get saved sort state for this entity type, default to Name ascending
                sort_column, sort_order = self.entity_sort_state.get(
                    entity_type, (0, Qt.SortOrder.AscendingOrder)
                )
                doc_tree.sortByColumn(sort_column, sort_order)

                # Restore previous selection if it still exists
                # Use QTimer to ensure this happens after sorting completes
                def restore_position():
                    if selected_doc_id is not None:
                        for i in range(doc_tree.topLevelItemCount()):
                            item = doc_tree.topLevelItem(i)
                            doc_data = item.data(0, Qt.ItemDataRole.UserRole)
                            if doc_data and doc_data.get('id') == selected_doc_id:
                                doc_tree.setCurrentItem(item)
                                doc_tree.scrollToItem(item)
                                self.logger.debug(f"Restored selection to document ID {selected_doc_id}")
                                break

                    # Restore scroll position
                    if scroll_bar and selected_doc_id is None:
                        # Only restore scroll if no item was selected (otherwise scrollToItem handles it)
                        scroll_bar.setValue(scroll_position)
                        self.logger.debug(f"Restored scroll position to {scroll_position}")

                # Delay restoration to ensure it happens after sorting
                QTimer.singleShot(0, restore_position)

        except Exception as e:
            self.logger.error(f"Error loading {entity_type} documents: {e}")

    def _on_new_module(self):
        """Handle new campaign creation."""
        name, ok = QInputDialog.getText(self, "New Campaign", "Campaign Name:")
        if ok and name:
            try:
                module_id = self.db.create_module(name)
                self.current_module_id = module_id

                # Save the new module ID to settings for auto-load next time
                self.settings.set_last_module_id(module_id)

                self._update_window_title()
                self._load_documents()
                # Update session widget with new module
                self._update_session_widget_module(module_id)
                self.status_bar.showMessage(f"Created campaign: {name}")

            except Exception as e:
                show_error(self, "Error", f"Failed to create campaign: {e}")

    def _on_open_module(self):
        """Handle campaign opening."""
        try:
            modules = self.db.get_modules()
            if not modules:
                show_info(self, "No Campaigns", "No campaigns available.")
                return

            # Simple module selection (could be enhanced with a proper dialog)
            module_names = [f"{m['name']} (ID: {m['id']})" for m in modules]

            module_name, ok = QInputDialog.getItem(
                self, "Change Campaign", "Select Campaign:", module_names, 0, False
            )

            if ok and module_name:
                # Extract module ID from selection
                for module in modules:
                    if f"{module['name']} (ID: {module['id']})" == module_name:
                        self.current_module_id = module['id']

                        # Save the selected module ID to settings for auto-load next time
                        self.settings.set_last_module_id(module['id'])

                        self._update_window_title()
                        self._load_documents()
                                # Update session widget with new module
                        self._update_session_widget_module(module['id'])
                        break

        except Exception as e:
            show_error(self, "Error", f"Failed to open campaign: {e}")

    def _on_manage_modules(self):
        """Open the Campaign Manager dialog."""
        try:
            dialog = ModuleManagerDialog(self.db, self)
            dialog.module_changed.connect(self._on_module_changed)
            dialog.exec()
        except Exception as e:
            self.logger.error(f"Error opening campaign manager: {e}", exc_info=True)
            show_error(self, "Error", f"Failed to open campaign manager: {e}")

    def _on_import_html_module(self):
        """Import an HTML adventure module into the current campaign (preview first)."""
        if not self.current_module_id:
            show_warning(self, "No Campaign", "Select or create a campaign before importing a module.")
            return
        try:
            from gui.dialogs.html_module_import_dialog import HtmlModuleImportDialog
            from services.html_module_import_service import HtmlModuleImportService
            from services.html_module_parser import parse_file

            start_dir = self.settings.get_custom_setting("last_html_module_dir", "") or ""
            path, _ = QFileDialog.getOpenFileName(
                self, "Import HTML Module", start_dir, "HTML modules (*.html *.htm);;All files (*)")
            if not path:
                return
            self.settings.set_custom_setting("last_html_module_dir", str(Path(path).parent))

            parsed = parse_file(path)
            if not parsed.entities and not parsed.sessions:
                show_warning(self, "Nothing to import",
                             "No NPCs, locations, items or scenes were recognised in this file.")
                return
            campaign = self.db.get_module(self.current_module_id) or {}
            service = HtmlModuleImportService(self.db, self.image_service)
            dialog = HtmlModuleImportDialog(service, parsed, self.current_module_id,
                                            campaign.get('name', ''), self)
            if dialog.exec() != QDialog.DialogCode.Accepted or dialog.import_result is None:
                return
            result = dialog.import_result
            self._load_documents()
            if hasattr(self, 'session_widget'):
                self.session_widget.refresh_data()
            message = (f"Created {result.created}, updated {result.updated}, linked {result.links}, "
                       f"pictures {result.images}.")
            if result.errors:
                show_warning(self, "Import finished with problems",
                             message + "\n\n" + "\n".join(result.errors[:10]))
            else:
                show_info(self, "Import complete", message)
        except Exception as e:
            self.logger.error(f"Error importing HTML module: {e}", exc_info=True)
            show_error(self, "Error", f"Failed to import campaign: {e}")

    def _on_module_changed(self):
        """Handle campaign changes from Campaign Manager."""
        try:
            # Reload modules list and update UI
            self._load_modules()
            self._update_window_title()
            self.logger.info("Campaign list refreshed after changes")
        except Exception as e:
            self.logger.error(f"Error refreshing after campaign change: {e}", exc_info=True)

    def _on_database(self):
        """Open database management dialog."""
        try:
            from gui.database_dialog import DatabaseDialog
            dialog = DatabaseDialog(self.db, self.image_service, self)
            dialog.exec()
        except Exception as e:
            self.logger.error(f"Error opening database dialog: {e}", exc_info=True)
            show_error(self, "Error", f"Failed to open database dialog: {e}")

    def _on_database_cleanup(self):
        """Open the Database Cleanup dialog."""
        try:
            # Warning before opening
            reply = show_question(
                self,
                "Database Cleanup",
                "This tool allows you to permanently delete inactive campaigns.\n\n"
                "This action cannot be undone. Do you want to continue?"
            )

            if reply:
                dialog = DatabaseCleanupDialog(self.db, ImageService(), self)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    # Reload modules after cleanup
                    self._load_modules()
                    self._update_window_title()

        except Exception as e:
            self.logger.error(f"Error opening database cleanup: {e}", exc_info=True)
            show_error(self, "Error", f"Failed to open database cleanup: {e}")

    def _on_sort_changed(self, entity_type: str, column: int, order: Qt.SortOrder):
        """Track sort state changes for entity lists."""
        self.entity_sort_state[entity_type] = (column, order)
        self.logger.debug(f"Sort changed for {entity_type}: column={column}, order={order}")

        # Persist sort preference to settings
        order_str = 'asc' if order == Qt.SortOrder.AscendingOrder else 'desc'
        self.settings.set_entity_sort_preference(entity_type, column, order_str)
        self.settings.save_settings()

    def _on_entity_column_resized(self, entity_type: str, index: int, old_size: int, new_size: int):
        """Save column widths when an entity column is resized."""
        if entity_type in self.entity_lists:
            doc_tree = self.entity_lists[entity_type]
            header = doc_tree.header()
            widths = [header.sectionSize(i) for i in range(header.count())]
            self.settings.set_column_widths(f'entity_{entity_type}', widths)

    def _on_send_entities_to_discord(self, entity_type: str, preselected_ids=()):
        """Open the picker for NPCs / locations and send the chosen ones to Discord."""
        from gui.discord_actions import send_entities_to_discord
        send_entities_to_discord(self, self.db, self.current_module_id, entity_type,
                                 get_registry().plural(entity_type), preselected_ids)

    def _on_entity_context_menu(self, entity_type: str, pos):
        """Right-click on an entity row: offer Discord (never Delete) for the clicked row."""
        doc_tree = self.entity_lists[entity_type]
        item = doc_tree.itemAt(pos)
        if item is None:
            return
        doc_tree.setCurrentItem(item)
        document = item.data(0, Qt.ItemDataRole.UserRole) or {}
        menu = QMenu(self)
        action = menu.addAction("Send to Discord...")
        if menu.exec(doc_tree.viewport().mapToGlobal(pos)) is action:
            self._on_send_entities_to_discord(entity_type, [document['id']] if document.get('id') else ())

    def _on_entity_tree_item_selected(self, item: QTreeWidgetItem, entity_type: str):
        """Handle document selection in entity-specific tabs (tree widget version)."""
        try:
            document_data = item.data(0, Qt.ItemDataRole.UserRole)
            if document_data:
                # Ensure document_data is a dictionary
                if not isinstance(document_data, dict):
                    self.logger.error(f"Invalid document data type: {type(document_data)}")
                    show_warning(self, "Document Error", "Invalid document data format.")
                    return

                # Safely create document object
                try:
                    self.logger.debug(f"Creating document object from data: {document_data}")
                    document = Document.from_dict(document_data)
                    self.logger.debug(f"Document object created: ID={document.id}, title={document.title}")

                    # Open document in new window
                    self._open_document_window(document)
                except Exception as doc_error:
                    self.logger.error(f"Error creating document object: {doc_error}")
                    show_warning(self, "Document Error", f"Failed to load document: {doc_error}")
                    return

        except Exception as e:
            self.logger.error(f"Error selecting document: {e}")
            show_warning(self, "Selection Error", f"Failed to select document: {e}")

    def _open_document_window(self, document: Document):
        """Open document in a new window."""
        try:
            viewer_window = DocumentViewerWindow(document, self.db, self)
            viewer_window.show()
        except Exception as e:
            self.logger.error(f"Error opening document window: {e}")
            show_error(self, "Error", f"Failed to open document: {e}")

    def _handle_internal_link(self, url):
        """
        Navigate to entity from internal link.

        Args:
            url: QUrl with format rpg://entity_type/document_id
                 Example: rpg://npc/42

        This method is called when a user clicks an internal link in any
        FormattedTextEdit widget. It parses the URL, fetches the entity
        from the database, and opens it in a DocumentViewerWindow.
        """

        self.logger.info(f"_handle_internal_link called with URL: {url.toString()}")

        try:
            # Parse URL components
            entity_type = url.host()  # e.g., 'npc', 'location'
            path = url.path().strip('/')
            document_id = int(path)

            # Validate entity type
            valid_types = get_registry().keys_for('context')  # hidden types stay linkable
            if entity_type not in valid_types:
                raise ValueError(f"Invalid entity type: {entity_type}")

            self.logger.info(f"Navigating to internal link: {entity_type}/{document_id}")

            # Fetch document from database
            doc_dict = self.db.get_document(document_id)
            if not doc_dict:
                QMessageBox.warning(
                    self,
                    "Entity Not Found",
                    f"Could not find {entity_type} with ID {document_id}.\n\n"
                    f"The entity may have been deleted."
                )
                return

            # A link may only open entries of the open campaign (a backup or import could point elsewhere)
            if doc_dict.get('module_id') != self.current_module_id:
                QMessageBox.warning(
                    self, "Link Outside This Campaign",
                    "This link points to an entry that belongs to a different campaign, so it was not opened."
                )
                return

            # Verify the entity type matches (optional validation)
            if doc_dict.get('entity_type') != entity_type:
                self.logger.warning(
                    f"Entity type mismatch: URL says {entity_type}, "
                    f"but database has {doc_dict.get('entity_type')}"
                )

            # Open in DocumentViewerWindow
            document = Document.from_dict(doc_dict)
            self._open_document_window(document)

        except (ValueError, IndexError) as e:
            QMessageBox.warning(
                self,
                "Invalid Link",
                f"Could not parse internal link:\n{url.toString()}\n\n"
                f"Error: {str(e)}"
            )
            self.logger.error(f"Failed to parse internal link {url.toString()}: {e}")
        except Exception as e:
            QMessageBox.critical(
                self,
                "Navigation Error",
                f"An error occurred while navigating to the entity:\n\n{str(e)}"
            )
            self.logger.error(f"Error navigating to internal link: {e}", exc_info=True)

    def _on_entity_search(self, text: str, entity_type: str):
        """Handle search within a specific entity type tab."""
        try:
            if not text.strip():
                # If search is empty, reload all documents for this entity type
                self._load_entity_documents(entity_type)
                return

            # Get all documents for this entity type
            self._module_title_cache = {}
            documents = self.db.get_documents(self.current_module_id, entity_type)

            # For NPCs, get valid faction names for validation
            valid_faction_names = set()
            if get_registry().has_capability(entity_type, CAP_FACTION_LINK):
                factions = self.db.get_documents(self.current_module_id, 'faction')
                valid_faction_names = {f['title'].lower() for f in factions}

            # Filter by search text
            filtered_docs = []
            search_lower = text.lower()
            for doc in documents:
                if (search_lower in doc['title'].lower() or
                    search_lower in doc['content'].lower()):
                    filtered_docs.append(doc)

            # Update the tree widget
            if entity_type in self.entity_lists:
                doc_tree = self.entity_lists[entity_type]

                # Temporarily disable sorting for faster insertion
                doc_tree.setSortingEnabled(False)
                doc_tree.clear()

                for doc in filtered_docs:
                    item = QTreeWidgetItem()
                    self._fill_entity_row(item, doc, entity_type, valid_faction_names)

                    # Store full document data in item
                    item.setData(0, Qt.ItemDataRole.UserRole, doc)

                    doc_tree.addTopLevelItem(item)

                # Re-enable sorting and restore previous sort state
                doc_tree.setSortingEnabled(True)

                # Get saved sort state for this entity type, default to Name ascending
                sort_column, sort_order = self.entity_sort_state.get(
                    entity_type, (0, Qt.SortOrder.AscendingOrder)
                )
                doc_tree.sortByColumn(sort_column, sort_order)

        except Exception as e:
            self.logger.error(f"Error searching {entity_type} documents: {e}")

    def _on_new_entity_document(self, entity_type: str, use_template: bool = True):
        """Handle new document creation for a specific entity type."""
        if not self.current_module_id:
            show_warning(self, "No Campaign", "Please create or open a campaign first.")
            return

        try:
            # Get document title
            from PyQt6.QtWidgets import QInputDialog

            title, ok = QInputDialog.getText(
                self,
                f"New {get_registry().label(entity_type)}",
                f"Enter {get_registry().label(entity_type)} name:"
            )

            if not ok or not title.strip():
                return

            document_id = None

            if use_template:
                # Create document with default template for this entity type
                template = self.template_service.get_default_template(entity_type)
                if template:
                    document_id = self.template_service.create_document_from_template(
                        template, {}, title, self.current_module_id
                    )
                else:
                    # No template available, ask if user wants to create blank document
                    if show_question(
                        self,
                        "No Template",
                        f"No default template found for {entity_type}. Create blank document instead?"
                    ):
                        document_id = self._create_blank_document(entity_type, title)
            else:
                # Create blank document
                document_id = self._create_blank_document(entity_type, title)

            if document_id:
                # Refresh the specific entity tab
                self._load_entity_documents(entity_type)

                # Open the new document in viewer window
                documents = self.db.get_documents(self.current_module_id, entity_type)
                for doc in documents:
                    if doc['id'] == document_id:
                        document = Document.from_dict(doc)
                        self._open_document_window(document)
                        break

                self.status_bar.showMessage(f"Created {entity_type}: {title}")
            else:
                show_error(self, "Error", f"Failed to create {entity_type}.")

        except Exception as e:
            self.logger.error(f"Error creating {entity_type} document: {e}")
            show_error(self, "Error", f"Failed to create {entity_type}: {e}")

    def _on_tab_changed(self, index: int):
        """Handle tab changes to load content when needed."""
        try:
            tab_text = self.tab_widget.tabText(index)
            self.logger.debug(f"Tab changed to: {tab_text}")

            if tab_text == "Templates":
                # Load templates when Templates tab is activated
                self._load_templates()

            elif tab_text == "Sessions":
                # Session widget is now created during initialization
                # Refresh data when tab is activated to ensure it's current
                if hasattr(self, 'session_widget') and self.session_widget is not None:
                    self.session_widget.refresh_data()

        except Exception as e:
            self.logger.error(f"Error handling tab change: {e}")

    def _on_delete_entity_document(self, entity_type: str):
        """Handle document deletion for a specific entity type."""
        self.logger.info(f"Entity document deletion initiated - Type: {entity_type}, Campaign: {self.current_module_id}")

        if not self.current_module_id:
            self.logger.warning("No campaign selected for entity deletion")
            show_warning(self, "No Campaign", "Please create or open a campaign first.")
            return

        try:
            # Get the currently selected item in the entity tree
            if entity_type in self.entity_lists:
                doc_tree = self.entity_lists[entity_type]
                current_item = doc_tree.currentItem()

                if not current_item:
                    self.logger.debug(f"No {entity_type} selected for deletion")
                    show_info(self, "No Selection", f"Please select a {entity_type} to delete.")
                    return

                document_data = current_item.data(0, Qt.ItemDataRole.UserRole)
                if not document_data:
                    self.logger.error(f"Invalid document data for {entity_type} deletion")
                    show_warning(self, "Invalid Selection", "Invalid document selection.")
                    return

                self.logger.info(f"Deleting {entity_type} document - ID: {document_data['id']}, Title: {document_data['title']}")

                # Confirm deletion
                if show_question(
                    self,
                    "Confirm Deletion",
                    f"Are you sure you want to delete '{document_data['title']}'?\n\nThis action cannot be undone."
                ):
                    self.logger.info(f"User confirmed deletion of {entity_type} document {document_data['id']}")
                    # Delete the document
                    success = self.db.delete_document(document_data['id'])

                    if success:
                        self.logger.info(f"Successfully deleted {entity_type} document {document_data['id']}")
                        self.status_bar.showMessage(f"Deleted {entity_type}: {document_data['title']}")
                        # Refresh the entity tab
                        self._load_entity_documents(entity_type)
                    else:
                        self.logger.error(f"Failed to delete {entity_type} document {document_data['id']}")
                        show_warning(self, "Delete Failed", "Failed to delete document.")

        except Exception as e:
            self.logger.error(f"Error deleting {entity_type} document: {e}", exc_info=True)
            show_error(self, "Error", f"Failed to delete {entity_type}: {e}")

    def _create_blank_document(self, entity_type: str, title: str) -> Optional[int]:
        """Create a blank document without using a template."""
        try:
            # Create document with minimal content
            blank_content = f"{get_registry().label(entity_type)}: {title}\n\n[Add your content here...]"

            return self.db.create_document(
                module_id=self.current_module_id,
                entity_type=entity_type,
                title=title,
                content=blank_content,
                created_by="user",
                status="draft"
            )
        except Exception as e:
            self.logger.error(f"Error creating blank document: {e}")
            return None

    # Old document display methods removed - now using DocumentViewerWindow

    def _update_window_title(self):
        """Update window title with current campaign."""
        if self.current_module_id:
            try:
                module = self.db.get_module(self.current_module_id)
                if module:
                    self.setWindowTitle(f"{APP_NAME} v{APP_VERSION} - {module['name']}")
                    self.module_label.setText(f"Current Campaign: {module['name']}")
                else:
                    self.setWindowTitle(get_version_string())
                    self.module_label.setText("Current Campaign: None")
            except (KeyError, TypeError, AttributeError):
                # Database access failed or module data invalid
                self.setWindowTitle(get_version_string())
                self.module_label.setText("Current Campaign: None")
        else:
            self.setWindowTitle(get_version_string())
            self.module_label.setText("Current Campaign: None")

    def _apply_settings(self):
        """Apply application settings to UI."""
        from PyQt6.QtWidgets import QApplication
        from gui.theme.style_manager import update_typography
        from gui.theme import get_theme_manager

        app = QApplication.instance()

        # Typography first: the application stylesheet is generated from it
        update_typography(self.settings.ui)

        # Theme: design tokens -> QPalette + stylesheet; 'auto' follows the OS scheme
        theme = self.settings.ui.theme.lower()
        try:
            if app:
                get_theme_manager().apply(app, theme)
        except Exception as e:
            self.logger.error(f"Failed to apply theme '{theme}': {e}")

        # Font (empty family means the platform default)
        font = self.font()
        font.setPointSize(self.settings.ui.font_size)
        if self.settings.ui.font_family:
            font.setFamily(self.settings.ui.font_family)
        self.setFont(font)
        if app:
            app.setFont(font)

        self.logger.info(f"Applied typography scale: {self.settings.ui.typography_scale}")

    def _on_settings(self):
        """Handle preferences dialog."""
        try:
            dialog = SettingsDialog(self.settings, self.db, self.image_service, self)
            dialog.exec()
            if dialog.entity_types_modified:
                # Also true after "Apply" followed by "Cancel": the types were already saved
                self._on_entity_types_changed()
            # (settings are applied to this window by the dialog's own Apply/OK handler)
        except Exception as e:
            show_error(self, "Error", f"Failed to open preferences: {e}")

    def _on_name_generator(self):
        """Handle name generator dialog."""
        try:
            from gui.name_generator_dialog import NameGeneratorDialog
            dialog = NameGeneratorDialog(self)
            dialog.show()
        except Exception as e:
            self.logger.error(f"Error opening name generator: {e}", exc_info=True)
            show_error(self, "Error", f"Failed to open name generator: {e}")

    def _on_database_integrity_check(self):
        """Handle database integrity check."""
        try:
            self.status_bar.showMessage("Checking database integrity...")
            self.logger.info("Running database integrity check from menu")

            # Run integrity check
            integrity_results = self.db.check_database_integrity()

            # Show results in a dialog
            self._show_integrity_results_dialog(integrity_results)

        except Exception as e:
            self.logger.error(f"Error during database integrity check: {e}", exc_info=True)
            show_error(self, "Error", f"Failed to check database integrity: {e}")

    def _on_database_repair(self):
        """Handle database repair."""
        try:
            # First check if repair is needed
            integrity_results = self.db.check_database_integrity()

            if integrity_results['is_healthy']:
                show_info(self, "Database Healthy", "Database is already healthy and doesn't need repair.")
                return

            # Show confirmation dialog
            error_summary = "\n".join(f"• {error}" for error in integrity_results['errors'])
            if not show_question(
                self,
                "Database Repair Required",
                "Database integrity issues detected:\n\n"
                f"{error_summary}\n\n"
                "Attempting repair may fix these issues but could result in data loss.\n\n"
                "Do you want to proceed with repair?"
            ):
                return

            self.status_bar.showMessage("Repairing database...")
            self.logger.warning("Starting database repair from menu")

            # Run repair
            repair_results = self.db.repair_database()

            # Show repair results
            self._show_repair_results_dialog(repair_results)

        except Exception as e:
            self.logger.error(f"Error during database repair: {e}", exc_info=True)
            show_error(self, "Error", f"Failed to repair database: {e}")

    def _show_integrity_results_dialog(self, integrity_results):
        """Show database integrity check results in a dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Database Integrity Check Results")
        dialog.setModal(True)
        dialog.resize(600, 500)

        layout = QVBoxLayout(dialog)

        # Status
        status_label = QLabel(f"Database Status: {'HEALTHY' if integrity_results['is_healthy'] else 'CORRUPTED'}")
        set_props(status_label, role="status", state="ok" if integrity_results['is_healthy'] else "error")
        layout.addWidget(status_label)

        # Database info
        info_group = QGroupBox("Database Information")
        info_layout = QFormLayout(info_group)

        info_layout.addRow("Database Path:", QLabel(integrity_results['database_path']))
        info_layout.addRow("Connection Status:", QLabel("Connected" if integrity_results['is_connected'] else "Disconnected"))

        if integrity_results['pragma_info']:
            info_layout.addRow("Page Size:", QLabel(str(integrity_results['pragma_info'].get('PRAGMA page_size', 'Unknown'))))
            info_layout.addRow("Page Count:", QLabel(str(integrity_results['pragma_info'].get('PRAGMA page_count', 'Unknown'))))

        layout.addWidget(info_group)

        # Integrity check results
        if integrity_results['integrity_check']:
            integrity_group = QGroupBox("Integrity Check")
            integrity_layout = QVBoxLayout(integrity_group)
            integrity_layout.addWidget(QLabel(f"Result: {integrity_results['integrity_check']}"))
            layout.addWidget(integrity_group)

        # Foreign key check
        if integrity_results['foreign_key_check']:
            fk_group = QGroupBox("Foreign Key Constraints")
            fk_layout = QVBoxLayout(fk_group)
            if integrity_results['foreign_key_check']:
                fk_layout.addWidget(QLabel(f"Violations found: {len(integrity_results['foreign_key_check'])}"))
                for violation in integrity_results['foreign_key_check'][:5]:  # Show first 5
                    fk_layout.addWidget(QLabel(f"• Table: {violation.get('table', 'Unknown')}, "
                                             f"Row: {violation.get('rowid', 'Unknown')}"))
            else:
                fk_layout.addWidget(QLabel("No violations found"))
            layout.addWidget(fk_group)

        # Errors
        if integrity_results['errors']:
            errors_group = QGroupBox("Issues Found")
            errors_layout = QVBoxLayout(errors_group)
            for error in integrity_results['errors']:
                errors_layout.addWidget(QLabel(f"• {error}"))
            layout.addWidget(errors_group)

        # Buttons
        button_layout = QHBoxLayout()

        if not integrity_results['is_healthy']:
            repair_btn = QPushButton("Repair Database")
            repair_btn.clicked.connect(lambda: self._on_database_repair_from_dialog(dialog))
            button_layout.addWidget(repair_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

        dialog.exec()

    def _on_database_repair_from_dialog(self, parent_dialog):
        """Handle repair from integrity check dialog."""
        parent_dialog.accept()  # Close the integrity dialog
        self._on_database_repair()  # Run repair

    def _show_repair_results_dialog(self, repair_results):
        """Show database repair results in a dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Database Repair Results")
        dialog.setModal(True)
        dialog.resize(500, 400)

        layout = QVBoxLayout(dialog)

        # Status
        status_label = QLabel(f"Repair Status: {'SUCCESS' if repair_results['success'] else 'FAILED'}")
        set_props(status_label, role="status", state="ok" if repair_results['success'] else "error")
        layout.addWidget(status_label)

        # Actions taken
        if repair_results['actions_taken']:
            actions_group = QGroupBox("Actions Performed")
            actions_layout = QVBoxLayout(actions_group)
            for action in repair_results['actions_taken']:
                actions_layout.addWidget(QLabel(f"• {action}"))
            layout.addWidget(actions_group)

        # Errors
        if repair_results['errors']:
            errors_group = QGroupBox("Errors Encountered")
            errors_layout = QVBoxLayout(errors_group)
            for error in repair_results['errors']:
                errors_layout.addWidget(QLabel(f"• {error}"))
            layout.addWidget(errors_group)

        # Final check recommendation
        if repair_results['success']:
            layout.addWidget(QLabel("✅ Database repair completed successfully. "
                                  "You may need to restart the application."))
        else:
            layout.addWidget(QLabel("❌ Database repair failed. "
                                  "Consider restoring from backup or recreating the database."))

        # Buttons
        button_layout = QHBoxLayout()

        if repair_results['success']:
            restart_btn = QPushButton("Restart Application")
            restart_btn.clicked.connect(lambda: self._restart_application())
            button_layout.addWidget(restart_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

        dialog.exec()

    def _restart_application(self):
        """Restart the application."""
        self.logger.info("User requested application restart after database repair")
        # Note: In a real application, you'd want to properly restart
        # For now, just close the main window
        self.close()

    def _on_about(self):
        """Handle about dialog."""
        QMessageBox.about(
            self,
            f"About {APP_NAME}",
            f"{get_version_string()}\n\n"
            "A desktop application for managing RPG content using a document-centric approach "
            "for campaigns, sessions and entities.\n\n"
            "Built with Python and PyQt6."
        )

    def closeEvent(self, event):
        """Handle window close event."""
        # Check for unsaved changes in session
        has_unsaved_session = False
        # Note: New SessionWidget uses popup windows, so unsaved changes are handled by DocumentViewerWindow
        # No need to check session widget for dirty state here

        # Build confirmation message
        if has_unsaved_session:
            message = "Are you sure you want to exit RPG Database Manager?\n\nYou have unsaved session changes that will be lost."
        else:
            message = "Are you sure you want to exit RPG Database Manager?"

        # Ask for confirmation before closing
        if not show_question(
            self,
            "Confirm Exit",
            message
        ):
            # User cancelled the close
            event.ignore()
            return

        # Clean up session widget to prevent Qt object lifecycle issues
        if hasattr(self, 'session_widget') and self.session_widget is not None:
            # Clean up the session widget properly
            self.session_widget.cleanup()
            self.session_widget = None

        # Save settings
        # When maximised, remember the restored (normal) rectangle, not the full-screen one
        self.settings.window.is_fullscreen = self.isFullScreen()
        if self.isMaximized() or self.isFullScreen():
            normal = self.normalGeometry()
            self.settings.window.position, self.settings.window.size = normal.topLeft(), normal.size()
        else:
            self.settings.window.position, self.settings.window.size = self.pos(), self.size()
        self.settings.window.is_maximized = (self.isMaximized() or
                                             (self.isFullScreen() and getattr(self, '_was_maximized_before_fullscreen', False)))
        self.settings.save_settings()

        # Flush WAL to main database file so it is clean for next open
        if getattr(self, 'db', None) is not None:
            try:
                self.db.close()
            except Exception as e:
                self.logger.warning(f"Could not close the database cleanly: {e}")

        event.accept()
