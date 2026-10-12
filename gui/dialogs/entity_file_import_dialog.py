"""Preview and confirm the import of an entity file (NPCs, locations, ... in Markdown, JSON or HTML)."""

from typing import Dict, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QRadioButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout)

from config.entity_types import get_registry
from services.entity_file_service import (ACTION_CONFLICT, ACTION_CREATE, ACTION_UNCHANGED, ACTION_UPDATE, ATTACH_CHOSEN,
                                          ATTACH_FILE, ATTACH_NEW, ATTACH_NONE, AttachOptions, EntityFileService,
                                          EntityImportPlan, EntityImportResult)

_ACTION_TEXT = {ACTION_CREATE: 'New', ACTION_UPDATE: 'Update', ACTION_UNCHANGED: 'Unchanged',
                ACTION_CONFLICT: 'Exists - overwrite?'}


class EntityFileImportDialog(QDialog):
    """Shows what an entity file will create or update, where it will be attached, then imports it."""

    def __init__(self, service: EntityFileService, plan: EntityImportPlan, campaign_name: str,
                 modules: Dict[int, str], parent=None):
        super().__init__(parent)
        self.service = service
        self.plan = plan
        self.import_result: Optional[EntityImportResult] = None
        self._modules = modules
        parsed = plan.parsed
        self.setWindowTitle(f"Import entities into campaign '{campaign_name}'")
        self.setModal(True)
        self.resize(780, 620)

        layout = QVBoxLayout(self)
        source = {'markdown': 'Markdown', 'json': 'JSON', 'html': 'HTML cards'}.get(parsed.format, parsed.format)
        layout.addWidget(QLabel(f"<b>{parsed.pack}</b><br>{len(plan.items)} entries &middot; read from {source}"))
        for warning in parsed.warnings[:6]:
            note = QLabel(f"⚠ {warning}")
            note.setWordWrap(True)
            layout.addWidget(note)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Entry", "Type", "Status", "Modules"])
        self.tree.setRootIsDecorated(False)
        self.tree.setColumnWidth(0, 260)
        self.tree.setColumnWidth(1, 90)
        self.tree.setColumnWidth(2, 170)
        self.tree.itemChanged.connect(lambda *_: self._update_summary())
        layout.addWidget(self.tree, 1)

        # Where the entries go: the modules named in the file, one module, a new one, or none
        layout.addWidget(QLabel("<b>Attach the entries to adventure modules</b>"))
        self.attach_group = QButtonGroup(self)
        named = ", ".join(parsed.modules) if parsed.modules else ""
        file_text = f"the modules named in the file{(' (' + named + ')') if named else ''}"
        self.radio_file = QRadioButton(file_text)
        self.radio_chosen = QRadioButton("one module I choose:")
        self.radio_new = QRadioButton("a new module named:")
        self.radio_none = QRadioButton("none")
        for radio in (self.radio_file, self.radio_chosen, self.radio_new, self.radio_none):
            self.attach_group.addButton(radio)
        self.module_combo = QComboBox()
        for module_id, title in sorted(modules.items(), key=lambda pair: pair[1].casefold()):
            self.module_combo.addItem(title, module_id)
        self.module_combo.currentIndexChanged.connect(lambda *_: self.radio_chosen.setChecked(True))
        self.new_name = QLineEdit(parsed.suggested_module)
        self.new_name.setPlaceholderText("Module name")
        self.new_name.textChanged.connect(lambda *_: self.radio_new.setChecked(True))
        self.radio_chosen.setEnabled(bool(modules))
        self.module_combo.setEnabled(bool(modules))
        layout.addWidget(self.radio_file)
        row = QHBoxLayout()
        row.addWidget(self.radio_chosen)
        row.addWidget(self.module_combo, 1)
        layout.addLayout(row)
        row = QHBoxLayout()
        row.addWidget(self.radio_new)
        row.addWidget(self.new_name, 1)
        layout.addLayout(row)
        layout.addWidget(self.radio_none)
        if parsed.modules:
            self.radio_file.setChecked(True)
        elif parsed.suggested_module:
            self.radio_new.setChecked(True)
        else:
            self.radio_none.setChecked(True)
        self.attach_group.buttonToggled.connect(lambda *_: self._fill_tree())

        self.create_factions = QCheckBox("Create factions that the entries name but that do not exist yet")
        self.create_factions.setChecked(True)
        layout.addWidget(self.create_factions)
        self.summary = QLabel()
        layout.addWidget(self.summary)
        buttons = QDialogButtonBox()
        guide = QPushButton("Format guide...")
        guide.clicked.connect(self._open_guide)
        buttons.addButton(guide, QDialogButtonBox.ButtonRole.HelpRole)
        self.import_button = buttons.addButton("Import", QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._do_import)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._fill_tree()

    # ------------------------------------------------------------------ preview

    def options(self) -> AttachOptions:
        create = self.create_factions.isChecked()
        if self.radio_chosen.isChecked() and self.module_combo.currentData() is not None:
            return AttachOptions(ATTACH_CHOSEN, module_doc_id=self.module_combo.currentData(), create_missing_factions=create)
        if self.radio_new.isChecked():
            return AttachOptions(ATTACH_NEW, new_module_title=self.new_name.text(), create_missing_factions=create)
        if self.radio_none.isChecked():
            return AttachOptions(ATTACH_NONE, create_missing_factions=create)
        return AttachOptions(ATTACH_FILE, create_missing_factions=create)

    def _module_text(self, item) -> str:
        options = self.options()
        if options.mode == ATTACH_CHOSEN:
            return self._modules.get(options.module_doc_id, '')
        return ", ".join(self.service.module_titles_for(self.plan, item, options))

    def _fill_tree(self):
        selected = {id(self.plan.items[i]): self.tree.topLevelItem(i).checkState(0) == Qt.CheckState.Checked
                    for i in range(self.tree.topLevelItemCount())} if self.tree.topLevelItemCount() else {}
        self.tree.blockSignals(True)
        self.tree.clear()
        registry = get_registry()
        for item in self.plan.items:
            row = QTreeWidgetItem([item.title, registry.label(item.kind), _ACTION_TEXT[item.action],
                                   self._module_text(item)])
            row.setFlags(row.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            checked = selected.get(id(item), item.selected)
            row.setCheckState(0, Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
            if item.reason:
                row.setToolTip(2, item.reason)
                row.setText(2, f"{_ACTION_TEXT[item.action]} - {item.reason}")
            self.tree.addTopLevelItem(row)
        self.tree.blockSignals(False)
        self._update_summary()

    def _sync_selection(self):
        for index, item in enumerate(self.plan.items):
            item.selected = self.tree.topLevelItem(index).checkState(0) == Qt.CheckState.Checked

    def _update_summary(self):
        self._sync_selection()
        chosen = [i for i in self.plan.items if i.selected]
        counts: Dict[str, int] = {}
        for item in chosen:
            counts[item.action] = counts.get(item.action, 0) + 1
        parts = [f"{counts[a]} {_ACTION_TEXT[a].split(' ')[0].lower()}" for a in (ACTION_CREATE, ACTION_UPDATE, ACTION_CONFLICT)
                 if counts.get(a)]
        self.summary.setText(("Will import: " + ", ".join(parts)) if parts else "Nothing selected.")
        self.import_button.setEnabled(bool(chosen))

    def _open_guide(self):
        from gui.dialogs.html_module_guide import open_html_module_guide
        open_html_module_guide(self, tab='entities')

    # ------------------------------------------------------------------ import

    def _do_import(self):
        self._sync_selection()
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.import_result = self.service.apply(self.plan, self.options())
        finally:
            QApplication.restoreOverrideCursor()
        self.accept()
