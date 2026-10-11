"""
Dialogs for campaign backup and restore functionality.
"""

from gui.theme import set_props
from typing import Optional, Dict, Any

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QRadioButton, QComboBox, QGroupBox,
    QFormLayout, QButtonGroup
)
from PyQt6.QtCore import Qt

from utils.ui_helpers import show_warning
from gui.components.dialog_button_bar import DialogButtonBar


class ModuleSelectionDialog(QDialog):
    """Dialog for selecting a campaign to backup."""

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.selected_module_id = None

        self.setWindowTitle("Select Campaign to Backup")
        self.setModal(True)
        self.resize(700, 400)

        self._setup_ui()
        self._load_modules()

    def _setup_ui(self):
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)

        # Header
        header = QLabel("Select a campaign to backup:")
        set_props(header, role="heading")
        layout.addWidget(header)

        # Module table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "ID", "Name", "Documents", "Images", "Sessions"
        ])

        # Set column widths
        self.table.setColumnWidth(0, 50)
        self.table.setColumnWidth(1, 300)
        self.table.setColumnWidth(2, 90)
        self.table.setColumnWidth(3, 80)
        self.table.setColumnWidth(4, 80)

        # Table settings
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self._on_double_click)

        layout.addWidget(self.table)

        # Button bar
        button_bar = DialogButtonBar(self)
        select_btn = button_bar.add_button("Select")
        select_btn.clicked.connect(self._on_select)
        cancel_btn = button_bar.add_button("Cancel")
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(button_bar)

    def _load_modules(self):
        """Load active campaigns into the table."""
        try:
            # Get all active modules
            modules = self.db.get_all_modules_with_statistics()
            active_modules = [m for m in modules if m.get('is_active', 1)]

            self.table.setRowCount(0)

            for module in active_modules:
                row = self.table.rowCount()
                self.table.insertRow(row)

                # ID
                id_item = QTableWidgetItem(str(module.get('id', '')))
                id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, 0, id_item)

                # Name
                name_item = QTableWidgetItem(module.get('name', ''))
                self.table.setItem(row, 1, name_item)

                # Documents
                doc_item = QTableWidgetItem(str(module.get('document_count', 0)))
                doc_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, 2, doc_item)

                # Images
                img_item = QTableWidgetItem(str(module.get('image_count', 0)))
                img_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, 3, img_item)

                # Sessions
                session_item = QTableWidgetItem(str(module.get('session_count', 0)))
                session_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, 4, session_item)

        except Exception as e:
            show_warning(self, "Error", f"Failed to load campaigns: {e}")

    def _on_select(self):
        """Handle select button click."""
        selected_rows = self.table.selectedItems()
        if not selected_rows:
            show_warning(self, "No Selection", "Please select a campaign to backup.")
            return

        row = self.table.currentRow()
        if row >= 0:
            id_item = self.table.item(row, 0)
            if id_item:
                self.selected_module_id = int(id_item.text())
                self.accept()

    def _on_double_click(self):
        """Handle double-click on table row."""
        self._on_select()

    def get_selected_module_id(self) -> Optional[int]:
        """Get the selected campaign ID."""
        return self.selected_module_id


