"""
Campaign Manager Dialog for RPG Database Manager.
"""

from gui.theme import get_theme_manager, to_qcolor
from gui.theme import set_props
from typing import Optional, Dict, Any
from datetime import datetime

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QInputDialog, QLabel
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QBrush

from models.database import DatabaseManager
from utils.logger import get_logger
from utils.ui_helpers import show_error, show_warning, show_info, show_question


class ModuleManagerDialog(QDialog):
    """Dialog for managing campaigns (view, rename, delete, restore)."""

    module_changed = pyqtSignal()  # Emitted when modules are modified

    def __init__(self, db_manager: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.logger = get_logger('module_manager')

        self.setWindowTitle("Campaign Manager")
        self.setMinimumSize(900, 500)

        self._setup_ui()
        self._load_modules()

    def _setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)

        # Header label
        header = QLabel("Manage Campaigns")
        header.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        set_props(header, role="h1")
        layout.addWidget(header)

        # Module table
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "ID", "Name", "Status", "Documents", "Images", "Sessions",
            "Created", "DB Size (KB)"
        ])

        # Set column widths
        self.table.setColumnWidth(0, 50)   # ID
        self.table.setColumnWidth(1, 250)  # Name
        self.table.setColumnWidth(2, 80)   # Status
        self.table.setColumnWidth(3, 90)   # Documents
        self.table.setColumnWidth(4, 80)   # Images
        self.table.setColumnWidth(5, 80)   # Sessions
        self.table.setColumnWidth(6, 120)  # Created
        self.table.setColumnWidth(7, 100)  # DB Size

        # Table settings
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(False)

        layout.addWidget(self.table)

        # Button layout
        button_layout = QHBoxLayout()

        self.rename_btn = QPushButton("Rename")
        self.rename_btn.clicked.connect(self._on_rename)
        button_layout.addWidget(self.rename_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setToolTip("Soft delete (hide) the selected campaign")
        self.delete_btn.clicked.connect(self._on_delete)
        button_layout.addWidget(self.delete_btn)

        self.restore_btn = QPushButton("Restore")
        self.restore_btn.setToolTip("Restore a soft-deleted campaign")
        self.restore_btn.clicked.connect(self._on_restore)
        button_layout.addWidget(self.restore_btn)

        self.discord_btn = QPushButton("Discord channel...")
        self.discord_btn.setToolTip("Choose the Discord channel that is preselected for this campaign")
        self.discord_btn.clicked.connect(self._on_discord_channel)
        button_layout.addWidget(self.discord_btn)

        button_layout.addStretch()

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self._load_modules)
        button_layout.addWidget(self.refresh_btn)

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.close_btn)

        layout.addLayout(button_layout)

    def _load_modules(self):
        """Load and display all campaigns (active and inactive) using optimized batch query."""
        try:
            # Get all modules with statistics in a single optimized query
            all_modules = self.db.get_all_modules_with_statistics()

            # Clear table
            self.table.setRowCount(0)

            # Populate table
            for module in all_modules:
                self._add_module_row(module)

            # Count active vs inactive
            active_count = sum(1 for m in all_modules if m.get('is_active', 1))
            inactive_count = len(all_modules) - active_count

            self.logger.info(f"Loaded {len(all_modules)} campaigns ({active_count} active, {inactive_count} inactive)")

        except Exception as e:
            self.logger.error(f"Error loading campaigns: {e}", exc_info=True)
            show_error(self, "Error", f"Failed to load campaigns: {e}")

    def _add_module_row(self, module: Dict[str, Any]):
        """Add a campaign to the table."""
        row = self.table.rowCount()
        self.table.insertRow(row)

        # ID
        id_item = QTableWidgetItem(str(module.get('id', '')))
        id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, 0, id_item)

        # Name
        name_item = QTableWidgetItem(module.get('name', ''))
        self.table.setItem(row, 1, name_item)

        # Status
        is_active = module.get('is_active', True)
        status_item = QTableWidgetItem("Active" if is_active else "Deleted")
        status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        # Color code: Green for active, Red for deleted
        if is_active:
            status_item.setForeground(QBrush(to_qcolor(get_theme_manager().tokens()['success'])))
        else:
            status_item.setForeground(QBrush(to_qcolor(get_theme_manager().tokens()['danger'])))

        self.table.setItem(row, 2, status_item)

        # Documents
        doc_item = QTableWidgetItem(str(module.get('document_count', 0)))
        doc_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, 3, doc_item)

        # Images
        img_item = QTableWidgetItem(str(module.get('image_count', 0)))
        img_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, 4, img_item)

        # Sessions
        session_item = QTableWidgetItem(str(module.get('session_count', 0)))
        session_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, 5, session_item)

        # Created date
        created_date = module.get('created_date', '')
        if created_date:
            try:
                # Format datetime
                dt = datetime.fromisoformat(created_date.replace('Z', '+00:00'))
                formatted_date = dt.strftime('%Y-%m-%d %H:%M')
            except (ValueError, AttributeError, TypeError) as e:
                # Handle date parsing errors gracefully
                self.logger.debug(f"Could not parse date '{created_date}': {e}")
                formatted_date = str(created_date)[:16]
        else:
            formatted_date = 'N/A'

        date_item = QTableWidgetItem(formatted_date)
        date_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, 6, date_item)

        # Database size
        db_size = module.get('database_size', 0)
        size_kb = db_size / 1024 if db_size else 0
        size_item = QTableWidgetItem(f"{size_kb:.1f}")
        size_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, 7, size_item)

    def _get_selected_module(self) -> Optional[Dict[str, Any]]:
        """Get the currently selected campaign."""
        selected_rows = self.table.selectedItems()
        if not selected_rows:
            return None

        row = self.table.currentRow()
        if row < 0:
            return None

        # Get module data from table with null safety
        id_item = self.table.item(row, 0)
        name_item = self.table.item(row, 1)
        status_item = self.table.item(row, 2)

        # Defensive check: ensure all items exist
        if not id_item or not name_item or not status_item:
            self.logger.warning(f"Table items are None for row {row}, cannot get selected campaign")
            return None

        try:
            module_id = int(id_item.text())
            module_name = name_item.text()
            is_active = status_item.text() == "Active"

            return {
                'id': module_id,
                'name': module_name,
                'is_active': is_active
            }
        except (ValueError, AttributeError) as e:
            self.logger.error(f"Error parsing campaign data from table row {row}: {e}")
            return None

    def _on_discord_channel(self):
        """Choose the campaign's default Discord channel."""
        selected = self._get_selected_module()
        if not selected:
            show_warning(self, "No campaign selected", "Select a campaign first.")
            return
        from gui.dialogs.module_discord_channel_dialog import ModuleDiscordChannelDialog
        module = self.db.get_module(selected['id']) or selected
        if ModuleDiscordChannelDialog(self.db, module, self).exec():
            self.module_changed.emit()

    def _on_rename(self):
        """Handle rename button click."""
        module = self._get_selected_module()
        if not module:
            show_warning(self, "No Selection", "Please select a campaign to rename.")
            return

        # Get new name from user
        new_name, ok = QInputDialog.getText(
            self,
            "Rename Campaign",
            f"Enter new name for campaign '{module['name']}':",
            text=module['name']
        )

        if ok and new_name.strip():
            if new_name.strip() == module['name']:
                return  # No change

            # Rename the module
            success = self.db.rename_module(module['id'], new_name.strip())

            if success:
                show_info(self, "Success", f"Campaign renamed to '{new_name}'")
                self._load_modules()
                self.module_changed.emit()
            else:
                show_error(self, "Error", "Failed to rename campaign.")

    def _on_delete(self):
        """Handle delete button click (soft delete)."""
        module = self._get_selected_module()
        if not module:
            show_warning(self, "No Selection", "Please select a campaign to delete.")
            return

        if not module['is_active']:
            show_warning(self, "Already Deleted", "This campaign is already deleted.")
            return

        # Get statistics for confirmation
        stats = self.db.get_module_statistics(module['id'])

        # Confirmation message
        message = (
            f"Are you sure you want to delete the campaign '{module['name']}'?\n\n"
            f"This will hide the campaign from the active list, but all data will be preserved:\n"
            f"  - {stats.get('document_count', 0)} documents\n"
            f"  - {stats.get('image_count', 0)} images\n"
            f"  - {stats.get('session_count', 0)} game sessions\n\n"
            f"You can restore it later from the Campaign Manager."
        )

        if show_question(self, "Confirm Delete", message):
            success = self.db.soft_delete_module(module['id'])

            if success:
                show_info(self, "Success", f"Module '{module['name']}' has been deleted (hidden).")
                self._load_modules()
                self.module_changed.emit()
            else:
                show_error(self, "Error", "Failed to delete campaign.")

    def _on_restore(self):
        """Handle restore button click."""
        module = self._get_selected_module()
        if not module:
            show_warning(self, "No Selection", "Please select a campaign to restore.")
            return

        if module['is_active']:
            show_warning(self, "Already Active", "This campaign is already active.")
            return

        # Restore the module
        success = self.db.restore_module(module['id'])

        if success:
            show_info(self, "Success", f"Module '{module['name']}' has been restored.")
            self._load_modules()
            self.module_changed.emit()
        else:
            show_error(self, "Error", "Failed to restore campaign.")
