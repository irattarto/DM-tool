"""Window shell of the main window: sidebar navigation, campaign switcher and the Ctrl+K palette.

These methods belong to MainWindow (they use its database, settings and pages); they live here
so the main window file stays readable.
"""

from collections import Counter
from typing import Dict, List, Optional

from PyQt6.QtCore import QRect, QSize, Qt
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPixmap
from PyQt6.QtWidgets import QHBoxLayout, QMenu, QMessageBox, QToolButton, QVBoxLayout, QWidget

from config.entity_types import get_registry
from gui.components.entity_list import initials, is_dark, name_hue, placeholder_color
from gui.components.pin_tray import PinTray
from gui.components.sidebar import ICON_FOR_TYPE, Sidebar
from gui.dialogs.command_palette import CommandPalette
from models.document import Document
from utils.ui_helpers import show_info

SHORTCUTS = (
    ("Ctrl+K", "Search all entries and actions"),
    ("Ctrl+N", "New entry from the template (on an entity list)"),
    ("Ctrl+Shift+N", "New blank entry (on an entity list)"),
    ("Enter", "Open the selected entry"),
    ("Delete", "Delete the selected entry (asks first, then Undo)"),
    ("Ctrl+Z", "Undo the last delete (for 10 seconds)"),
    ("F11", "Full screen"),
)


