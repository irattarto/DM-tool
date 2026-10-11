"""
Simplified session widget for RPG Database Manager - uses DocumentViewerWindow popup pattern.
"""

from typing import Optional, Any
from datetime import date

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTreeWidget, QTreeWidgetItem, QHeaderView, QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSignal

from models.session import GameSession
from models.document import Document
from services.session_service import SessionService
from gui.dialogs.document_viewer import DocumentViewerWindow
from utils.logger import get_logger
from utils.ui_helpers import show_error, show_question, show_warning, show_info
from config.settings import Settings


class SessionWidget(QWidget):
    """Widget for managing game sessions using DocumentViewerWindow popup pattern."""

    # Signals
    session_created = pyqtSignal(int)  # session_id
    session_selected = pyqtSignal(int)  # session_id

    def __init__(self, session_service: SessionService, module_id: int, template_service: Optional[Any] = None, settings: Optional[Settings] = None):
        super().__init__()

        self.session_service = session_service
        self.template_service = template_service
        self.module_id = module_id
        self.sessions = []
        self.settings = settings

        self.logger = get_logger('session_widget')

        self._setup_ui()
        self._load_sessions()

    def _setup_ui(self):
        """Setup the session widget UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        layout.setContentsMargins(5, 5, 5, 5)

        # Combined toolbar with search and action buttons (matching entity tabs pattern)
        toolbar_layout = QHBoxLayout()

        # Search/filter on the left
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search sessions...")
        self.search_edit.textChanged.connect(self._filter_sessions)
        toolbar_layout.addWidget(self.search_edit)

        # Stretch to push buttons to the right
        toolbar_layout.addStretch()

        # Action buttons on the right (matching entity tabs pattern)
        self.new_session_btn = QPushButton("New Session")
        self.new_session_btn.clicked.connect(self._on_new_session)
        toolbar_layout.addWidget(self.new_session_btn)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self._load_sessions)
        toolbar_layout.addWidget(self.refresh_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setToolTip("Delete selected session")
        self.delete_btn.clicked.connect(self._on_delete_session)
        toolbar_layout.addWidget(self.delete_btn)

        layout.addLayout(toolbar_layout)

        # Sessions tree widget
        self.sessions_tree = QTreeWidget()
        self.sessions_tree.setHeaderLabels(["Title", "Date", "Status", "Participants"])
        self.sessions_tree.setAlternatingRowColors(True)
        self.sessions_tree.setSortingEnabled(True)

        # Load sort preference from settings or use default (Date column, descending)
        if self.settings:
            saved_column, saved_order_str = self.settings.get_session_sort_preference()
            saved_order = Qt.SortOrder.AscendingOrder if saved_order_str == 'asc' else Qt.SortOrder.DescendingOrder
        else:
            saved_column = 1  # Date column
            saved_order = Qt.SortOrder.DescendingOrder

        # Set sort based on saved preference
        self.sessions_tree.sortByColumn(saved_column, saved_order)

        # Set column widths - Interactive allows user resizing
        header = self.sessions_tree.header()

        # Connect to sort indicator changed signal to save user's sort preference
        header.sortIndicatorChanged.connect(self._on_sort_changed)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)  # Title
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)  # Date
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)  # Status
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)  # Participants

        # Restore saved column widths or use defaults
        if self.settings:
            saved_widths = self.settings.get_column_widths('sessions')
            if saved_widths and len(saved_widths) == 4:
                for i, width in enumerate(saved_widths):
                    header.resizeSection(i, width)
            else:
                # Set default widths
                header.resizeSection(0, 250)  # Title
                header.resizeSection(1, 100)  # Date
                header.resizeSection(2, 100)  # Status
                header.resizeSection(3, 200)  # Participants
        else:
            # Set default widths if no settings available
            header.resizeSection(0, 250)  # Title
            header.resizeSection(1, 100)  # Date
            header.resizeSection(2, 100)  # Status
            header.resizeSection(3, 200)  # Participants

        # Connect to save column widths when resized
        header.sectionResized.connect(self._on_column_resized)

        # Connect double-click to open in popup
        self.sessions_tree.itemDoubleClicked.connect(self._on_session_double_clicked)

        layout.addWidget(self.sessions_tree)

        self.logger.debug("Session widget UI setup completed")

    def _load_sessions(self):
        """Load sessions for the current campaign."""
        try:
            self.logger.debug(f"Loading sessions for module_id: {self.module_id}")

            self.sessions = self.session_service.get_sessions(self.module_id)
            self.logger.debug(f"Loaded {len(self.sessions)} sessions")

            self._populate_sessions_tree()

        except Exception as e:
            self.logger.error(f"Error loading sessions: {e}")
            show_error(self, "Error", f"Failed to load sessions: {e}")

    def _populate_sessions_tree(self, filter_text: str = ""):
        """Populate the sessions tree widget."""
        self.sessions_tree.clear()

        for session in self.sessions:
            # Apply filter if provided
            if filter_text:
                if filter_text.lower() not in session.title.lower():
                    continue

            item = QTreeWidgetItem()
            item.setText(0, session.title or "Untitled")
            item.setText(1, session.session_date or "")
            item.setText(2, session.status or "planned")
            item.setText(3, ", ".join(session.participants) if session.participants else "")

            # Store session data in item
            item.setData(0, Qt.ItemDataRole.UserRole, session)

            self.sessions_tree.addTopLevelItem(item)

    def _filter_sessions(self, text: str):
        """Filter sessions based on search text."""
        self._populate_sessions_tree(filter_text=text)

    def _on_session_double_clicked(self, item: QTreeWidgetItem, column: int):
        """Handle session double-click - open in DocumentViewerWindow popup."""
        try:
            session = item.data(0, Qt.ItemDataRole.UserRole)
            if session:
                self.logger.debug(f"Opening session in popup: ID={session.id}, title={session.title}")

                # Convert GameSession to Document for DocumentViewerWindow
                document = self._session_to_document(session)

                # Open in DocumentViewerWindow popup
                viewer_window = DocumentViewerWindow(document, self._get_database_manager(), self)
                viewer_window.show()

                self.session_selected.emit(session.id)

        except Exception as e:
            self.logger.error(f"Error opening session: {e}")
            show_error(self, "Error", f"Failed to open session: {e}")

    def _on_new_session(self):
        """Handle new session creation."""
        try:
            current_date = date.today()
            default_title = f"Session {current_date}"

            # Get default session template and apply it
            content = ""
            if self.template_service:
                template = self.template_service.get_default_template("session")
                if template:
                    content = self.template_service.apply_template(template, {})

            # Create session document with template content
            session_id = self.session_service.create_session(
                module_id=self.module_id,
                session_date=current_date,
                title=default_title,
                content=content,
                participants=[],
                duration_minutes=None
            )

            if session_id:
                self._load_sessions()
                self.session_created.emit(session_id)

                # Open the new session immediately in popup
                session = self.session_service.get_session(session_id)
                if session:
                    document = self._session_to_document(session)
                    viewer_window = DocumentViewerWindow(document, self._get_database_manager(), self)
                    viewer_window.show()
            else:
                show_error(self, "Error", "Failed to create session.")

        except Exception as e:
            self.logger.error(f"Error creating session: {e}")
            show_error(self, "Error", f"Failed to create session: {e}")

    def _on_delete_session(self):
        """Handle session deletion from list."""
        try:
            # Get selected item
            current_item = self.sessions_tree.currentItem()
            if not current_item:
                show_warning(self, "No Selection", "Please select a session to delete.")
                return

            session = current_item.data(0, Qt.ItemDataRole.UserRole)
            if not session:
                return

            # Confirm deletion
            response = show_question(
                self,
                "Confirm Deletion",
                f"Are you sure you want to delete '{session.title}'?\nThis action cannot be undone."
            )

            if response:
                # Delete via session service
                self.session_service.delete_session(session.id)
                self.logger.info(f"Deleted session: {session.title} (ID: {session.id})")

                # Refresh the list
                self._load_sessions()
                show_info(self, "Success", f"Session '{session.title}' deleted successfully.")

        except Exception as e:
            self.logger.error(f"Error deleting session: {e}")
            show_error(self, "Error", f"Failed to delete session: {e}")

    def _session_to_document(self, session: GameSession) -> Document:
        """Convert a GameSession to a Document for DocumentViewerWindow."""
        import json

        # Build metadata JSON with session-specific fields
        metadata = {
            'session_date': session.session_date,
            'status': session.status,
            'participants': session.participants,
            'duration_minutes': session.duration_minutes
        }

        return Document(
            id=session.id,
            module_id=session.module_id,
            entity_type='session',
            title=session.title,
            content=session.content,
            metadata=json.dumps(metadata)
        )

    def _get_database_manager(self):
        """Get database manager from parent window."""
        # Traverse up the widget hierarchy to find main window
        parent = self.parent()
        while parent:
            if hasattr(parent, 'db'):
                return parent.db
            parent = parent.parent()

        self.logger.error("Could not find database manager in parent hierarchy")
        return None

    def set_module_id(self, module_id: int):
        """Update the campaign ID and refresh session data."""
        self.module_id = module_id
        self._load_sessions()

    def refresh_data(self):
        """Refresh all session data."""
        self._load_sessions()

    def _on_column_resized(self, index: int, old_size: int, new_size: int):
        """Save column widths when a column is resized."""
        if self.settings:
            header = self.sessions_tree.header()
            widths = [header.sectionSize(i) for i in range(header.count())]
            self.settings.set_column_widths('sessions', widths)

    def _on_sort_changed(self, column: int, order: Qt.SortOrder):
        """Save sort preference when user changes the sort column or order."""
        if self.settings:
            order_str = 'asc' if order == Qt.SortOrder.AscendingOrder else 'desc'
            self.settings.set_session_sort_preference(column, order_str)
            self.settings.save_settings()
            self.logger.debug(f"Session sort changed: column={column}, order={order_str}")

    def cleanup(self):
        """Clean up widget resources."""
        try:
            self.sessions_tree.clear()
            self.sessions = []
        except (RuntimeError, AttributeError):
            pass
