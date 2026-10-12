"""Preview and confirm the import of an HTML adventure module into the current campaign."""

import hashlib
import html
import re
from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QHeaderView,
                             QInputDialog, QLabel, QMessageBox, QProgressDialog, QTableWidget, QTableWidgetItem,
                             QTreeWidget, QTreeWidgetItem, QVBoxLayout)

from config.entity_types import get_registry
from gui.dialogs.html_module_guide import open_html_module_guide
from services.html_module_import_service import (ACTION_CONFLICT, ACTION_CREATE, ACTION_UNCHANGED,
                                                 ACTION_UPDATE, AUTO_FACTION_IDS, NEW_FACTION_PREFIX,
                                                 HtmlModuleImportService, ImportOptions, ImportPlan, ImportResult)
from services.html_module_parser import ParsedModule

_ACTION_TEXT = {
    ACTION_CREATE: 'New',
    ACTION_UPDATE: 'Update',
    ACTION_UNCHANGED: 'Unchanged',
    ACTION_CONFLICT: 'Edited here - overwrite?',
}
_KIND_ORDER = ['module', 'session', 'character', 'npc', 'faction', 'location', 'item', 'event']
_NEW_FACTION_CHOICE = '__new_faction__'      # data of the "New faction..." entry of the drop-downs


def _tooltip(text: str) -> str:
    """Rich-text tooltip of limited width; the text is escaped so imported content is never rendered as HTML."""
    return f'<table width="420"><tr><td>{html.escape(text)}</td></tr></table>' if text else ''


