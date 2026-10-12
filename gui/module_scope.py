"""Adventure modules in the main window: the scope selector, the per-list module filter and bulk actions.

An entry can belong to no module, one or several. The links are 'belongs_to_module' relationships; the scope
(top bar) filters every list, the Sessions page, Home and Ctrl+K at once, and each list has its own filter on top.

These methods belong to MainWindow; they live here so the main window file stays readable.
"""

from typing import Dict, List, Optional, Set


from PyQt6.QtWidgets import QComboBox, QInputDialog, QLabel, QMenu, QToolButton

from config.entity_types import CAP_FACTION_LINK, get_registry
from gui.components.module_picker import StayOpenMenu
from gui.components.entity_list import ROLE_DOC
from utils.natural_sort import natural_key

FILTER_NONE = 'none'     # value of the list filter "No module"


class ModuleScopeMixin:
    """Methods of MainWindow for module links, the scope selector and the module filters."""

    def _init_module_scope(self):
        self._scope_all = True
        self._scope_modules: Set[int] = set()
        self._scope_none = False
        self._module_links: Dict[int, Set[int]] = {}
        self._module_titles: Dict[int, str] = {}
        self.entity_module_filters: Dict[str, QComboBox] = {}
        self._list_module_filter: Dict[str, object] = {}   # entity type -> None | FILTER_NONE | module id

    # --- the links ---------------------------------------------------------------------------------------

    def _reload_module_links(self):
        """Read the modules of the open campaign and which entries belong to them."""
        if not self.current_module_id:
            self._module_links, self._module_titles = {}, {}
        else:
            try:
                summaries = self.db.get_document_summaries(self.current_module_id)
                self._module_titles = {d['id']: d['title'] for d in summaries if d['entity_type'] == 'module'}
                links = self.db.get_module_links(self.current_module_id)
                self._module_links = {doc_id: {m for m in modules if m in self._module_titles}
                                      for doc_id, modules in links.items()}
            except Exception as e:
                self.logger.warning(f"Could not read module links: {e}")
                self._module_links, self._module_titles = {}, {}
        self._scope_modules &= set(self._module_titles)
        if not self._scope_all and not self._scope_modules and not self._scope_none:
            self._scope_all = True
        for entity_type, value in list(self._list_module_filter.items()):
            if isinstance(value, int) and value not in self._module_titles:
                self._list_module_filter[entity_type] = None
        self._refresh_module_filters()
        self._update_scope_button()

    def _module_titles_for(self, doc_id: int) -> str:
        """The modules of an entry as text ("A, B"), or ''."""
        titles = sorted((self._module_titles[m] for m in self._module_links.get(doc_id, ()) if m in self._module_titles),
                        key=natural_key)
        return ", ".join(titles)

    def _in_scope(self, doc_id: int, entity_type: str = '') -> bool:
        """Is the entry inside the scope chosen in the top bar? (Module pages themselves are always shown.)"""
        if self._scope_all or entity_type == 'module':
            return True
        links = self._module_links.get(doc_id)
        if not links:
            return self._scope_none
        return bool(links & self._scope_modules)

    def _passes_list_filter(self, entity_type: str, doc_id: int) -> bool:
        """The filter of one list (its own module box), on top of the scope."""
        chosen = self._list_module_filter.get(entity_type)
        if chosen is None:
            return True
        links = self._module_links.get(doc_id, set())
        return not links if chosen == FILTER_NONE else chosen in links

    def _visible_in_list(self, entity_type: str, doc_id: int) -> bool:
        return (self._in_scope(doc_id, entity_type)
                and (entity_type == 'module' or self._passes_list_filter(entity_type, doc_id)))

    # --- scope selector in the top bar -------------------------------------------------------------------

    def _create_scope_button(self, toolbar):
        self.scope_button = QToolButton()
        self.scope_button.setToolTip("Show only the entries of some adventure modules, in every list, the "
                                     "Sessions page, Home and the search (Ctrl+K)")
        self.scope_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.scope_menu = StayOpenMenu(self.scope_button)
        self.scope_menu.aboutToShow.connect(self._fill_scope_menu)
        self.scope_button.setMenu(self.scope_menu)
        toolbar.addWidget(self.scope_button)
        self._update_scope_button()

    def _scope_text(self) -> str:
        if self._scope_all:
            return "Whole campaign"
        names = [self._module_titles[m] for m in sorted(self._scope_modules, key=lambda m: natural_key(self._module_titles[m]))]
        if self._scope_none:
            names.append("No module")
        if len(names) == 1:
            return names[0]
        joined = ", ".join(names)
        return f"{len(names)} modules: {joined}" if len(joined) < 40 else f"{len(names)} modules"

    def _update_scope_button(self):
        if hasattr(self, 'scope_button'):
            self.scope_button.setText(f"Scope: {self._scope_text()}  ▾")

    def _fill_scope_menu(self):
        menu = self.scope_menu
        menu.clear()
        self._scope_actions = {}
        whole = menu.addAction("Whole campaign")
        whole.setCheckable(True)
        whole.setChecked(self._scope_all)
        whole.toggled.connect(self._on_scope_whole)
        self._scope_actions['all'] = whole
        menu.addSeparator()
        if not self._module_titles:
            menu.addAction("No adventure modules yet").setEnabled(False)
        for module_id, title in sorted(self._module_titles.items(), key=lambda pair: natural_key(pair[1])):
            action = menu.addAction(title)
            action.setCheckable(True)
            action.setChecked(module_id in self._scope_modules)
            action.toggled.connect(lambda checked, m=module_id: self._on_scope_module(m, checked))
            self._scope_actions[module_id] = action
        menu.addSeparator()
        none = menu.addAction("No module")
        none.setCheckable(True)
        none.setChecked(self._scope_none)
        none.toggled.connect(self._on_scope_none)
        self._scope_actions['none'] = none

    def _sync_scope_menu(self):
        """Tick the menu entries to match the scope without rebuilding them (this runs inside one of their clicks)."""
        wanted = {'all': self._scope_all, 'none': self._scope_none}
        wanted.update({m: m in self._scope_modules for m in self._module_titles})
        for key, action in getattr(self, '_scope_actions', {}).items():
            if key in wanted and action.isChecked() != wanted[key]:
                action.blockSignals(True)
                action.setChecked(wanted[key])
                action.blockSignals(False)

    def _on_scope_whole(self, checked: bool):
        self._set_scope(True, set(), False)   # unticking it does nothing: pick a module instead

    def _on_scope_module(self, module_id: int, checked: bool):
        modules = set(self._scope_modules)
        (modules.add if checked else modules.discard)(module_id)
        self._set_scope(not modules and not self._scope_none, modules, self._scope_none)

    def _on_scope_none(self, checked: bool):
        self._set_scope(not self._scope_modules and not checked, set(self._scope_modules), checked)

    def _set_scope(self, whole: bool, modules: Set[int], none: bool):
        self._scope_all, self._scope_modules, self._scope_none = whole, modules, none
        self._update_scope_button()
        self._sync_scope_menu()
        self._apply_scope()

    def _apply_scope(self):
        """Redraw everything that follows the scope."""
        for entity_type in self.entity_types:
            self._populate_entity_list(entity_type)
        if getattr(self, 'session_widget', None) is not None:
            self.session_widget.refresh_data()
        self._refresh_sidebar_counts()
        if hasattr(self, 'home_tab') and self.tab_widget.currentWidget() is self.home_tab:
            self._refresh_home()

    # --- the module filter of each list -------------------------------------------------------------------

    def _add_module_filter(self, toolbar_layout, entity_type: str):
        """A "Module" box in the toolbar of one list (not on the modules page itself)."""
        if entity_type == 'module':
            return
        toolbar_layout.addWidget(QLabel("Module:"))
        combo = QComboBox()
        combo.setToolTip("Show only the entries of one module in this list")
        combo.currentIndexChanged.connect(lambda _i, et=entity_type: self._on_list_module_filter_changed(et))
        toolbar_layout.addWidget(combo)
        self.entity_module_filters[entity_type] = combo
        self._fill_module_filter(entity_type)

    def _fill_module_filter(self, entity_type: str):
        combo = self.entity_module_filters.get(entity_type)
        if combo is None:
            return
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("All", None)
        combo.addItem("No module", FILTER_NONE)
        for module_id, title in sorted(self._module_titles.items(), key=lambda pair: natural_key(pair[1])):
            combo.addItem(title, module_id)
        index = combo.findData(self._list_module_filter.get(entity_type))
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.blockSignals(False)

    def _refresh_module_filters(self):
        for entity_type in list(self.entity_module_filters):
            self._fill_module_filter(entity_type)

    def _on_list_module_filter_changed(self, entity_type: str):
        self._list_module_filter[entity_type] = self.entity_module_filters[entity_type].currentData()
        self._populate_entity_list(entity_type)

    # --- bulk actions on selected rows -------------------------------------------------------------------

    def _selected_entity_documents(self, entity_type: str) -> List[dict]:
        tree = self.entity_lists[entity_type]
        return [item.data(0, ROLE_DOC) for item in tree.selectedItems() if item.data(0, ROLE_DOC)]

    def _add_bulk_menu_actions(self, menu: QMenu, entity_type: str, documents: List[dict]) -> Dict:
        """Add "Add to module", "Remove from module" and "Set faction" to a context menu; returns action -> callback."""
        callbacks = {}
        ids = [d['id'] for d in documents]
        many = f" ({len(documents)} entries)" if len(documents) > 1 else ""

        add_menu = menu.addMenu(f"Add to module{many}")
        for module_id, title in sorted(self._module_titles.items(), key=lambda pair: natural_key(pair[1])):
            callbacks[add_menu.addAction(title)] = lambda m=module_id: self._bulk_set_module(entity_type, ids, m, True)
        if self._module_titles:
            add_menu.addSeparator()
        callbacks[add_menu.addAction("New module...")] = lambda: self._bulk_new_module(entity_type, ids)

        current = set()
        for doc_id in ids:
            current |= self._module_links.get(doc_id, set())
        if current:
            remove_menu = menu.addMenu(f"Remove from module{many}")
            for module_id in sorted(current, key=lambda m: natural_key(self._module_titles[m])):
                callbacks[remove_menu.addAction(self._module_titles[module_id])] = (
                    lambda m=module_id: self._bulk_set_module(entity_type, ids, m, False))

        callbacks[menu.addAction(f"Export as entity file...{many}")] = lambda: self._export_entities(documents)

        if get_registry().has_capability(entity_type, CAP_FACTION_LINK):
            factions = [d for d in self.db.get_document_summaries(self.current_module_id) if d['entity_type'] == 'faction']
            faction_menu = menu.addMenu(f"Set faction{many}")
            callbacks[faction_menu.addAction("(None)")] = lambda: self._bulk_set_faction(entity_type, ids, None)
            if factions:
                faction_menu.addSeparator()
            for faction in sorted(factions, key=lambda d: natural_key(d['title'])):
                callbacks[faction_menu.addAction(faction['title'])] = (
                    lambda f=faction['id']: self._bulk_set_faction(entity_type, ids, f))
        return callbacks

    def _bulk_set_module(self, entity_type: str, ids: List[int], module_id: int, member: bool):
        try:
            changed = self.db.set_module_membership(ids, module_id, member)
        except Exception as e:
            self.logger.error(f"Could not change module links: {e}", exc_info=True)
            return
        title = self._module_titles.get(module_id, '')
        verb = "Added to" if member else "Removed from"
        self.status_bar.showMessage(f"{verb} module '{title}': {changed} of {len(ids)} entries changed")
        self._after_module_links_changed()

    def _bulk_new_module(self, entity_type: str, ids: List[int]):
        title, ok = QInputDialog.getText(self, "New module", "Name of the new adventure module:")
        title = title.strip()
        if not ok or not title:
            return
        try:
            module_doc_id = self.db.create_document(
                module_id=self.current_module_id, entity_type='module', title=title,
                content=f"Module: {title}", created_by="user", status="draft")
        except Exception as e:
            self.logger.error(f"Could not create module: {e}", exc_info=True)
            return
        self._reload_module_links()
        self._load_entity_documents('module') if 'module' in self.entity_types else None
        self._bulk_set_module(entity_type, ids, module_doc_id, True)

    def _bulk_set_faction(self, entity_type: str, ids: List[int], faction_id: Optional[int]):
        try:
            changed = self.db.set_documents_faction(ids, faction_id)
        except Exception as e:
            self.logger.error(f"Could not set the faction: {e}", exc_info=True)
            return
        name = next((d['title'] for d in self.db.get_document_summaries(self.current_module_id)
                     if d['id'] == faction_id), '(none)')
        self.status_bar.showMessage(f"Faction '{name}' set on {changed} entries")
        self._load_entity_documents(entity_type)
        if hasattr(self, 'home_tab') and self.tab_widget.currentWidget() is self.home_tab:
            self._refresh_home()

    def _on_export_entities(self):
        """File > Export Entities: the selected rows of the open list, or the whole list when none is selected."""
        from utils.ui_helpers import show_info
        key = self._current_page_key()
        if key not in self.entity_lists:
            show_info(self, "Export Entities", "Open one of the entity lists (NPCs, Locations...) first, "
                      "and select the rows to export (or none to export the whole list).")
            return
        documents = self._selected_entity_documents(key)
        if not documents:
            tree = self.entity_lists[key]
            stack = [tree.topLevelItem(i) for i in range(tree.topLevelItemCount())]
            while stack:
                item = stack.pop(0)
                if item.data(0, ROLE_DOC):
                    documents.append(item.data(0, ROLE_DOC))
                stack.extend(item.child(i) for i in range(item.childCount()))
        self._export_entities(documents)

    def _export_entities(self, documents: List[dict]):
        """Write entries to an entity file (Markdown or JSON) that Import Entities reads again."""
        from pathlib import Path
        from PyQt6.QtWidgets import QFileDialog
        from services.entity_file_export import export_documents
        from utils.ui_helpers import show_error, show_info
        if not documents:
            show_info(self, "Export Entities", "There is nothing to export in this list.")
            return
        start = self.settings.get_custom_setting("last_entity_file_dir", "") or ""
        campaign = (self.db.get_module(self.current_module_id) or {}).get('name', 'campaign')
        path, _ = QFileDialog.getSaveFileName(self, "Export entities", str(Path(start) / f"{campaign}-entities.md"),
                                              "Markdown (*.md);;JSON (*.json)")
        if not path:
            return
        self.settings.set_custom_setting("last_entity_file_dir", str(Path(path).parent))
        try:
            fresh = [d for d in (self.db.get_document(doc['id']) for doc in documents) if d]
            result = export_documents(self.db, fresh, path)
        except Exception as e:
            self.logger.error(f"Export failed: {e}", exc_info=True)
            show_error(self, "Export failed", str(e))
            return
        note = f" and {result.images} pictures (folder 'images' next to it)" if result.images else ""
        self.status_bar.showMessage(f"Exported {result.entries} entries{note} to {result.path}")

    def _after_module_links_changed(self):
        """Module links changed (bulk action, editor): redraw the lists, counts and Home."""
        self._reload_module_links()
        self._apply_scope()
