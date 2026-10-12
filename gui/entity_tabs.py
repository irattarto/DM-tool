"""Entity list tabs of the main window: building the tabs, filling, sorting, grouping, previews and deleting.

These methods belong to MainWindow (they use its database, settings and widgets); they live here
so the main window file stays readable.
"""

import json
from typing import Dict, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel, QTreeWidget, QTreeWidgetItem,
    QMenu, QComboBox, QSplitter, QToolButton,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut

from config.entity_types import get_registry, CAP_FACTION_LINK, CAP_RACE_COLUMN
from models.document import Document
from utils.ui_helpers import show_error, show_warning, show_info, show_question
from utils.entity_metadata_extractor import extract_npc_metadata, extract_faction_metadata, format_date
from gui.components.entity_list import (
    ROLE_DOC, ROLE_ROW, EntityPreviewPanel, EntityRowDelegate, PinClickFilter, RowHoverFilter, name_color, name_hue,
    is_dark,
)

UNDO_SECONDS = 10  # how long a deleted entry can still be brought back


class EntityTabsMixin:
    """Methods of MainWindow that build and run the entity list tabs."""

    def _init_entity_state(self):
        """State of the entity list tabs (called once from MainWindow.__init__)."""
        # Entity list sort state tracking (column, order) per entity type
        self.entity_sort_state: Dict[str, tuple[int, Qt.SortOrder]] = {}
        # Entity list view state per entity type: grouping, the documents on show, preview panels
        self.entity_group_state: Dict[str, str] = {}
        self.entity_folded_groups: Dict[str, set] = {}
        self.entity_view_documents: Dict[str, tuple] = {}
        self.entity_previews: Dict[str, EntityPreviewPanel] = {}
        self.entity_sort_combos: Dict[str, QComboBox] = {}
        self.entity_order_buttons: Dict[str, QToolButton] = {}
        self.entity_group_combos: Dict[str, QComboBox] = {}

        # Deleted entries wait here for UNDO_SECONDS before they really leave the database
        self._pending_deletes: Dict[int, tuple] = {}
        self._pending_delete_timer = QTimer(self)
        self._pending_delete_timer.setSingleShot(True)
        self._pending_delete_timer.timeout.connect(self._flush_pending_deletes)
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
        self._rebuild_sidebar()  # a no-op while the window is still starting up

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
        race_text = faction_text = ''

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

            race_text, faction_text = extracted.get('race') or '', faction_name
            values = [race_text, faction_text, created_date, modified_date]
        elif registry.has_capability(entity_type, CAP_RACE_COLUMN):
            race_text = extract_faction_metadata(doc.get('content', '')).get('race') or ''
            values = [race_text, created_date, modified_date]
        else:
            values = [created_date, modified_date]
        module_title = ''
        if entity_type != 'module':
            module_title = self._module_title_for(doc)
            values.append(module_title)

        for column, value in enumerate(values, start=1):
            item.setText(column, value)

        # What the thumbnail list paints (the picture is added by _populate_entity_list)
        if faction_text:
            hue = name_hue(faction_text)
        elif registry.has_capability(entity_type, CAP_FACTION_LINK):
            hue = 220  # a person without a faction gets a neutral blue
        else:
            hue = name_hue(doc.get('title', ''))
        item.setData(0, ROLE_ROW, {'race': race_text, 'faction': faction_text, 'module': module_title,
                                   'hue': hue, 'image': None, 'is_group': False})

    # Delete lives in the right-click menu and on the Delete key (always with a confirmation, then Undo).
    # Set to False to bring back the toolbar Delete button and keep Delete out of the menu.
    ENTITY_MENU_HAS_DELETE = True

    def _setup_entity_tab(self, tab: QWidget, entity_type: str):
        """Setup a specific entity type tab."""
        layout = QVBoxLayout(tab)
        registry = get_registry()
        label = registry.label(entity_type)

        # Toolbar for this entity type
        toolbar_layout = QHBoxLayout()

        # Filter (for this entity type only)
        filter_layout = QHBoxLayout()
        filter_label = QLabel(f"Filter {label}:")
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
            discord_btn.setToolTip(f"Choose {label} to post to a Discord channel "
                                   "(name and primary picture)")
            discord_btn.clicked.connect(lambda checked, et=entity_type: self._on_send_entities_to_discord(et))
            toolbar_layout.addWidget(discord_btn)
            self.entity_discord_buttons = getattr(self, 'entity_discord_buttons', {})
            self.entity_discord_buttons[entity_type] = discord_btn

        toolbar_layout.addStretch()

        # How the list is ordered and grouped (the thumbnail list has no column headers to click)
        column_labels, _default_widths = self._entity_columns(entity_type)
        saved_column, saved_order_str = self.settings.get_entity_sort_preference(entity_type)
        saved_column = saved_column if saved_column < len(column_labels) else 0
        saved_order = Qt.SortOrder.AscendingOrder if saved_order_str == 'asc' else Qt.SortOrder.DescendingOrder
        self.entity_sort_state[entity_type] = (saved_column, saved_order)

        toolbar_layout.addWidget(QLabel("Sort by:"))
        sort_combo = QComboBox()
        for index, column_label in enumerate(column_labels):
            sort_combo.addItem(column_label, index)
        sort_combo.setCurrentIndex(saved_column)
        sort_combo.currentIndexChanged.connect(lambda _i, et=entity_type: self._on_entity_sort_changed(et))
        toolbar_layout.addWidget(sort_combo)
        self.entity_sort_combos[entity_type] = sort_combo

        order_button = QToolButton()
        order_button.setAutoRaise(False)
        order_button.clicked.connect(lambda checked=False, et=entity_type: self._on_entity_order_toggled(et))
        toolbar_layout.addWidget(order_button)
        self.entity_order_buttons[entity_type] = order_button
        self._update_order_button(entity_type)

        toolbar_layout.addWidget(QLabel("Group by:"))
        group_combo = QComboBox()
        group_combo.addItem("None", '')
        if entity_type != 'module':
            group_combo.addItem("Module", 'module')
        if registry.has_capability(entity_type, CAP_FACTION_LINK):
            group_combo.addItem("Faction", 'faction')
        saved_group = self.settings.get_entity_group_preference(entity_type)
        group_index = group_combo.findData(saved_group)
        group_combo.setCurrentIndex(group_index if group_index >= 0 else 0)
        self.entity_group_state[entity_type] = group_combo.currentData()
        group_combo.currentIndexChanged.connect(lambda _i, et=entity_type: self._on_entity_group_changed(et))
        toolbar_layout.addWidget(group_combo)
        self.entity_group_combos[entity_type] = group_combo

        # One New button: from the default template, or a blank document
        new_button = QToolButton()
        new_button.setText(f"New {label}")
        new_button.setToolTip(f"Create a new {entity_type}")
        new_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        new_menu = QMenu(new_button)
        template_action = new_menu.addAction("From template")
        template_action.setShortcut(QKeySequence("Ctrl+N"))
        template_action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        template_action.triggered.connect(lambda checked=False, et=entity_type: self._on_new_entity_document(et, use_template=True))
        blank_action = new_menu.addAction("Blank document")
        blank_action.setShortcut(QKeySequence("Ctrl+Shift+N"))
        blank_action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        blank_action.triggered.connect(lambda checked=False, et=entity_type: self._on_new_entity_document(et, use_template=False))
        tab.addAction(template_action)
        tab.addAction(blank_action)
        new_button.setMenu(new_menu)
        toolbar_layout.addWidget(new_button)

        # Delete button (while Delete is not in the right-click menu)
        if not self.ENTITY_MENU_HAS_DELETE:
            delete_btn = QPushButton("Delete")
            delete_btn.setToolTip(f"Delete selected {entity_type}")
            delete_btn.clicked.connect(lambda checked, et=entity_type: self._on_delete_entity_document(et))
            toolbar_layout.addWidget(delete_btn)

        layout.addLayout(toolbar_layout)

        # The list: one painted column (thumbnail, name, race · faction, module). The other columns
        # stay in the tree, hidden, so their text is still there for sorting, filtering and tests.
        doc_tree = QTreeWidget()
        doc_tree.setRootIsDecorated(False)  # No tree hierarchy, just a flat list (groups are plain header rows)
        doc_tree.setIndentation(0)
        doc_tree.setAlternatingRowColors(True)  # Better readability
        doc_tree.setColumnCount(len(column_labels))
        doc_tree.setHeaderLabels(column_labels)
        doc_tree.setHeaderHidden(True)
        for column in range(1, len(column_labels)):
            doc_tree.setColumnHidden(column, True)
        doc_tree.setSortingEnabled(False)  # ordered in code, see _populate_entity_list
        doc_tree.setUniformRowHeights(False)
        doc_tree.setMouseTracking(True)
        doc_tree.setItemDelegateForColumn(0, EntityRowDelegate(self.entity_thumbs, doc_tree))

        # Connect double-click, Enter, Delete key, and a click on a group header folds the group
        doc_tree.itemDoubleClicked.connect(lambda item, col, et=entity_type: self._on_entity_tree_item_selected(item, et))
        doc_tree.itemClicked.connect(self._on_entity_item_clicked)
        pin_filter = PinClickFilter(doc_tree)  # the star at the right of a row pins it for tonight
        pin_filter.pin_clicked.connect(self._on_pin_item)
        doc_tree.viewport().installEventFilter(pin_filter)
        enter_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Return), doc_tree)
        enter_shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
        enter_shortcut.activated.connect(lambda et=entity_type: self._open_current_entity(et))
        delete_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Delete), doc_tree)
        delete_shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
        delete_shortcut.activated.connect(lambda et=entity_type: self._on_delete_entity_document(et))

        if entity_type in DISCORD_ENTITY_TYPES or self.ENTITY_MENU_HAS_DELETE:
            doc_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            doc_tree.customContextMenuRequested.connect(
                lambda pos, et=entity_type: self._on_entity_context_menu(et, pos))

        # Preview panel next to the list: the hovered row, or the selected one
        preview = EntityPreviewPanel(self.entity_thumbs, with_discord=entity_type in DISCORD_ENTITY_TYPES)
        preview.open_requested.connect(lambda document, et=entity_type: self._open_document_dict(document))
        preview.pin_requested.connect(lambda document: self._toggle_pin(document['id']))
        preview.discord_requested.connect(
            lambda document, et=entity_type: self._on_send_entities_to_discord(et, [document['id']]))
        self.entity_previews[entity_type] = preview
        doc_tree.currentItemChanged.connect(lambda current, _previous, et=entity_type: self._update_entity_preview(et, current))
        doc_tree.itemEntered.connect(lambda item, _col, et=entity_type: self._update_entity_preview(et, item))
        hover_filter = RowHoverFilter(doc_tree)
        hover_filter.left.connect(lambda et=entity_type: self._update_entity_preview(et, self.entity_lists[et].currentItem()))
        doc_tree.viewport().installEventFilter(hover_filter)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(doc_tree)
        splitter.addWidget(preview)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setCollapsible(0, False)
        splitter.setSizes([900, 280])

        self.entity_lists[entity_type] = doc_tree
        layout.addWidget(splitter)

        # Store search widget for this entity type
        self.entity_search_widgets = getattr(self, 'entity_search_widgets', {})
        self.entity_search_widgets[entity_type] = search_edit

    def _load_documents(self):
        """Load documents for current campaign."""
        if not self.current_module_id:
            return

        try:
            self._load_pins()  # before the lists, so their rows know which entries are pinned
            # Load documents for each entity type
            for entity_type in self.entity_types.keys():
                self._load_entity_documents(entity_type)
            self._refresh_pin_tray()
            if self.tab_widget.currentWidget() is self.home_tab:
                self._refresh_home()

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

            self.entity_view_documents[entity_type] = (documents, valid_faction_names)
            self._populate_entity_list(entity_type)

        except Exception as e:
            self.logger.error(f"Error loading {entity_type} documents: {e}")

    def _populate_entity_list(self, entity_type: str):
        """(Re)build one entity list from the documents on show: pictures, order and grouping."""
        if entity_type not in self.entity_lists:
            return
        doc_tree = self.entity_lists[entity_type]
        documents, valid_faction_names = self.entity_view_documents.get(entity_type, ([], set()))
        documents = [doc for doc in documents if doc['id'] not in self._pending_deletes]

        # Keep the selection and scroll position across the rebuild
        selected_doc_id = None
        current_item = doc_tree.currentItem()
        if current_item:
            doc_data = current_item.data(0, ROLE_DOC)
            if doc_data:
                selected_doc_id = doc_data.get('id')
        scroll_bar = doc_tree.verticalScrollBar()
        scroll_position = scroll_bar.value() if scroll_bar else 0

        images = self.db.get_primary_images_for_documents([doc['id'] for doc in documents])
        items = []
        for doc in documents:
            item = QTreeWidgetItem()
            self._fill_entity_row(item, doc, entity_type, valid_faction_names)
            item.setData(0, ROLE_DOC, doc)  # full document data
            info = item.data(0, ROLE_ROW)
            info['image'] = images.get(doc['id'])
            info['pinned'] = doc['id'] in self._pins
            item.setData(0, ROLE_ROW, info)
            items.append(item)
        items = self._sort_entity_items(entity_type, items)

        doc_tree.blockSignals(True)
        doc_tree.clear()
        group_by = self.entity_group_state.get(entity_type, '')
        if group_by:
            folded = self.entity_folded_groups.setdefault(entity_type, set())
            groups: Dict[str, list] = {}
            for item in items:
                groups.setdefault(item.data(0, ROLE_ROW).get(group_by) or '', []).append(item)
            none_label = f"No {group_by}"
            names = sorted((name for name in groups if name), key=str.casefold)
            if '' in groups:
                names.append('')  # entries without a value come last
            for name in names:
                header = QTreeWidgetItem()
                header.setData(0, ROLE_ROW, {'is_group': True, 'title': name or none_label, 'count': len(groups[name])})
                header.setFlags(Qt.ItemFlag.ItemIsEnabled)  # a header can be clicked but never selected
                doc_tree.addTopLevelItem(header)
                header.addChildren(groups[name])
                header.setExpanded(name not in folded)
        else:
            doc_tree.addTopLevelItems(items)

        # Restore the selection if it still exists, otherwise the scroll position
        restored = self._find_entity_item(doc_tree, selected_doc_id) if selected_doc_id is not None else None
        if restored is not None:
            doc_tree.setCurrentItem(restored)
            doc_tree.scrollToItem(restored)
        elif scroll_bar:
            scroll_bar.setValue(scroll_position)
        doc_tree.blockSignals(False)
        self._update_entity_preview(entity_type, doc_tree.currentItem())
        self._refresh_sidebar_counts()

    def _sort_entity_items(self, entity_type: str, items: list) -> list:
        """Order list rows by the chosen column; rows without a value always come last."""
        labels, _widths = self._entity_columns(entity_type)
        column, order = self.entity_sort_state.get(entity_type, (0, Qt.SortOrder.AscendingOrder))
        label = labels[column] if column < len(labels) else 'Name'

        def title(item):
            return item.data(0, ROLE_DOC).get('title', '').casefold()

        def value(item):
            doc = item.data(0, ROLE_DOC)
            if label == 'Name':
                return title(item)
            if label == 'Created Date':
                return doc.get('created_date') or ''
            if label == 'Modified Date':
                return doc.get('modified_date') or ''
            return item.text(column).casefold()

        filled = [item for item in items if value(item) != '']
        empty = sorted((item for item in items if value(item) == ''), key=title)
        filled.sort(key=lambda item: (value(item), title(item)), reverse=order == Qt.SortOrder.DescendingOrder)
        return filled + empty

    @staticmethod
    def _find_entity_item(doc_tree: QTreeWidget, doc_id: int) -> Optional[QTreeWidgetItem]:
        """The list row of a document (rows may sit inside group headers)."""
        stack = [doc_tree.topLevelItem(i) for i in range(doc_tree.topLevelItemCount())]
        while stack:
            item = stack.pop()
            data = item.data(0, ROLE_DOC)
            if data and data.get('id') == doc_id:
                return item
            stack.extend(item.child(i) for i in range(item.childCount()))
        return None

    def _update_order_button(self, entity_type: str):
        _column, order = self.entity_sort_state.get(entity_type, (0, Qt.SortOrder.AscendingOrder))
        button = self.entity_order_buttons[entity_type]
        ascending = order == Qt.SortOrder.AscendingOrder
        button.setText('▲' if ascending else '▼')
        button.setToolTip("Ascending - click to reverse" if ascending else "Descending - click to reverse")

    def _on_entity_sort_changed(self, entity_type: str):
        """A different sort column was chosen in the toolbar."""
        column = self.entity_sort_combos[entity_type].currentData()
        _old_column, order = self.entity_sort_state.get(entity_type, (0, Qt.SortOrder.AscendingOrder))
        self._on_sort_changed(entity_type, column, order)
        self._populate_entity_list(entity_type)

    def _on_entity_order_toggled(self, entity_type: str):
        """The sort direction button was clicked."""
        column, order = self.entity_sort_state.get(entity_type, (0, Qt.SortOrder.AscendingOrder))
        order = (Qt.SortOrder.DescendingOrder if order == Qt.SortOrder.AscendingOrder
                 else Qt.SortOrder.AscendingOrder)
        self._on_sort_changed(entity_type, column, order)
        self._update_order_button(entity_type)
        self._populate_entity_list(entity_type)

    def _on_entity_group_changed(self, entity_type: str):
        """Grouping was changed in the toolbar."""
        group = self.entity_group_combos[entity_type].currentData() or ''
        self.entity_group_state[entity_type] = group
        self.settings.set_entity_group_preference(entity_type, group)
        self.settings.save_settings()
        self.entity_folded_groups.pop(entity_type, None)
        self._populate_entity_list(entity_type)

    def _on_entity_item_clicked(self, item: QTreeWidgetItem, _column: int):
        """A click on a group header folds or unfolds the group."""
        info = item.data(0, ROLE_ROW)
        if info and info.get('is_group'):
            item.setExpanded(not item.isExpanded())
            entity_type = next((et for et, tree in self.entity_lists.items() if tree is item.treeWidget()), None)
            if entity_type:
                folded = self.entity_folded_groups.setdefault(entity_type, set())
                name = info['title']
                folded.discard(name) if item.isExpanded() else folded.add(name)

    def _open_current_entity(self, entity_type: str):
        """Enter key: open the selected row."""
        item = self.entity_lists[entity_type].currentItem()
        if item is not None:
            self._on_entity_tree_item_selected(item, entity_type)

    def _open_document_dict(self, document: dict):
        self._open_document_window(Document.from_dict(document))

    def _update_entity_preview(self, entity_type: str, item: Optional[QTreeWidgetItem]):
        """Show a row (hovered or selected) in the preview panel next to the list."""
        preview = self.entity_previews.get(entity_type)
        if preview is None:
            return
        document = item.data(0, ROLE_DOC) if item is not None else None
        if not document:
            if item is None:
                preview.show_empty()
            return  # a group header leaves the preview as it is
        info = item.data(0, ROLE_ROW) or {}
        registry = get_registry()
        labels, _widths = self._entity_columns(entity_type)
        dark = is_dark(self.palette())
        rows = []
        if registry.has_capability(entity_type, CAP_FACTION_LINK) or registry.has_capability(entity_type, CAP_RACE_COLUMN):
            rows.append(("Race", info.get('race', ''), None))
        if registry.has_capability(entity_type, CAP_FACTION_LINK):
            faction = info.get('faction', '')
            rows.append(("Faction", faction, name_color(name_hue(faction), dark) if faction else None))
        if entity_type != 'module':
            rows.append(("Module", info.get('module', ''), None))
        for column_label, caption in (('Created Date', 'Created'), ('Modified Date', 'Modified')):
            if column_label in labels:
                rows.append((caption, item.text(labels.index(column_label)), None))
        preview.show_document(document, info, rows)

    def _on_sort_changed(self, entity_type: str, column: int, order: Qt.SortOrder):
        """Track sort state changes for entity lists."""
        self.entity_sort_state[entity_type] = (column, order)
        self.logger.debug(f"Sort changed for {entity_type}: column={column}, order={order}")

        # Persist sort preference to settings
        order_str = 'asc' if order == Qt.SortOrder.AscendingOrder else 'desc'
        self.settings.set_entity_sort_preference(entity_type, column, order_str)
        self.settings.save_settings()

    def _on_send_entities_to_discord(self, entity_type: str, preselected_ids=()):
        """Open the picker for NPCs / locations and send the chosen ones to Discord."""
        self._flush_pending_deletes()  # the picker reads the database: a deleted entry must not be offered
        from gui.discord_actions import send_entities_to_discord
        send_entities_to_discord(self, self.db, self.current_module_id, entity_type,
                                 get_registry().plural(entity_type), preselected_ids)

    def _on_entity_context_menu(self, entity_type: str, pos):
        """Right-click on an entity row: Open, Discord where it exists, and Delete only if enabled."""
        from gui.discord_actions import DISCORD_ENTITY_TYPES
        doc_tree = self.entity_lists[entity_type]
        item = doc_tree.itemAt(pos)
        if item is None or not item.data(0, ROLE_DOC):
            return
        doc_tree.setCurrentItem(item)
        document = item.data(0, ROLE_DOC) or {}
        menu = QMenu(self)
        open_action = menu.addAction("Open")
        pin_action = menu.addAction("Unpin" if self._is_pinned(document.get('id')) else "Pin for tonight")
        discord_action = menu.addAction("Send to Discord...") if entity_type in DISCORD_ENTITY_TYPES else None
        delete_action = None
        if self.ENTITY_MENU_HAS_DELETE:
            menu.addSeparator()
            delete_action = menu.addAction("Delete")
        chosen = menu.exec(doc_tree.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        if chosen is open_action:
            self._on_entity_tree_item_selected(item, entity_type)
        elif chosen is pin_action:
            self._toggle_pin(document['id'])
        elif chosen is discord_action:
            self._on_send_entities_to_discord(entity_type, [document['id']] if document.get('id') else ())
        elif chosen is delete_action:
            self._on_delete_entity_document(entity_type)

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

            self.entity_view_documents[entity_type] = (filtered_docs, valid_faction_names)
            self._populate_entity_list(entity_type)

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
                    f"Are you sure you want to delete '{document_data['title']}'?\n\n"
                    f"You can undo this for {UNDO_SECONDS} seconds."
                ):
                    self.logger.info(f"User confirmed deletion of {entity_type} document {document_data['id']}")
                    self._schedule_entity_delete(entity_type, document_data)

        except Exception as e:
            self.logger.error(f"Error deleting {entity_type} document: {e}", exc_info=True)
            show_error(self, "Error", f"Failed to delete {entity_type}: {e}")

    def _schedule_entity_delete(self, entity_type: str, document_data: dict):
        """Hide a confirmed delete from the list; it leaves the database after UNDO_SECONDS unless undone."""
        self._flush_pending_deletes()  # an earlier delete can no longer be undone
        self._pending_deletes[document_data['id']] = (entity_type, document_data)
        self._populate_entity_list(entity_type)
        self.undo_toast.show_message(f"'{document_data['title']}' deleted", UNDO_SECONDS * 1000)
        self._pending_delete_timer.start(UNDO_SECONDS * 1000)
        self.status_bar.showMessage(f"Deleted {entity_type}: {document_data['title']}")

    def _flush_pending_deletes(self):
        """Really delete what is waiting in the undo window (timer, closing, or before the database is read)."""
        self._pending_delete_timer.stop()
        if hasattr(self, 'undo_toast'):
            self.undo_toast.dismiss()
        pending, self._pending_deletes = self._pending_deletes, {}
        failed = []
        for doc_id, (entity_type, document_data) in pending.items():
            try:
                if self.db.delete_document(doc_id):
                    self.logger.info(f"Successfully deleted {entity_type} document {doc_id}")
                    # the list keeps its documents for re-sorting: drop this one for good
                    documents, valid_faction_names = self.entity_view_documents.get(entity_type, ([], set()))
                    self.entity_view_documents[entity_type] = (
                        [doc for doc in documents if doc['id'] != doc_id], valid_faction_names)
                    continue
                self.logger.error(f"Failed to delete {entity_type} document {doc_id}")
            except Exception as e:
                self.logger.error(f"Error deleting {entity_type} document {doc_id}: {e}", exc_info=True)
            failed.append((entity_type, document_data))
        for entity_type in {entity_type for entity_type, _ in failed}:
            self._populate_entity_list(entity_type)  # the entry is still in the database: show it again
        if failed:
            show_warning(self, "Delete Failed", "Failed to delete: " + ", ".join(d['title'] for _, d in failed))

    def _undo_pending_delete(self):
        """Bring back what was deleted in the last UNDO_SECONDS."""
        if not self._pending_deletes:
            return
        pending, self._pending_deletes = self._pending_deletes, {}
        self._pending_delete_timer.stop()
        self.undo_toast.dismiss()
        for entity_type in {entity_type for entity_type, _ in pending.values()}:
            self._populate_entity_list(entity_type)
        restored = ", ".join(data['title'] for _, data in pending.values())
        self.status_bar.showMessage(f"Restored: {restored}")

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