class ShellMixin:
    """Methods of MainWindow for the sidebar, the campaign switcher and the search palette."""

    # --- sidebar ---------------------------------------------------------------------------------------

    def _build_shell(self):
        """Put the sidebar next to the pages. The page widget keeps its tabs, but the sidebar replaces the tab bar."""
        self.sidebar = Sidebar()
        self.sidebar.view_selected.connect(self._on_sidebar_selected)
        # After a click (or Enter) the keyboard goes to the page, so Enter, Delete and Ctrl+N work in its list.
        # Arrow-key navigation inside the sidebar keeps the focus there.
        self.sidebar.itemClicked.connect(lambda _item: self._focus_page())
        self.sidebar.itemActivated.connect(lambda _item: self._focus_page())
        self.tab_widget.tabBar().hide()
        self.tab_widget.currentChanged.connect(self._sync_sidebar)

        # The pages, with the tray of pinned entries ("Tonight") under them
        self.pin_tray = PinTray(self.entity_thumbs)
        self.pin_tray.open_requested.connect(self._open_pinned)
        self.pin_tray.unpin_requested.connect(self._toggle_pin)
        pages = QWidget()
        pages_layout = QVBoxLayout(pages)
        pages_layout.setContentsMargins(0, 0, 0, 0)
        pages_layout.setSpacing(0)
        pages_layout.addWidget(self.tab_widget, 1)
        pages_layout.addWidget(self.pin_tray)

        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.sidebar)
        layout.addWidget(pages, 1)
        self.setCentralWidget(container)

    def _page_for_key(self, key: str) -> Optional[QWidget]:
        if key == 'home':
            return self.home_tab
        if key == 'sessions':
            return self.sessions_tab
        if key == 'templates':
            return self.templates_tab
        return self.entity_tabs.get(key)

    def _current_page_key(self) -> Optional[str]:
        widget = self.tab_widget.currentWidget()
        if widget is getattr(self, 'home_tab', None):
            return 'home'
        if widget is getattr(self, 'sessions_tab', None):
            return 'sessions'
        if widget is getattr(self, 'templates_tab', None):
            return 'templates'
        return next((key for key, tab in getattr(self, 'entity_tabs', {}).items() if tab is widget), None)

    def _rebuild_sidebar(self):
        """(Re)build the sidebar entries: Sessions, one per visible entity type, Templates."""
        if not hasattr(self, 'sidebar') or not hasattr(self, 'home_tab'):
            return  # still starting up
        entries: List[dict] = [{'kind': 'view', 'key': 'home', 'label': 'Home', 'icon': ICON_FOR_TYPE['home'], 'count': None},
                               {'kind': 'group', 'label': 'Play'},
                               {'kind': 'view', 'key': 'sessions', 'label': 'Sessions',
                                'icon': ICON_FOR_TYPE['sessions'], 'count': None},
                               {'kind': 'group', 'label': 'World'}]
        for entity_type, label in self.entity_types.items():
            entries.append({'kind': 'view', 'key': entity_type, 'label': label,
                            'icon': ICON_FOR_TYPE.get(entity_type, 'square'), 'count': None})
        entries += [{'kind': 'group', 'label': 'Library'},
                    {'kind': 'view', 'key': 'templates', 'label': 'Templates', 'icon': ICON_FOR_TYPE['templates'],
                     'count': None}]
        self.sidebar.set_entries(entries, self._current_page_key())
        self._refresh_sidebar_counts()

    def _on_sidebar_selected(self, key: str):
        page = self._page_for_key(key)
        if page is not None:
            self.tab_widget.setCurrentWidget(page)

    def _focus_page(self):
        """Give the keyboard to the list of the page just chosen."""
        key = self._current_page_key()
        tree = self.entity_lists.get(key) if key else None
        if tree is not None:
            tree.setFocus()

    def _sync_sidebar(self, _index: int = -1):
        """The page changed (sidebar, search or code): highlight its entry."""
        key = self._current_page_key()
        if key:
            self.sidebar.select_key(key)

    def _refresh_sidebar_counts(self):
        """Show how many entries each type has, and the campaign status line."""
        if not hasattr(self, 'sidebar') or not self.current_module_id or self._suspend_sidebar_counts:
            return
        try:
            counts = self.db.get_module_counts(self.current_module_id)
        except Exception as e:
            self.logger.warning(f"Could not count entries: {e}")
            return
        waiting = Counter(entity_type for entity_type, _data in self._pending_deletes.values())
        total = 0
        for entity_type in self.entity_types:
            number = max(0, counts['documents'].get(entity_type, 0) - waiting.get(entity_type, 0))
            total += number
            self.sidebar.set_count(entity_type, number)
        self.sidebar.set_count('sessions', counts['sessions'])
        self.sidebar.viewport().update()
        sessions = counts['sessions']
        self._campaign_status = f"{sessions} session{'s' if sessions != 1 else ''} · {total} entries"
        self._update_campaign_button()

    # --- campaign switcher ---------------------------------------------------------------------------

    def _create_campaign_switcher(self, toolbar):
        """Campaign name, a short status and a menu to switch, create or manage campaigns; then the search button."""
        self._campaign_name = ''
        self._campaign_status = ''
        self.campaign_button = QToolButton()
        self.campaign_button.setToolTip("Switch campaign")
        self.campaign_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.campaign_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.campaign_button.setIconSize(QSize(32, 32))
        self.campaign_menu = QMenu(self.campaign_button)
        self.campaign_menu.aboutToShow.connect(self._fill_campaign_menu)
        self.campaign_button.setMenu(self.campaign_menu)
        toolbar.addWidget(self.campaign_button)
        toolbar.addSeparator()

        self.search_button = QToolButton()
        self.search_button.setText("Search everything…   Ctrl+K")
        self.search_button.setToolTip("Find any entry or action (Ctrl+K)")
        self.search_button.clicked.connect(self._show_command_palette)
        toolbar.addWidget(self.search_button)
        self._update_campaign_button()

    def _update_campaign_button(self, name: Optional[str] = None):
        """Refresh the campaign button. Pass the name when it changed; None keeps the current one."""
        if not hasattr(self, 'campaign_button'):
            return
        if name is not None:
            self._campaign_name = name
        title = self._campaign_name or "No campaign"
        status = self._campaign_status if self._campaign_name else "Choose or create a campaign"
        self.campaign_button.setText(f"{title}\n{status}" if status else title)
        self.campaign_button.setIcon(QIcon(self._campaign_pixmap(self._campaign_name)))

    def _campaign_pixmap(self, name: str, size: int = 32) -> QPixmap:
        """A rounded square with the campaign's initials, in a colour made from its name."""
        ratio = 2
        pixmap = QPixmap(size * ratio, size * ratio)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, size * ratio, size * ratio, 9 * ratio, 9 * ratio)
        painter.setClipPath(path)
        painter.fillRect(QRect(0, 0, size * ratio, size * ratio),
                         placeholder_color(name_hue(name) if name else 220, is_dark(self.palette())))
        painter.setPen(QColor('white'))
        font = QFont(self.font())
        font.setPixelSize(int(size * ratio * 0.4))
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.drawText(QRect(0, 0, size * ratio, size * ratio), Qt.AlignmentFlag.AlignCenter,
                         initials(name) if name else '?')
        painter.end()
        pixmap.setDevicePixelRatio(ratio)
        return pixmap

    def _fill_campaign_menu(self):
        menu = self.campaign_menu
        menu.clear()
        for module in self.db.get_modules():
            action = menu.addAction(module['name'])
            action.setCheckable(True)
            action.setChecked(module['id'] == self.current_module_id)
            action.triggered.connect(lambda _checked=False, module_id=module['id']: self._switch_campaign(module_id))
        menu.addSeparator()
        menu.addAction("New campaign...", self._on_new_module)
        menu.addAction("Manage campaigns...", self._on_manage_modules)

    def _switch_campaign(self, module_id: int):
        """Open another campaign (same steps as the older Change Campaign dialog)."""
        if module_id == self.current_module_id:
            return
        self._flush_pending_deletes()
        module = self.db.get_module(module_id)
        if not module:
            return
        self.current_module_id = module_id
        self.settings.set_last_module_id(module_id)  # opened again next time
        self._update_window_title()
        self._load_documents()
        self._update_session_widget_module(module_id)
        self.status_bar.showMessage(f"Loaded campaign: {module['name']}")

    # --- search palette ----------------------------------------------------------------------------

    def _palette_images(self, document_ids: List[int]) -> Dict[int, dict]:
        return self.db.get_primary_images_for_documents(document_ids)

    def _palette_actions(self):
        registry = get_registry()
        actions = []
        current = self._current_page_key()
        if current in self.entity_tabs:
            actions.append((f"New {registry.label(current)} from template", "Ctrl+N",
                            lambda et=current: self._on_new_entity_document(et, use_template=True)))
        actions.append(("Open Name Generator", "", self._on_name_generator))
        actions.append(("Open Settings", "", self._on_settings))
        actions.append(("Manage campaigns", "", self._on_manage_modules))
        actions.append(("Toggle full screen", "F11", lambda: self._set_fullscreen(not self.isFullScreen())))
        pages = ([('home', 'Home'), ('sessions', 'Sessions')] + list(self.entity_types.items())
                 + [('templates', 'Templates')])
        for key, label in pages:
            actions.append((f"Go to {label}", "", lambda k=key: self._on_sidebar_selected(k)))
        return actions

    def _show_command_palette(self):
        """Ctrl+K: find any entry of the campaign, or run an action."""
        if not self.current_module_id:
            show_info(self, "No Campaign", "Create or open a campaign first.")
            return
        self._flush_pending_deletes()  # the palette reads the database: a deleted entry must not be offered
        registry = get_registry()
        labels = {key: registry.label(key) for key in registry.keys_for('context')}
        documents = [d for d in self.db.get_documents(self.current_module_id) if d.get('entity_type') in labels]
        palette = CommandPalette(self, documents, labels, self.entity_thumbs, self._palette_images,
                                 self._palette_actions())
        palette.entity_chosen.connect(self._open_palette_entry)
        palette.exec()

    def _open_palette_entry(self, document: dict):
        """Go to the entry's list, select it there, and open it."""
        if 'content' not in document:  # Home passes summaries without the text
            document = self.db.get_document(document['id'])
            if not document:
                return
        entity_type = document.get('entity_type')
        if entity_type in self.entity_tabs:
            self.tab_widget.setCurrentWidget(self.entity_tabs[entity_type])
            item = self._find_entity_item(self.entity_lists[entity_type], document['id'])
            if item is not None:
                self.entity_lists[entity_type].setCurrentItem(item)
                self.entity_lists[entity_type].scrollToItem(item)
        self._open_document_window(Document.from_dict(document))

    def _on_shortcuts(self):
        """Help > Keyboard Shortcuts."""
        rows = "".join(f"<tr><td><b>{keys}</b>&nbsp;&nbsp;</td><td>{what}</td></tr>" for keys, what in SHORTCUTS)
        QMessageBox.information(self, "Keyboard Shortcuts", f"<table cellpadding='3'>{rows}</table>")
