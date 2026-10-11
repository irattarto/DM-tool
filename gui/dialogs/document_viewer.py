"""
Document viewer window for viewing and editing individual documents.
"""

import json

from config.entity_types import get_registry, CAP_SESSION, CAP_FACTION_LINK, CAP_ABILITIES, CAP_INVENTORY
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTabWidget,
    QComboBox, QDateEdit, QFormLayout, QGroupBox, QMessageBox
)
from PyQt6.QtCore import QTimer, QDate, Qt

from gui.theme import set_props
from models.database import DatabaseManager
from models.document import Document
from services.image_service import ImageService
from utils.logger import get_logger
from utils.ui_helpers import show_error, show_warning, show_question
from utils.sounds import play_recording_stopped, prepare_recording_stopped
from gui.image_gallery_widget import ImageGalleryWidget
from gui.primary_image_widget import PrimaryImageWidget
from gui.widgets.formatted_text_edit import FormattedTextEdit
from gui.ability_widget import AbilityWidget
from gui.inventory_widget import InventoryWidget
from utils.audio_recording import AudioRecordingThread, microphone_support_status
from config.settings import Settings


class DocumentViewerWindow(QMainWindow):
    """Window for viewing and editing individual documents."""

    def __init__(self, document: Document, database_manager: DatabaseManager, parent=None):
        super().__init__(parent)
        self.document = document
        self.db = database_manager
        self.logger = get_logger('document_viewer')

        # Find MainWindow by traversing parent hierarchy
        self.main_window = self._find_main_window(parent)

        self.setWindowTitle(f"{get_registry().label(document.entity_type)}: {document.title}")
        self.setMinimumSize(800, 600)
        self._updating_display = False
        self._is_dirty = False  # Track if document has unsaved changes

        # Speech-to-text state
        # Use the live settings of the main window (not defaults) when there is one
        self.settings = getattr(self.main_window, 'settings', None) or Settings()
        self._recording_active = False
        self._recording_timeout_timer = QTimer()  # Timeout protection
        self._recording_timeout_timer.setSingleShot(True)
        self._recording_timeout_timer.timeout.connect(self._on_recording_timeout)
        self._recording_thread = None
        self._transcription_worker = None

        self._setup_ui()
        self._display_document()

    def _find_main_window(self, widget):
        """
        Find MainWindow by traversing up the widget hierarchy.

        Args:
            widget: Starting widget (usually parent)

        Returns:
            MainWindow instance if found, None otherwise
        """
        from gui.main_window import MainWindow

        current = widget
        while current is not None:
            if isinstance(current, MainWindow):
                self.logger.debug(f"Found MainWindow: {current}")
                return current
            # Try to get parent
            if hasattr(current, 'parent'):
                current = current.parent()
            elif hasattr(current, 'parentWidget'):
                current = current.parentWidget()
            else:
                break

        self.logger.warning(f"MainWindow not found in parent hierarchy starting from {widget}")
        return None

    _RELATION_LABELS = {
        ('belongs_to_module', 'out'): "Part of module",
        ('belongs_to_module', 'in'): "Contents of this module",
        ('appears_in_session', 'out'): "Appears in sessions",
        ('appears_in_session', 'in'): "In this session",
        ('member_of', 'out'): "Member of",
        ('member_of', 'in'): "Members",
        ('references', 'out'): "Mentions",
        ('references', 'in'): "Mentioned by",
    }

    def _module_title(self) -> str:
        """Title of the adventure module this document was imported from, or ''."""
        try:
            module_doc_id = json.loads(self.document.metadata).get('module_doc_id') if self.document.metadata else None
            module_doc = self.db.get_document(module_doc_id) if module_doc_id is not None else None
            return module_doc['title'] if module_doc else ''
        except (TypeError, ValueError, AttributeError):
            return ''

    def _build_connections_tab(self):
        """Read-only list of linked documents, or None when there are none."""
        import html
        from PyQt6.QtWidgets import QTextBrowser

        try:
            rows = self.db.get_relationships_for_document(self.document.id)
        except Exception as e:
            self.logger.warning(f"Could not load connections: {e}")
            return None
        if not rows:
            return None

        registry = get_registry()
        sections = {}
        for row in rows:
            key = (row['relationship_type'], row['direction'])
            sections.setdefault(key, []).append(row)

        parts = []
        for key in sorted(sections, key=lambda k: (k[0] != 'belongs_to_module', k[0], k[1])):
            label = self._RELATION_LABELS.get(key, f"{key[0].replace('_', ' ').capitalize()} ({key[1]})")
            items = ''.join(
                f'<li><a href="rpg://{html.escape(r["other_type"])}/{int(r["other_id"])}">'
                f'{html.escape(r["other_title"])}</a> <i>({html.escape(registry.label(r["other_type"]))})</i></li>'
                for r in sections[key])
            parts.append(f"<h4>{html.escape(label)}</h4><ul>{items}</ul>")

        browser = QTextBrowser()
        browser.setOpenLinks(False)
        browser.setHtml(''.join(parts))
        browser.anchorClicked.connect(self._on_connection_clicked)
        return browser

    def _on_connection_clicked(self, url):
        if self.main_window is not None and hasattr(self.main_window, '_handle_internal_link'):
            self.main_window._handle_internal_link(url)

    def _setup_ui(self):
        """Setup the document viewer UI."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)

        # Header with entity type
        header_layout = QHBoxLayout()
        self.entity_type_label = QLabel(f"Entity Type: {get_registry().label(self.document.entity_type)}")
        header_layout.addWidget(self.entity_type_label)
        module_title = self._module_title()
        if module_title:
            self.module_badge = QLabel(f"Module: {module_title}")
            self.module_badge.setToolTip("The adventure module this entry belongs to")
            set_props(self.module_badge, role="accent")
            header_layout.addWidget(self.module_badge)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Create tab widget
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget, 1)  # Stretch to fill space

        # Tab 1: Details (title and content)
        details_tab = QWidget()
        details_layout = QVBoxLayout(details_tab)

        # Title editor with primary image
        title_layout = QHBoxLayout()

        # Primary image thumbnail (50x50px) on the left
        self.primary_image_widget = PrimaryImageWidget(
            document_id=self.document.id,
            document_title=self.document.title,
            db_manager=self.db,
            parent=self
        )
        self.primary_image_widget.go_to_images_tab.connect(self._go_to_images_tab)
        title_layout.addWidget(self.primary_image_widget)

        # Title field
        title_layout.addWidget(QLabel("Title:"))
        self.title_edit = QLineEdit()
        self.title_edit.textChanged.connect(self._on_title_changed)
        title_layout.addWidget(self.title_edit)
        details_layout.addLayout(title_layout)

        # Session-specific fields (if entity type is session)
        if get_registry().has_capability(self.document.entity_type, CAP_SESSION):
            session_details_group = QGroupBox("Session Details")
            session_details_layout = QFormLayout(session_details_group)

            # Session date
            self.session_date_edit = QDateEdit()
            self.session_date_edit.setDate(QDate.currentDate())
            self.session_date_edit.setCalendarPopup(True)
            self.session_date_edit.dateChanged.connect(self._on_session_field_changed)
            session_details_layout.addRow("Date:", self.session_date_edit)

            # Session status
            self.session_status_combo = QComboBox()
            self.session_status_combo.addItems(['planned', 'active', 'played'])
            self.session_status_combo.currentTextChanged.connect(self._on_session_field_changed)
            session_details_layout.addRow("Status:", self.session_status_combo)

            # Participants (simple text field for now)
            self.session_participants_edit = QLineEdit()
            self.session_participants_edit.setPlaceholderText("Comma-separated names")
            self.session_participants_edit.textChanged.connect(self._on_session_field_changed)
            session_details_layout.addRow("Participants:", self.session_participants_edit)

            details_layout.addWidget(session_details_group)

        # Content editor with formatting toolbar
        # Pass db_manager and module_id for link insertion dialog
        self.content_edit = FormattedTextEdit(
            parent=self,
            db_manager=self.db,
            module_id=self.document.module_id
        )
        self.content_edit.textChanged.connect(self._on_content_changed)

        # Connect internal link signal to MainWindow's handler
        if self.main_window and hasattr(self.main_window, '_handle_internal_link'):
            self.content_edit.internal_link_clicked.connect(self.main_window._handle_internal_link)
            self.logger.debug("Connected internal link handler to MainWindow")
        else:
            self.logger.warning("Could not connect internal link handler - MainWindow not found or missing method")


        # Add formatting toolbar (from FormattedTextEdit)
        format_toolbar = self.content_edit.create_format_toolbar()
        details_layout.addWidget(format_toolbar)
        details_layout.addWidget(self.content_edit)


        self.tab_widget.addTab(details_tab, "Details")

        # Tab 2: Images
        images_tab = QWidget()
        images_layout = QVBoxLayout(images_tab)

        # Create image gallery widget
        self.image_gallery = ImageGalleryWidget(
            module_id=self.document.module_id,
            document_id=self.document.id,
            db_manager=self.db,
            image_service=ImageService(),
            parent=self
        )
        # Connect primary_changed signal to refresh primary image widget
        self.image_gallery.primary_changed.connect(self._on_primary_changed)
        images_layout.addWidget(self.image_gallery)

        self.tab_widget.addTab(images_tab, "Images")

        connections_tab = self._build_connections_tab()
        if connections_tab is not None:
            self.tab_widget.addTab(connections_tab, "Connections")

        # For sessions, only show Details and Images tabs (skip Metadata, Abilities, Inventory)
        if get_registry().has_capability(self.document.entity_type, CAP_SESSION):
            # Sessions don't need Metadata, Abilities, or Inventory tabs
            pass
        # Tab 3: Metadata (only for NPCs currently)
        elif get_registry().has_capability(self.document.entity_type, CAP_FACTION_LINK):
            metadata_tab = QWidget()
            metadata_layout = QVBoxLayout(metadata_tab)

            # Faction selection
            faction_group_layout = QHBoxLayout()
            faction_group_layout.addWidget(QLabel("Faction:"))

            self.faction_combo = QComboBox()
            self.faction_combo.addItem("(None)", None)  # Default empty option

            # Populate with factions from current module
            try:
                factions = self.db.get_documents(self.document.module_id, 'faction')
                for faction in factions:
                    self.faction_combo.addItem(faction['title'], faction['id'])
                self.logger.debug(f"Loaded {len(factions)} factions for NPC metadata selector")
            except Exception as e:
                self.logger.error(f"Failed to load factions for metadata tab: {e}")

            faction_group_layout.addWidget(self.faction_combo)
            faction_group_layout.addStretch()

            metadata_layout.addLayout(faction_group_layout)

            # Add space for future metadata fields (race, class, etc.)
            metadata_layout.addStretch()

            self.tab_widget.addTab(metadata_tab, "Metadata")

        # Tab 4: Abilities (for characters and NPCs, but not sessions) - Multi-item management
        if get_registry().has_capability(self.document.entity_type, CAP_ABILITIES):
            # Create AbilityWidget for managing multiple ability items
            self.ability_widget = AbilityWidget(
                database_manager=self.db,
                module_id=self.document.module_id,
                parent_document_id=self.document.id
            )
            # Connect data modification signal to mark document as dirty
            self.ability_widget.data_modified.connect(lambda: setattr(self, '_is_dirty', True))

            self.tab_widget.addTab(self.ability_widget, "Abilities")

        # Tab 5: Inventory (for characters and NPCs, but not sessions) - Multi-item management
        if get_registry().has_capability(self.document.entity_type, CAP_INVENTORY):
            # Create InventoryWidget for managing multiple inventory items
            self.inventory_widget = InventoryWidget(
                database_manager=self.db,
                module_id=self.document.module_id,
                parent_document_id=self.document.id
            )
            # Connect data modification signal to mark document as dirty
            self.inventory_widget.data_modified.connect(lambda: setattr(self, '_is_dirty', True))

            self.tab_widget.addTab(self.inventory_widget, "Inventory")

        # Bottom button bar - speech-to-text on left, save/delete buttons on right
        bottom_layout = QHBoxLayout()

        # Speech-to-text button on the left
        self.stt_button = QPushButton("🎤 Record")
        self.stt_button.setToolTip("Click to start recording, click again to stop and transcribe")
        self.stt_button.clicked.connect(self._on_stt_button_clicked)
        mic_available, mic_reason = microphone_support_status()
        if not mic_available:
            self.stt_button.setEnabled(False)
            self.stt_button.setToolTip(mic_reason)
        bottom_layout.addWidget(self.stt_button)

        bottom_layout.addStretch()

        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self._on_save)
        bottom_layout.addWidget(self.save_btn)

        self.save_close_btn = QPushButton("Save && Close")
        self.save_close_btn.clicked.connect(self._on_save_close)
        bottom_layout.addWidget(self.save_close_btn)

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self._on_close)
        bottom_layout.addWidget(self.close_btn)

        layout.addLayout(bottom_layout)

    def _display_document(self):
        """Display document content."""
        if self._updating_display:
            return

        self._updating_display = True
        try:
            self.title_edit.setText(self.document.title)
            # Load content - set_content() handles both HTML and plain text automatically
            self.content_edit.set_content(self.document.content or '')

            # Note: Abilities and Inventory are now managed as separate items
            # via AbilityWidget and InventoryWidget - no need to load old text fields

            # Load session-specific fields from metadata
            if get_registry().has_capability(self.document.entity_type, CAP_SESSION) and self.document.metadata:
                try:
                    metadata = json.loads(self.document.metadata)

                    # Load session date
                    if hasattr(self, 'session_date_edit'):
                        session_date_str = metadata.get('session_date')
                        if session_date_str:
                            from datetime import date
                            if isinstance(session_date_str, str):
                                session_date = date.fromisoformat(session_date_str)
                                self.session_date_edit.setDate(QDate(session_date.year, session_date.month, session_date.day))

                    # Load status
                    if hasattr(self, 'session_status_combo'):
                        status = metadata.get('status', 'planned')
                        index = self.session_status_combo.findText(status)
                        if index >= 0:
                            self.session_status_combo.setCurrentIndex(index)

                    # Load participants
                    if hasattr(self, 'session_participants_edit'):
                        participants = metadata.get('participants', [])
                        if isinstance(participants, list):
                            self.session_participants_edit.setText(", ".join(participants))
                        elif isinstance(participants, str):
                            self.session_participants_edit.setText(participants)

                    self.logger.debug(f"Loaded session metadata for session ID {self.document.id}")
                except json.JSONDecodeError as e:
                    self.logger.warning(f"Failed to parse session metadata: {e}")
                except Exception as e:
                    self.logger.error(f"Error loading session metadata: {e}")

            # Load metadata if exists (for NPCs)
            if hasattr(self, 'faction_combo') and self.document.metadata:
                try:
                    metadata = json.loads(self.document.metadata)
                    faction_id = metadata.get('faction_id')
                    if faction_id is not None:
                        # Find and select the faction in combo box
                        index = self.faction_combo.findData(faction_id)
                        if index >= 0:
                            self.faction_combo.setCurrentIndex(index)
                            self.logger.debug(f"Loaded faction_id {faction_id} from metadata")
                except json.JSONDecodeError as e:
                    self.logger.warning(f"Failed to parse document metadata: {e}")
                except Exception as e:
                    self.logger.error(f"Error loading faction from metadata: {e}")
        finally:
            self._updating_display = False
            # Reset dirty flag after loading document
            self._is_dirty = False

    def _on_title_changed(self):
        """Handle title changes."""
        if not self._updating_display:
            self.document.title = self.title_edit.text()
            self._is_dirty = True

    def _on_content_changed(self):
        """Handle content changes."""
        if not self._updating_display:
            self.document.content = self.content_edit.get_content()
            self._is_dirty = True

    def _on_session_field_changed(self):
        """Handle session-specific field changes."""
        if not self._updating_display:
            self._is_dirty = True

    # Note: _on_abilities_changed and _on_inventory_changed removed
    # Abilities and Inventory now managed via AbilityWidget/InventoryWidget
    # which emit data_modified signals when items are saved/deleted

    def _on_save(self):
        """Save document and images."""
        try:
            # Update document content from editor before saving
            self.document.content = self.content_edit.get_content()

            if not self.document.title.strip():
                show_warning(self, "Save Failed", "Document title cannot be empty.")
                return

            # Save any unsaved ability or inventory items first
            if hasattr(self, 'ability_widget'):
                if self.ability_widget.ability_form_component.is_dirty():
                    self.ability_widget._on_save_ability()

            if hasattr(self, 'inventory_widget'):
                if self.inventory_widget.inventory_form_component.is_dirty():
                    self.inventory_widget._on_save_item()

            # Build metadata JSON (for sessions and NPCs). Merge into what is stored so keys this
            # form does not edit (module_doc_id, source_id, import hashes, ...) survive a save.
            metadata_json = None
            existing_metadata = {}
            try:
                stored = self.db.get_document(self.document.id)
                if stored and stored.get('metadata'):
                    loaded = json.loads(stored['metadata'])
                    if isinstance(loaded, dict):
                        existing_metadata = loaded
            except (TypeError, ValueError) as e:
                self.logger.warning(f"Could not read stored metadata, saving form fields only: {e}")

            # Session-specific metadata
            if get_registry().has_capability(self.document.entity_type, CAP_SESSION):
                metadata = {}
                if hasattr(self, 'session_date_edit'):
                    date_obj = self.session_date_edit.date().toPyDate()
                    metadata['session_date'] = date_obj.isoformat()

                if hasattr(self, 'session_status_combo'):
                    metadata['status'] = self.session_status_combo.currentText()

                if hasattr(self, 'session_participants_edit'):
                    participants_text = self.session_participants_edit.text()
                    participants = [p.strip() for p in participants_text.split(',') if p.strip()]
                    metadata['participants'] = participants

                metadata['duration_minutes'] = None  # Could add duration field later

                if metadata:
                    metadata_json = json.dumps({**existing_metadata, **metadata})
                    self.logger.debug(f"Saving session metadata: {metadata}")

            # NPC-specific metadata
            elif hasattr(self, 'faction_combo'):
                metadata = dict(existing_metadata)
                faction_id = self.faction_combo.currentData()
                if faction_id is not None:
                    metadata['faction_id'] = faction_id
                    self.logger.debug(f"Saving faction_id {faction_id} to metadata")
                else:
                    metadata.pop('faction_id', None)    # "(None)" really clears the faction

                metadata_json = json.dumps(metadata)

            # Save document content with metadata
            success = self.db.update_document(
                self.document.id,
                self.document.title,
                self.document.content,
                metadata_json
            )

            if success:
                # Save images if the image gallery exists
                if hasattr(self, 'image_gallery'):
                    image_save_success = self.image_gallery.save_images(self.document.id)
                    if not image_save_success:
                        self.logger.warning("Some images may not have been saved properly")

                self.statusBar().showMessage(f"Saved: {self.document.title}")
                # Reset dirty flag after successful save
                self._is_dirty = False
                # Refresh the parent widget's data
                if hasattr(self.parent(), 'refresh_data'):
                    # SessionWidget uses refresh_data()
                    try:
                        self.parent().refresh_data()
                    except Exception as e:
                        self.logger.warning(f"Could not refresh parent data: {e}")
                elif hasattr(self.parent(), '_load_entity_documents'):
                    # Main window uses _load_entity_documents()
                    try:
                        self.parent()._load_entity_documents(self.document.entity_type)
                    except Exception as e:
                        self.logger.warning(f"Could not refresh parent document list: {e}")
            else:
                show_warning(
                    self,
                    "Save Failed",
                    "Failed to save document",
                    f"Document ID: {self.document.id}\nTitle: {self.document.title}\nError: Document save returned False"
                )

        except Exception as e:
            show_error(
                self,
                "Save Error",
                "Failed to save document",
                f"Document ID: {self.document.id}\nTitle: {self.document.title}\nError: {str(e)}"
            )

    def _on_save_close(self):
        """Save document and close window."""
        self._on_save()
        self.close()

    def _on_close(self):
        """Handle close button - check for unsaved changes."""
        self.close()  # Triggers closeEvent which handles unsaved changes

    def _on_primary_changed(self, image_id: int):
        """Handle primary image change from image gallery."""
        if hasattr(self, 'primary_image_widget'):
            self.primary_image_widget.refresh()
            self.logger.info(f"Primary image updated to image ID: {image_id}")

    def _go_to_images_tab(self):
        """Switch to the Images tab."""
        if hasattr(self, 'tab_widget'):
            self.tab_widget.setCurrentIndex(1)  # Images tab is index 1
            self.logger.debug("Switched to Images tab")

    def _retire_speech_threads(self):
        from gui.workers.lifecycle import retire_worker
        self._recording_timeout_timer.stop()
        for worker in (self._recording_thread, self._transcription_worker):
            if worker is not None and worker.isRunning():
                if hasattr(worker, 'stop_recording'):
                    worker.stop_recording()
                retire_worker(worker, 0)

    def closeEvent(self, event):
        """Handle window close event - check for unsaved changes."""
        if self._is_dirty:
            choice = self._ask_save_changes()
            if choice == "cancel":
                event.ignore()          # stay open: the click on close was a mistake
                return
            if choice == "save":
                self._on_save()
                if self._is_dirty:      # the save failed: do not lose the changes
                    event.ignore()
                    return
        event.accept()
        self._retire_speech_threads()

    def _ask_save_changes(self) -> str:
        """'save', 'discard' or 'cancel'."""
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Unsaved Changes")
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.setText(f"Save changes to '{self.document.title}' before closing?")
        save = box.addButton("Save", QMessageBox.ButtonRole.AcceptRole)
        discard = box.addButton("Discard changes", QMessageBox.ButtonRole.DestructiveRole)
        cancel = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(save)
        box.setEscapeButton(cancel)
        box.exec()
        clicked = box.clickedButton()
        return "save" if clicked is save else "discard" if clicked is discard else "cancel"

    def document_saved(self, document_id: int):
        """Signal emitted when document is saved."""
        # This can be used to refresh the main window's document lists

    # Speech-to-text functionality

    def _on_stt_button_clicked(self):
        """Toggle speech-to-text: the first click starts recording, the next one stops it and transcribes."""
        if self._recording_active:
            self._stop_recording()
            return
        limit = self._recording_limit_seconds()
        self.statusBar().showMessage(f"🎤 Recording... click again when done speaking (stops after {limit} s)")
        self._preload_local_model()
        prepare_recording_stopped()
        self._start_speech_recognition()
        if self._recording_active:
            self.stt_button.setText("🔴 Stop recording")

    GOOGLE_MAX_SECONDS = 60  # the free Google recognizer rejects recordings of about a minute or more

    def _recording_limit_seconds(self) -> int:
        """The 'maximum recording duration' from Preferences; Google's service cannot take more than a minute."""
        stt = self.settings.speech_to_text
        limit = stt.phrase_limit
        return min(limit, self.GOOGLE_MAX_SECONDS) if stt.provider == "google" else limit

    def _preload_local_model(self):
        """Load the local Whisper model while the user is still speaking (no-op when already loaded)."""
        stt = self.settings.speech_to_text
        if stt.provider != "whisper":
            return
        try:
            from services import local_stt
            if (stt.whisper_device != "cpu" and not stt.gpu_prompt_declined and local_stt.gpu_libs_missing()):
                return  # the GPU libraries will be offered first; do not load a CPU model meanwhile
            local_stt.preload(local_stt.resolve_plan(stt.whisper_model, stt.whisper_device))
        except Exception as e:
            self.logger.debug(f"Model preload skipped: {e}")

    def _stop_recording(self):
        """Stop the current recording session immediately."""
        if not self._recording_active:
            return

        # Stop timeout timer
        self._recording_timeout_timer.stop()
        self._recording_active = False

        # Stop the recording thread
        if self._recording_thread and self._recording_thread.isRunning():
            self._recording_thread.stop_recording()

        # The audio arrives in a moment; _set_transcribing takes over the button from there
        if self.stt_button:
            self.stt_button.setEnabled(False)
            self.stt_button.setText("⏳ Finishing...")

    def _start_speech_recognition(self):
        """Start continuous speech recognition."""
        if self._recording_active:
            return  # Already recording
        if self._recording_thread is not None and self._recording_thread.isRunning():
            self.statusBar().showMessage("Previous recording is still closing, try again in a moment")
            return  # never overwrite a running QThread

        self._recording_active = True

        try:
            # Start recording thread
            device_index = self.settings.speech_to_text.device_index
            self._recording_thread = AudioRecordingThread(device_index=device_index)
            self._recording_thread.recording_finished.connect(self._on_recording_finished)
            self._recording_thread.recording_error.connect(self._on_recording_error)
            self._recording_thread.start()

            # Safety limit: the 'maximum recording duration' from Preferences
            self._recording_timeout_timer.start(self._recording_limit_seconds() * 1000)

        except Exception as e:
            self.statusBar().showMessage(f"❌ Failed to start recording: {e}")
            self.logger.error(f"Recording start error: {e}")
            self._recording_active = False
            if self.stt_button:
                self.stt_button.setEnabled(True)
                self.stt_button.setText("🎤 Record")

    def _on_recording_finished(self, audio_data):
        """Handle completion of audio recording."""
        # Stop timeout timer
        self._recording_timeout_timer.stop()

        if not audio_data:
            self.statusBar().showMessage("❌ Recording failed - no audio captured")
            self._recording_active = False
            if self.stt_button:
                self.stt_button.setEnabled(True)
                self.stt_button.setText("🎤 Record")
            return

        # Check if audio has content
        if len(audio_data.frame_data) == 0:
            self.statusBar().showMessage("❌ Recording failed - empty audio")
            self._recording_active = False
            if self.stt_button:
                self.stt_button.setEnabled(True)
                self.stt_button.setText("🎤 Record")
            return

        self._recording_active = False
        try:
            self._start_transcription(audio_data)
        except Exception as e:
            self.statusBar().showMessage(f"❌ Could not start transcription: {e}")
            self.logger.error(f"Speech recognition error: {e}")
            self._set_transcribing(False)

    def _on_recording_error(self, error_message):
        """Handle recording error from thread."""
        # Stop timeout timer
        self._recording_timeout_timer.stop()

        self.logger.error(f"Recording error: {error_message}")
        self.statusBar().showMessage(f"❌ Recording failed: {error_message}", 5000)
        self._recording_active = False

        # Reset button state
        try:
            self.stt_button.setText("🎤 Record")
            self.stt_button.setEnabled(True)
        except Exception:
            pass

        # Show user-friendly error dialog for permission issues
        if "access" in error_message.lower() or "denied" in error_message.lower():
            from utils.ui_helpers import show_warning
            show_warning(
                self,
                "Microphone Access Denied",
                "Cannot access microphone. Please check:\n\n"
                "1. Windows Privacy Settings → Microphone\n"
                "2. Allow desktop apps to access microphone\n"
                "3. Microphone is not being used by another application\n\n"
                f"Error: {error_message}"
            )

    def _on_recording_timeout(self):
        """Handle recording timeout (safety mechanism)."""
        self.logger.info("Recording reached the maximum duration - stopping")
        if self._recording_active:
            self._stop_recording()
            play_recording_stopped()  # the user did not stop it, so tell them it has stopped
            self.statusBar().showMessage("Maximum recording time reached, transcribing...", 3000)

    def _start_transcription(self, audio_data):
        """Transcribe on a worker thread so the window stays responsive."""
        from gui.workers.transcription_worker import TranscriptionWorker
        stt = self.settings.speech_to_text
        if self._offer_gpu_libraries(audio_data):
            return  # the download runs first; the recording is transcribed when it finishes
        worker = TranscriptionWorker(audio_data, stt.provider, stt.language,
                                     stt.whisper_model, stt.whisper_device)
        worker.status.connect(self.statusBar().showMessage)
        worker.result_ready.connect(self._on_transcription_ready)
        worker.error.connect(lambda msg: self.statusBar().showMessage(f"❌ {msg}", 8000))
        worker.finished.connect(lambda w=worker: self._on_transcription_finished(w))
        self._transcription_worker = worker
        self._set_transcribing(True)
        worker.start()

    def _offer_gpu_libraries(self, audio_data) -> bool:
        """Offer (once) to download the NVIDIA CUDA libraries so the graphics card can be used.

        Returns True when a download was started; the pending recording is transcribed after it.
        """
        stt = self.settings.speech_to_text
        if (stt.provider != "whisper" or stt.whisper_device == "cpu" or stt.gpu_prompt_declined
                or getattr(self, '_gpu_download_failed', False)):
            return False
        try:
            from services import local_stt
            if not local_stt.gpu_libs_missing():
                return False
            gpu = local_stt.detect_hardware().gpu_name
        except Exception as e:
            self.logger.debug(f"GPU library check skipped: {e}")
            return False
        if not show_question(
                self, "Use the graphics card?",
                f"Your {gpu} can transcribe much faster than the processor, but it needs NVIDIA's CUDA libraries "
                "(about 1 GB, downloaded once from PyPI, checksum-verified).\n\nDownload them now?\n\n"
                "Choosing No keeps using the processor (slow with big models) and will not ask again."):
            stt.gpu_prompt_declined = True
            self.settings.save_settings()
            return False
        from gui.workers.cuda_download_worker import CudaDownloadWorker
        worker = CudaDownloadWorker(self)
        worker.status.connect(self.statusBar().showMessage)
        worker.done.connect(lambda: self._on_gpu_libraries_ready(audio_data))
        worker.error.connect(lambda msg: self._on_gpu_libraries_failed(msg, audio_data))
        worker.finished.connect(worker.deleteLater)
        self._cuda_worker = worker
        self._set_transcribing(True)
        worker.start()
        return True

    def _on_gpu_libraries_ready(self, audio_data):
        self._set_transcribing(False)
        self._start_transcription(audio_data)

    def _on_gpu_libraries_failed(self, message: str, audio_data):
        self.statusBar().showMessage(f"❌ {message} Transcribing on the processor instead.", 8000)
        self._gpu_download_failed = True  # do not ask again until the app is restarted
        self._set_transcribing(False)
        self._start_transcription(audio_data)

    def _set_transcribing(self, busy: bool):
        if self.stt_button:
            self.stt_button.setEnabled(not busy)
            self.stt_button.setText("⏳ Transcribing..." if busy else "🎤 Record")

    def _on_transcription_ready(self, text: str):
        if text:
            self._insert_transcribed_text(text)
            self.statusBar().showMessage("✅ Speech transcribed successfully", 5000)
        else:
            self.statusBar().showMessage("❌ Could not understand audio", 5000)

    def _on_transcription_finished(self, worker):
        if getattr(self, '_transcription_worker', None) is worker:
            self._transcription_worker = None
            self._set_transcribing(False)
        worker.deleteLater()

    def _insert_transcribed_text(self, text: str):
        """Insert transcribed text into the currently active tab's content field."""
        # Get the current tab index
        current_tab_index = self.tab_widget.currentIndex()

        # Only insert into Details tab (index 0) which has the content editor
        if current_tab_index == 0 and hasattr(self, 'content_edit'):
            cursor = self.content_edit.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            current_text = self.content_edit.toPlainText()
            if current_text and not current_text.endswith('\n'):
                cursor.insertText('\n')
            cursor.insertText(text + '\n')
        else:
            self.logger.warning("Speech-to-text only works in the Details tab with content field")