class RestoreOptionsDialog(QDialog):
    """Dialog for selecting restore options."""

    def __init__(self, db_manager, metadata: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.metadata = metadata
        self.restore_mode = None
        self.target_module_id = None

        self.setWindowTitle("Restore Campaign Options")
        self.setModal(True)
        self.resize(500, 400)

        self._setup_ui()

    def _setup_ui(self):
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)

        # Backup information
        info_group = QGroupBox("Backup Information")
        info_layout = QFormLayout(info_group)

        module_name = self.metadata.get('module_name', 'Unknown')
        backup_date = self.metadata.get('backup_date', 'Unknown')
        image_count = self.metadata.get('actual_image_count',
                                       self.metadata.get('image_count', 0))
        doc_count = self.metadata.get('document_count', 0)
        session_count = self.metadata.get('session_count', 0)

        def plain(value) -> QLabel:
            # The values come from the backup file, which may be hostile: never render them as HTML
            label = QLabel(str(value))
            label.setTextFormat(Qt.TextFormat.PlainText)
            return label

        info_layout.addRow("Campaign Name:", plain(module_name))
        info_layout.addRow("Backup Date:", plain(str(backup_date)[:19]))
        info_layout.addRow("Documents:", plain(doc_count))
        info_layout.addRow("Images:", plain(image_count))
        info_layout.addRow("Sessions:", plain(session_count))

        layout.addWidget(info_group)

        # Restore mode selection
        mode_group = QGroupBox("Restore Options")
        mode_layout = QVBoxLayout(mode_group)

        self.mode_button_group = QButtonGroup(self)

        # New module option
        self.new_module_radio = QRadioButton("Create as new campaign")
        self.new_module_radio.setChecked(True)
        self.new_module_radio.setToolTip(
            "Create a new campaign with a timestamp suffix.\n"
            "Original campaigns remain untouched."
        )
        self.mode_button_group.addButton(self.new_module_radio)
        mode_layout.addWidget(self.new_module_radio)

        # Overwrite option
        self.overwrite_radio = QRadioButton("Overwrite existing campaign")
        self.overwrite_radio.setToolTip(
            "Replace an existing campaign's data.\n"
            "WARNING: This will permanently delete the old campaign data!"
        )
        self.mode_button_group.addButton(self.overwrite_radio)
        self.overwrite_radio.toggled.connect(self._on_mode_changed)
        mode_layout.addWidget(self.overwrite_radio)

        # Module selection combo (for overwrite mode)
        overwrite_layout = QHBoxLayout()
        overwrite_layout.addSpacing(20)
        self.module_combo_label = QLabel("Target campaign:")
        self.module_combo_label.setEnabled(False)
        overwrite_layout.addWidget(self.module_combo_label)

        self.module_combo = QComboBox()
        self.module_combo.setEnabled(False)
        self._load_modules()
        overwrite_layout.addWidget(self.module_combo)

        mode_layout.addLayout(overwrite_layout)

        layout.addWidget(mode_group)

        # Warning label
        self.warning_label = QLabel("")
        set_props(self.warning_label, state="error")
        self.warning_label.setWordWrap(True)
        self.warning_label.setVisible(False)
        layout.addWidget(self.warning_label)

        layout.addStretch()

        # Button bar
        button_bar = DialogButtonBar(self)
        restore_btn = button_bar.add_button("Restore")
        restore_btn.clicked.connect(self._on_restore)
        cancel_btn = button_bar.add_button("Cancel")
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(button_bar)

    def _load_modules(self):
        """Load active campaigns into the combo box."""
        try:
            modules = self.db.get_all_modules_with_statistics()
            active_modules = [m for m in modules if m.get('is_active', 1)]

            for module in active_modules:
                module_id = module.get('id')
                module_name = module.get('name', 'Unknown')
                doc_count = module.get('document_count', 0)

                display_text = f"{module_name} (ID: {module_id}, {doc_count} docs)"
                self.module_combo.addItem(display_text, module_id)

        except Exception as e:
            show_warning(self, "Error", f"Failed to load campaigns: {e}")

    def _on_mode_changed(self):
        """Handle restore mode change."""
        is_overwrite = self.overwrite_radio.isChecked()

        self.module_combo_label.setEnabled(is_overwrite)
        self.module_combo.setEnabled(is_overwrite)

        if is_overwrite:
            self.warning_label.setText(
                "⚠ WARNING: Overwrite mode will permanently delete the target campaign's "
                "database and images. This action cannot be undone!"
            )
            self.warning_label.setVisible(True)
        else:
            self.warning_label.setVisible(False)

    def _on_restore(self):
        """Handle restore button click."""
        if self.new_module_radio.isChecked():
            self.restore_mode = "new"
            self.target_module_id = None
            self.accept()
        elif self.overwrite_radio.isChecked():
            if self.module_combo.currentIndex() < 0:
                show_warning(self, "No Selection", "Please select a campaign to overwrite.")
                return

            self.restore_mode = "overwrite"
            self.target_module_id = self.module_combo.currentData()
            self.accept()

    def get_restore_options(self) -> tuple[Optional[str], Optional[int]]:
        """
        Get the selected restore options.

        Returns:
            Tuple of (restore_mode, target_module_id)
        """
        return self.restore_mode, self.target_module_id