class HtmlModuleImportDialog(QDialog):
    """Shows what an import will create/update, lets the user deselect items, then imports."""

    def __init__(self, service: HtmlModuleImportService, parsed: ParsedModule, campaign_id: int,
                 campaign_name: str, parent=None):
        super().__init__(parent)
        self.service = service
        self.parsed = parsed
        self.campaign_id = campaign_id
        self.import_result: Optional[ImportResult] = None
        self._selection: Dict[str, bool] = {}     # remembered choices when options rebuild the plan
        self._faction_choices: Dict[str, str] = {}  # NPC source id -> faction source id picked by the user
        self._custom_factions: List[Tuple[str, str]] = []   # factions typed in here: (source id, title)
        self._plan: Optional[ImportPlan] = None

        self.setWindowTitle(f"Import module into campaign '{campaign_name}'")
        self.setModal(True)
        self.resize(760, 620)

        layout = QVBoxLayout(self)
        source = 'embedded dm-module data' if parsed.parser == 'json' else 'HTML markup'
        header = QLabel(f"<b>{parsed.title}</b><br>"
                        f"{parsed.rule_system or 'unknown system'} &middot; read from {source}")
        header.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(header)

        options_row = QHBoxLayout()
        self.images_check = QCheckBox("Import portraits and pictures")
        self.images_check.setChecked(True)
        self.prompts_check = QCheckBox("Keep image prompts in the notes")
        self.prompts_check.setChecked(True)
        self.gear_check = QCheckBox("Gear lists become inventory items")
        self.gear_check.setChecked(True)
        for check in (self.images_check, self.prompts_check, self.gear_check):
            check.toggled.connect(self._rebuild)
            options_row.addWidget(check)
        options_row.addStretch()
        layout.addLayout(options_row)

        self.auto_factions_check = QCheckBox(
            "NPCs without a faction join an automatic 'Unaffiliated' faction, monsters a 'Monsters' faction")
        self.auto_factions_check.toggled.connect(self._rebuild)
        layout.addWidget(self.auto_factions_check)

        scenes_row = QHBoxLayout()
        scenes_row.addWidget(QLabel("Scenes become events. Also copy their text into:"))
        self.scenes_combo = QComboBox()
        self.scenes_combo.addItem("A new first session (default)", 'new')
        self.scenes_combo.addItem("Nowhere (events only)", None)
        for doc in self.service.db.get_documents(campaign_id):
            if doc.get('entity_type') == 'session':
                self.scenes_combo.addItem(f"Existing session: {doc.get('title') or doc['id']}", doc['id'])
        self.scenes_combo.currentIndexChanged.connect(self._rebuild)
        scenes_row.addWidget(self.scenes_combo, 1)
        layout.addLayout(scenes_row)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Item", "Action", "Note"])
        self.tree.setColumnWidth(0, 340)
        self.tree.setColumnWidth(1, 150)
        self.tree.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.tree, 1)

        self.faction_label = QLabel("These NPCs are in no faction. Pick one if you want them linked:")
        self.faction_table = QTableWidget(0, 2)
        self.faction_table.setHorizontalHeaderLabels(["NPC", "Faction"])
        self.faction_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.faction_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.faction_table.verticalHeader().setVisible(False)
        self.faction_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.faction_table.setMaximumHeight(170)
        layout.addWidget(self.faction_label)
        layout.addWidget(self.faction_table)

        self.summary = QLabel()
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.guide_button = buttons.addButton("Format guide...", QDialogButtonBox.ButtonRole.HelpRole)
        self.guide_button.setToolTip("How to write an HTML module the app can import (also in Help > HTML Module Guide)")
        self.guide_button.clicked.connect(lambda: open_html_module_guide(self))
        self.import_button = buttons.addButton("Import", QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.accepted.connect(self._do_import)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._rebuild()

    # ------------------------------------------------------------ plan view

    def _options(self) -> ImportOptions:
        return ImportOptions(import_images=self.images_check.isChecked(),
                             import_prompts=self.prompts_check.isChecked(),
                             scenes_to_session=self.scenes_combo.currentData(),
                             faction_choices=dict(self._faction_choices),
                             auto_factions=self.auto_factions_check.isChecked(),
                             new_factions=list(self._custom_factions),
                             gear_to_inventory=self.gear_check.isChecked())

    def _remember_selection(self) -> None:
        if self._plan:
            for item in self._plan.items:
                if item.action != ACTION_UNCHANGED:
                    self._selection[item.source_id] = item.selected

    def _rebuild(self, *_):
        self._remember_selection()
        self._plan = self.service.build_plan(self.parsed, self.campaign_id, self._options())
        for item in self._plan.items:
            if item.source_id in self._selection and item.action != ACTION_UNCHANGED:
                item.selected = self._selection[item.source_id]

        registry = get_registry()
        self.tree.blockSignals(True)
        self.tree.clear()
        groups: Dict[str, QTreeWidgetItem] = {}
        kinds = [k for k in _KIND_ORDER if any(i.kind == k for i in self._plan.items)]
        kinds += sorted({i.kind for i in self._plan.items} - set(kinds))
        for kind in kinds:
            group = QTreeWidgetItem(self.tree, [registry.plural(kind)])
            group.setFlags(group.flags() | Qt.ItemFlag.ItemIsAutoTristate | Qt.ItemFlag.ItemIsUserCheckable)
            group.setExpanded(kind in ('module', 'session', 'faction'))
            groups[kind] = group
        for plan_item in self._plan.items:
            row = QTreeWidgetItem(groups[plan_item.kind], [
                plan_item.title, _ACTION_TEXT.get(plan_item.action, plan_item.action),
                self._note(plan_item)])
            row.setFlags(row.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            row.setCheckState(0, Qt.CheckState.Checked if plan_item.selected else Qt.CheckState.Unchecked)
            row.setData(0, Qt.ItemDataRole.UserRole, plan_item.source_id)
            if plan_item.kind in ('npc', 'character'):
                row.setToolTip(0, _tooltip(self.service.plain_summary(plan_item.content)))
        self.tree.blockSignals(False)
        self._fill_faction_table()
        self._update_summary()

    def _faction_options(self):
        """(source id, title) pairs a prompt may choose from; '' means no faction."""
        options = [('', "(no faction)"), ('__unknown__', "Unknown faction"), ('__undecided__', "Undecided yet")]
        options += [(sid, f"{title} (new)" if sid.startswith(NEW_FACTION_PREFIX) else title)
                    for sid, title in self._plan.factions]
        if self._plan.options.auto_factions:
            titles = self.service.auto_faction_titles(self.parsed.language)
            options += [(auto_id, f"{titles[auto_id]} (new)") for auto_id in AUTO_FACTION_IDS]
        options.append((_NEW_FACTION_CHOICE, "+ New faction..."))
        return options

    def _fill_faction_table(self) -> None:
        prompts = self._plan.faction_prompts
        self.faction_label.setVisible(bool(prompts))
        self.faction_table.setVisible(bool(prompts))
        self.faction_table.blockSignals(True)
        self.faction_table.setRowCount(len(prompts))
        options = self._faction_options()
        for row, prompt in enumerate(prompts):
            name_item = QTableWidgetItem(prompt.title)
            name_item.setToolTip(_tooltip(prompt.description))
            self.faction_table.setItem(row, 0, name_item)
            combo = QComboBox()
            combo.setToolTip(_tooltip(prompt.description))
            for source_id, title in options:
                combo.addItem(title, source_id)
            combo.setCurrentIndex(max(0, combo.findData(prompt.current)))
            combo.currentIndexChanged.connect(
                lambda _index, sid=prompt.source_id, box=combo: self._on_faction_picked(sid, box))
            self.faction_table.setCellWidget(row, 1, combo)
        self.faction_table.blockSignals(False)

    def _on_faction_picked(self, source_id: str, combo: QComboBox) -> None:
        choice = combo.currentData() or ''
        if choice == _NEW_FACTION_CHOICE:
            choice = self._ask_new_faction()
            if choice is None:                       # cancelled: put the drop-down back where it was
                previous = self._faction_choices.get(source_id)
                if previous is None:
                    previous = next((p.current for p in self._plan.faction_prompts if p.source_id == source_id), '')
                combo.blockSignals(True)
                combo.setCurrentIndex(max(0, combo.findData(previous)))
                combo.blockSignals(False)
                return
        self._faction_choices[source_id] = choice
        QTimer.singleShot(0, self._rebuild)         # not inside the combo's own signal: the table is rebuilt

    def _ask_new_faction(self) -> Optional[str]:
        """Ask for a faction name; returns the source id to use (a faction that already exists is reused)."""
        name, accepted = QInputDialog.getText(self, "New faction", "Name of the new faction:")
        name = re.sub(r'\s+', ' ', name or '').strip()[:100]
        if not accepted or not name:
            return None
        known = list(self._plan.factions) + list(self._custom_factions)
        titles = self.service.auto_faction_titles(self.parsed.language)
        if self._plan.options.auto_factions:
            known += [(auto_id, titles[auto_id]) for auto_id in AUTO_FACTION_IDS]
        for source_id, title in known:
            if title.strip().lower() == name.lower():
                return source_id                    # same name as an existing faction: use that one
        slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-') or hashlib.sha1(
            name.encode('utf-8'), usedforsecurity=False).hexdigest()[:8]
        source_id, counter = f'{NEW_FACTION_PREFIX}{slug}', 2
        used = {sid for sid, _ in known}
        while source_id in used:
            source_id = f'{NEW_FACTION_PREFIX}{slug}-{counter}'
            counter += 1
        self._custom_factions.append((source_id, name))
        return source_id

    @staticmethod
    def _note(plan_item) -> str:
        bits = []
        if plan_item.reason:
            bits.append(plan_item.reason)
        if plan_item.subtype:
            bits.append(plan_item.subtype)
        if plan_item.parent_source_id:
            bits.append(f"gear of {plan_item.parent_source_id}")
        if plan_item.faction_source_id:
            bits.append(f"faction: {plan_item.faction_source_id}")
        if plan_item.image_path is not None:
            bits.append("picture")
        return ', '.join(bits)

    def _on_item_changed(self, row: QTreeWidgetItem, _column: int) -> None:
        source_id = row.data(0, Qt.ItemDataRole.UserRole)
        if source_id is None or self._plan is None:
            return
        for item in self._plan.items:
            if item.source_id == source_id:
                item.selected = row.checkState(0) == Qt.CheckState.Checked
        self._update_summary()

    def _update_summary(self) -> None:
        plan = self._plan
        selected = [i for i in plan.items if i.selected]
        new = sum(1 for i in selected if i.action == ACTION_CREATE)
        updated = sum(1 for i in selected if i.action != ACTION_CREATE)
        conflicts = sum(1 for i in plan.items if i.action == ACTION_CONFLICT and not i.selected)
        text = f"{new} new, {updated} to update."
        pictures = sum(1 for i in plan.items if i.action == ACTION_UNCHANGED and i.pictures_changed)
        if pictures:
            text += f" {pictures} unchanged with new or changed pictures (only the pictures are updated)."
        if conflicts:
            text += f" {conflicts} edited here and left alone unless you tick them."
        if plan.unlinked:
            text += f" {len(plan.unlinked)} NPCs have no faction."
        if self.parsed.warnings:
            text += " Warnings: " + "; ".join(self.parsed.warnings[:3])
        self.summary.setText(text)
        self.import_button.setEnabled(bool(selected) or bool(pictures and plan.options.import_images))

    # ------------------------------------------------------------ import

    def _do_import(self) -> None:
        progress = QProgressDialog("Importing...", None, 0, 100, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)

        def on_progress(step: int, total: int, label: str) -> None:
            progress.setMaximum(total)
            progress.setValue(step)
            progress.setLabelText(label)
            QApplication.processEvents()

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.import_result = self.service.apply(self._plan, on_progress)
        except Exception as e:           # surface anything unexpected instead of closing silently
            QApplication.restoreOverrideCursor()
            progress.close()
            QMessageBox.critical(self, "Import failed", str(e))
            return
        QApplication.restoreOverrideCursor()
        progress.close()
        self.accept()
