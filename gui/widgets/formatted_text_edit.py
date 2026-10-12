"""
Formatted Text Edit Widget for RPG Database Manager.

A reusable QTextEdit widget with built-in text formatting capabilities,
including bold, italic, underline, strikethrough, color selection, and more.
"""

from PyQt6.QtWidgets import (
    QTextEdit, QToolBar, QMessageBox
)
from PyQt6.QtCore import pyqtSignal, QUrl
from PyQt6.QtGui import (
    QFont, QTextCharFormat, QColor, QAction, QKeySequence, QTextCursor,
    QTextListFormat, QDesktopServices
)

from gui.widgets.name_completer import NameCompleter
from utils.local_files import local_audio_path
from utils.name_matching import NameEntry
from utils.logger import get_logger


class FormattedTextEdit(QTextEdit):
    """
    QTextEdit with built-in text formatting capabilities.

    Features:
    - Bold, Italic, Underline, Strikethrough
    - Text color selection with color history
    - Font size adjustment
    - Clear formatting
    - Paste without formatting
    - Smart selection handling
    - HTML content support
    - Clickable links (external and internal)
    """

    # Signals
    formatting_changed = pyqtSignal()  # Emitted when text formatting changes
    internal_link_clicked = pyqtSignal(QUrl)  # Emitted when internal rpg:// link is clicked

    def __init__(self, parent=None, db_manager=None, module_id=None):
        super().__init__(parent)
        self.logger = get_logger('formatted_text_edit')

        # Store database manager and module ID for link insertion dialog
        self.db_manager = db_manager
        self.module_id = module_id

        # Store references to toolbar actions for state updates
        self._formatting_actions = {}

        # Enable mouse tracking for cursor changes on hover
        self.setMouseTracking(True)

        # Context menu will be handled by contextMenuEvent override
        # (No need to set custom context menu policy)

        # Tab completion of entry names (needs the database); the owner can switch it off or exclude its own entry
        self.exclude_doc_id = None
        self.create_entry_callback = None  # callable(kind, title) -> new document id, set by the owner window
        self.name_priorities = None        # optional callable returning ids that come first (pinned entries)
        self._name_cache = (0.0, [])
        self.completer = NameCompleter(self, self._name_entries)
        self.completer.enabled = bool(db_manager) and module_id is not None

        # Connect signals to update button states
        self.textChanged.connect(self._update_formatting_actions)
        self.cursorPositionChanged.connect(self._update_formatting_actions)
        self.selectionChanged.connect(self._update_formatting_actions)

    def create_format_toolbar(self) -> QToolBar:
        """
        Create and return a toolbar with formatting actions.

        Returns:
            QToolBar with all formatting actions configured
        """
        toolbar = QToolBar("Format")
        toolbar.setMovable(False)

        # Bold
        bold_action = QAction("Bold", self)
        bold_action.setShortcut(QKeySequence("Ctrl+B"))
        bold_action.setToolTip("Bold (Ctrl+B)")
        bold_action.setCheckable(True)
        bold_action.triggered.connect(self.toggle_bold)
        self._formatting_actions['bold'] = bold_action
        toolbar.addAction(bold_action)

        # Italic
        italic_action = QAction("Italic", self)
        italic_action.setShortcut(QKeySequence("Ctrl+I"))
        italic_action.setToolTip("Italic (Ctrl+I)")
        italic_action.setCheckable(True)
        italic_action.triggered.connect(self.toggle_italic)
        self._formatting_actions['italic'] = italic_action
        toolbar.addAction(italic_action)

        # Underline
        underline_action = QAction("Underline", self)
        underline_action.setShortcut(QKeySequence("Ctrl+U"))
        underline_action.setToolTip("Underline (Ctrl+U)")
        underline_action.setCheckable(True)
        underline_action.triggered.connect(self.toggle_underline)
        self._formatting_actions['underline'] = underline_action
        toolbar.addAction(underline_action)

        # Strikethrough
        strikethrough_action = QAction("Strikethrough", self)
        strikethrough_action.setShortcut(QKeySequence("Ctrl+T"))
        strikethrough_action.setToolTip("Strikethrough (Ctrl+T)")
        strikethrough_action.setCheckable(True)
        strikethrough_action.triggered.connect(self.toggle_strikethrough)
        self._formatting_actions['strikethrough'] = strikethrough_action
        toolbar.addAction(strikethrough_action)

        toolbar.addSeparator()

        # Heading 1 (Largest)
        h1_action = QAction("H1", self)
        h1_action.setShortcut(QKeySequence("Ctrl+1"))
        h1_action.setToolTip("Heading 1 (Ctrl+1)")
        h1_action.triggered.connect(lambda: self.apply_heading(1))
        toolbar.addAction(h1_action)

        # Heading 2
        h2_action = QAction("H2", self)
        h2_action.setShortcut(QKeySequence("Ctrl+2"))
        h2_action.setToolTip("Heading 2 (Ctrl+2)")
        h2_action.triggered.connect(lambda: self.apply_heading(2))
        toolbar.addAction(h2_action)

        # Heading 3
        h3_action = QAction("H3", self)
        h3_action.setShortcut(QKeySequence("Ctrl+3"))
        h3_action.setToolTip("Heading 3 (Ctrl+3)")
        h3_action.triggered.connect(lambda: self.apply_heading(3))
        toolbar.addAction(h3_action)

        # Normal Text
        normal_action = QAction("Normal", self)
        normal_action.setShortcut(QKeySequence("Ctrl+0"))
        normal_action.setToolTip("Normal Text (Ctrl+0)")
        normal_action.triggered.connect(lambda: self.apply_heading(0))
        toolbar.addAction(normal_action)

        toolbar.addSeparator()

        # Bullet List
        bullet_list_action = QAction("• List", self)
        bullet_list_action.setShortcut(QKeySequence("Ctrl+Shift+B"))
        bullet_list_action.setToolTip("Bullet List (Ctrl+Shift+B)")
        bullet_list_action.triggered.connect(self.toggle_bullet_list)
        toolbar.addAction(bullet_list_action)

        # Numbered List
        numbered_list_action = QAction("1. List", self)
        numbered_list_action.setShortcut(QKeySequence("Ctrl+Shift+N"))
        numbered_list_action.setToolTip("Numbered List (Ctrl+Shift+N)")
        numbered_list_action.triggered.connect(self.toggle_numbered_list)
        toolbar.addAction(numbered_list_action)

        toolbar.addSeparator()

        # Clear Formatting
        clear_format_action = QAction("Clear Format", self)
        clear_format_action.setShortcut(QKeySequence("Ctrl+Shift+C"))
        clear_format_action.setToolTip("Clear Formatting (Ctrl+Shift+C)")
        clear_format_action.triggered.connect(self.clear_formatting)
        toolbar.addAction(clear_format_action)

        return toolbar

    def toggle_bold(self):
        """Toggle bold formatting for selected text or current cursor position."""
        cursor = self.textCursor()

        if cursor.hasSelection():
            # Check if the majority of the selection is bold
            is_bold = self._is_selection_formatted(cursor, 'bold')

            # Create new format with only bold property set
            fmt = QTextCharFormat()
            fmt.setFontWeight(QFont.Weight.Normal if is_bold else QFont.Weight.Bold)
            cursor.mergeCharFormat(fmt)
            self.setTextCursor(cursor)
        else:
            # Apply to future typing
            fmt = self.currentCharFormat()
            is_bold = fmt.fontWeight() == QFont.Weight.Bold
            fmt.setFontWeight(QFont.Weight.Normal if is_bold else QFont.Weight.Bold)
            self.setCurrentCharFormat(fmt)

        self.formatting_changed.emit()
        self._update_formatting_actions()

    def toggle_italic(self):
        """Toggle italic formatting for selected text or current cursor position."""
        cursor = self.textCursor()

        if cursor.hasSelection():
            # Check if the majority of the selection is italic
            is_italic = self._is_selection_formatted(cursor, 'italic')

            # Create new format with only italic property set
            fmt = QTextCharFormat()
            fmt.setFontItalic(not is_italic)
            cursor.mergeCharFormat(fmt)
            self.setTextCursor(cursor)
        else:
            # Apply to future typing
            fmt = self.currentCharFormat()
            is_italic = fmt.fontItalic()
            fmt.setFontItalic(not is_italic)
            self.setCurrentCharFormat(fmt)

        self.formatting_changed.emit()
        self._update_formatting_actions()

    def toggle_underline(self):
        """Toggle underline formatting for selected text or current cursor position."""
        cursor = self.textCursor()

        if cursor.hasSelection():
            # Check if the majority of the selection is underlined
            is_underline = self._is_selection_formatted(cursor, 'underline')

            # Create new format with only underline property set
            fmt = QTextCharFormat()
            fmt.setFontUnderline(not is_underline)
            cursor.mergeCharFormat(fmt)
            self.setTextCursor(cursor)
        else:
            # Apply to future typing
            fmt = self.currentCharFormat()
            is_underline = fmt.fontUnderline()
            fmt.setFontUnderline(not is_underline)
            self.setCurrentCharFormat(fmt)

        self.formatting_changed.emit()
        self._update_formatting_actions()

    def toggle_strikethrough(self):
        """Toggle strikethrough formatting for selected text or current cursor position."""
        cursor = self.textCursor()

        if cursor.hasSelection():
            # Check if the majority of the selection has strikethrough
            is_strikethrough = self._is_selection_formatted(cursor, 'strikethrough')

            # Create new format with only strikethrough property set
            fmt = QTextCharFormat()
            fmt.setFontStrikeOut(not is_strikethrough)
            cursor.mergeCharFormat(fmt)
            self.setTextCursor(cursor)
        else:
            # Apply to future typing
            fmt = self.currentCharFormat()
            is_strikethrough = fmt.fontStrikeOut()
            fmt.setFontStrikeOut(not is_strikethrough)
            self.setCurrentCharFormat(fmt)

        self.formatting_changed.emit()
        self._update_formatting_actions()

    def apply_heading(self, level: int):
        """
        Apply heading level to current line or all selected lines.

        Args:
            level: Heading level (0=normal, 1=H1, 2=H2, 3=H3)

        Note:
            This applies visual formatting only. The # markers are added
            when converting to Markdown during save (see get_content()).
            If text is selected, applies to all selected lines.
        """
        cursor = self.textCursor()

        # Create format for the heading level
        fmt = QTextCharFormat()

        # Set font size and weight based on heading level
        if level == 1:
            fmt.setFontPointSize(20)  # H1 - largest
            fmt.setFontWeight(QFont.Weight.Bold)
        elif level == 2:
            fmt.setFontPointSize(16)  # H2
            fmt.setFontWeight(QFont.Weight.Bold)
        elif level == 3:
            fmt.setFontPointSize(13)  # H3
            fmt.setFontWeight(QFont.Weight.Bold)
        else:
            # Normal text - clear formatting and set to widget's default size, preserve color
            fmt.setFontWeight(QFont.Weight.Normal)
            fmt.setFontItalic(False)
            fmt.setFontUnderline(False)
            fmt.setFontStrikeOut(False)
            fmt.setFontPointSize(self.font().pointSize())  # Widget's default font size
            # Preserve existing foreground color
            fmt.setBackground(QColor(0, 0, 0, 0))  # Transparent background

        # Handle selection
        if cursor.hasSelection():
            # Apply to all selected lines
            start = cursor.selectionStart()
            end = cursor.selectionEnd()

            # Create temp cursor to iterate through blocks
            temp_cursor = QTextCursor(cursor)
            temp_cursor.setPosition(start)
            temp_cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)

            # Apply formatting to each block in selection
            while temp_cursor.position() <= end:
                # Select entire block
                temp_cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
                temp_cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)

                # Apply format
                temp_cursor.mergeCharFormat(fmt)

                # Move to next block
                temp_cursor.clearSelection()
                if not temp_cursor.movePosition(QTextCursor.MoveOperation.NextBlock):
                    break

            # Restore original selection
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
            self.setTextCursor(cursor)
        else:
            # No selection - apply to current line only
            cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)

            # Apply the formatting to the block
            cursor.mergeCharFormat(fmt)

            # Move cursor to end of line
            cursor.clearSelection()
            cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock)
            self.setTextCursor(cursor)

        self.formatting_changed.emit()

    def clear_formatting(self):
        """Clear all formatting from selected text or entire document."""
        cursor = self.textCursor()

        if cursor.hasSelection():
            # Clear formatting for selection - preserve original font size and color but clear styling
            fmt = cursor.charFormat()
            fmt.setFontWeight(QFont.Weight.Normal)  # Normal weight
            fmt.setFontItalic(False)
            fmt.setFontUnderline(False)
            fmt.setFontStrikeOut(False)
            # Preserve existing foreground color
            fmt.setBackground(QColor(0, 0, 0, 0))  # Transparent background
            cursor.mergeCharFormat(fmt)
            self.setTextCursor(cursor)
        else:
            # Clear formatting for entire document
            cursor.select(cursor.SelectionType.Document)
            fmt = cursor.charFormat()
            fmt.setFontWeight(QFont.Weight.Normal)  # Normal weight
            fmt.setFontItalic(False)
            fmt.setFontUnderline(False)
            fmt.setFontStrikeOut(False)
            # Preserve existing foreground color
            fmt.setBackground(QColor(0, 0, 0, 0))  # Transparent background
            cursor.mergeCharFormat(fmt)
            # Restore cursor position
            cursor.clearSelection()
            self.setTextCursor(cursor)

        self.formatting_changed.emit()

    def _is_selection_formatted(self, cursor, format_type: str) -> bool:
        """
        Check if the majority of a selection has a specific format applied.

        Args:
            cursor: QTextCursor with selection
            format_type: One of 'bold', 'italic', 'underline', 'strikethrough'

        Returns:
            True if more than half the selection has the format, False otherwise
        """
        if not cursor.hasSelection():
            return False

        # Save original cursor position
        start = cursor.selectionStart()
        end = cursor.selectionEnd()

        # Count characters with and without the format
        formatted_count = 0
        total_count = 0

        # Create a new cursor to iterate through the selection
        temp_cursor = QTextCursor(cursor)
        temp_cursor.setPosition(start)

        while temp_cursor.position() < end:
            # Get the format at this position
            temp_cursor.movePosition(QTextCursor.MoveOperation.NextCharacter, QTextCursor.MoveMode.KeepAnchor)
            fmt = temp_cursor.charFormat()

            # Check the specific format type
            if format_type == 'bold':
                if fmt.fontWeight() == QFont.Weight.Bold:
                    formatted_count += 1
            elif format_type == 'italic':
                if fmt.fontItalic():
                    formatted_count += 1
            elif format_type == 'underline':
                if fmt.fontUnderline():
                    formatted_count += 1
            elif format_type == 'strikethrough':
                if fmt.fontStrikeOut():
                    formatted_count += 1

            total_count += 1
            temp_cursor.setPosition(temp_cursor.position())  # Move to next position

        # Return True if more than half is formatted
        return formatted_count > (total_count / 2) if total_count > 0 else False

    def _update_formatting_actions(self):
        """Update the state of formatting action buttons based on current selection/cursor."""
        if not self._formatting_actions:
            return

        cursor = self.textCursor()

        # Determine formatting state
        if cursor.hasSelection():
            # Has selection - check if majority is formatted
            is_bold = self._is_selection_formatted(cursor, 'bold')
            is_italic = self._is_selection_formatted(cursor, 'italic')
            is_underline = self._is_selection_formatted(cursor, 'underline')
            is_strikethrough = self._is_selection_formatted(cursor, 'strikethrough')
        else:
            # No selection - use current char format
            fmt = self.currentCharFormat()
            is_bold = fmt.fontWeight() == QFont.Weight.Bold
            is_italic = fmt.fontItalic()
            is_underline = fmt.fontUnderline()
            is_strikethrough = fmt.fontStrikeOut()

        # Update button states
        if 'bold' in self._formatting_actions:
            self._formatting_actions['bold'].setChecked(is_bold)

        if 'italic' in self._formatting_actions:
            self._formatting_actions['italic'].setChecked(is_italic)

        if 'underline' in self._formatting_actions:
            self._formatting_actions['underline'].setChecked(is_underline)

        if 'strikethrough' in self._formatting_actions:
            self._formatting_actions['strikethrough'].setChecked(is_strikethrough)

    def paste_without_formatting(self):
        """Paste clipboard content as plain text, removing all formatting."""
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtGui import QTextCharFormat

        clipboard = QApplication.clipboard()
        text = clipboard.text()

        if text:
            # Get cursor and save current position
            cursor = self.textCursor()

            # Create a plain text format (no formatting)
            plain_format = QTextCharFormat()

            # Apply plain format and insert text
            cursor.setCharFormat(plain_format)
            cursor.insertText(text)

            # Update the cursor position
            self.setTextCursor(cursor)

    def _name_entries(self):
        """The entries whose names can be completed (the campaign's, refreshed every few seconds)."""
        import time
        stamp, entries = self._name_cache
        if time.monotonic() - stamp < 5.0 and entries:
            return [e for e in entries if e.doc_id != self.exclude_doc_id]
        if not self.db_manager or self.module_id is None:
            return []
        from config.entity_types import get_registry
        try:
            allowed = set(get_registry().keys_for('context')) - {'module'}
            first = set(self.name_priorities()) if callable(self.name_priorities) else set()
            entries = [NameEntry(d['title'], d['entity_type'], d['id'], 0 if d['id'] in first else 1)
                       for d in self.db_manager.get_document_summaries(self.module_id)
                       if d['entity_type'] in allowed and d['title']]
        except Exception as e:
            self.logger.warning(f"Could not read the names for completion: {e}")
            entries = []
        self._name_cache = (time.monotonic(), entries)
        return [e for e in entries if e.doc_id != self.exclude_doc_id]

    def forget_names(self):
        """The set of entries changed: read the names again at the next key."""
        self._name_cache = (0.0, [])

    def keyPressEvent(self, event):
        if self.completer.handle_key(event):
            return
        super().keyPressEvent(event)
        self.completer.after_key(event)

    def focusOutEvent(self, event):
        self.completer.clear()
        super().focusOutEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        self.completer.paint_ghost()

    def mousePressEvent(self, event):
        """Override mouse press to handle link clicks with Ctrl+Click."""
        from PyQt6.QtCore import Qt

        # Get the cursor at the click position
        cursor = self.cursorForPosition(event.pos())

        # Check if we clicked on a link with Ctrl held down
        char_format = cursor.charFormat()
        if char_format.isAnchor():
            anchor_href = char_format.anchorHref()
            if anchor_href and (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
                # Ctrl+Click on link - handle it
                url = QUrl(anchor_href)
                self.logger.info(f"Handling link click: {url.toString()}")
                self._handle_link_click(url)
                # Don't call the parent handler - we've handled this click
                return

        # Not a Ctrl+link click - call parent implementation
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Override mouse move to show pointer cursor on links when Ctrl is held."""
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QCursor

        # Check if Ctrl is held and we're hovering over a link
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            cursor = self.cursorForPosition(event.pos())
            char_format = cursor.charFormat()
            if char_format.isAnchor() and char_format.anchorHref():
                # Over a link with Ctrl held - show pointing hand cursor
                self.viewport().setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            else:
                # Not over a link - show normal I-beam cursor
                self.viewport().setCursor(QCursor(Qt.CursorShape.IBeamCursor))
        else:
            # Ctrl not held - show normal I-beam cursor
            self.viewport().setCursor(QCursor(Qt.CursorShape.IBeamCursor))

        # Call parent implementation
        super().mouseMoveEvent(event)

    def contextMenuEvent(self, event):
        """Override context menu event to add custom link options."""
        menu = self.createStandardContextMenu()

        menu.addSeparator()

        # Check if cursor is on a link at the click position
        cursor = self.cursorForPosition(event.pos())

        # Try to get the format at the current position and nearby positions
        # Sometimes the cursor lands between characters
        char_format = cursor.charFormat()
        is_on_link = char_format.isAnchor() and char_format.anchorHref()

        # If not on a link, try moving one character back
        if not is_on_link and cursor.position() > 0:
            test_cursor = QTextCursor(cursor)
            test_cursor.movePosition(QTextCursor.MoveOperation.PreviousCharacter)
            test_format = test_cursor.charFormat()
            if test_format.isAnchor() and test_format.anchorHref():
                is_on_link = True
                char_format = test_format
                cursor = test_cursor

        # Add "Remove Link" action if cursor is on a link
        if is_on_link:
            remove_link_action = menu.addAction("Remove Link")
            # Store the cursor position for _remove_link to use
            remove_link_action.triggered.connect(lambda: self._remove_link(cursor))
            menu.addSeparator()

        # Add "Insert Link" action (only if db_manager is available)
        if self.db_manager and self.module_id is not None:
            insert_link_action = menu.addAction("Insert Link...")
            insert_link_action.triggered.connect(self._show_insert_link_dialog)

        # Add "Create entry from selection" (the owner window provides how an entry is made)
        if self.create_entry_callback is not None and self.textCursor().hasSelection():
            from config.entity_types import get_registry
            registry = get_registry()
            create_menu = menu.addMenu("Create entry from selection")
            for kind in registry.keys_for('create'):
                if kind not in ('session', 'character'):
                    create_menu.addAction(registry.label(kind), lambda k=kind: self._create_entry_from_selection(k))

        # Add "Send Selection to Discord" (needs a selection and a module context)
        if self.db_manager and self.module_id is not None and self.textCursor().hasSelection():
            discord_action = menu.addAction("Send Selection to Discord...")
            discord_action.triggered.connect(self._send_selection_to_discord)

        # Add "Paste Without Formatting" action
        paste_plain_action = menu.addAction("Paste Without Formatting")
        paste_plain_action.setShortcut(QKeySequence("Ctrl+Shift+V"))
        paste_plain_action.triggered.connect(self.paste_without_formatting)

        menu.exec(event.globalPos())

    def _create_entry_from_selection(self, kind: str):
        """A new entry named like the selected text; the selection becomes a link to it."""
        name = self.textCursor().selectedText().replace(' ', ' ').strip()
        if not name or self.create_entry_callback is None:
            return
        doc_id = self.create_entry_callback(kind, name)
        if doc_id:
            self._insert_markdown_link(name, f"rpg://{kind}/{doc_id}")
            self.forget_names()

    def _send_selection_to_discord(self):
        """Preview and send the selected text to Discord."""
        from gui.discord_actions import send_text_to_discord
        selected = self.textCursor().selection().toPlainText()
        send_text_to_discord(self, self.db_manager, self.module_id, selected)

    def loadResource(self, resource_type, name):
        """Never fetch remote resources (e.g. <img src="http://...">) from document content.

        Network shares (UNC paths, file://server/share) are blocked as well: on Windows opening one
        sends the user's credentials to that server, and imported documents are untrusted.
        """
        try:
            url = name if isinstance(name, QUrl) else QUrl(str(name))
            text = url.toString(QUrl.ComponentFormattingOption.FullyDecoded)
            scheme = url.scheme().lower()
            remote = (scheme in ('http', 'https', 'ftp')
                      or text.startswith(('\\', '//'))
                      or (scheme == 'file' and (bool(url.host()) or url.path().startswith('//'))))
            if remote:
                self.logger.warning(f"Blocked remote resource in document: {url.host() or text[:60]}")
                return None
        except Exception:
            return None
        return super().loadResource(resource_type, name)

    def _handle_link_click(self, url: QUrl):
        """
        Handle clicks on links in the document.

        Args:
            url: The clicked URL (can be http/https or rpg://)
        """
        if url.scheme() in ['http', 'https']:
            # External link - show confirmation dialog for security
            reply = QMessageBox.question(
                self,
                "Open External Link",
                f"Open this URL in your browser?\n\n{url.toString()}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No  # Default to No for safety
            )

            if reply == QMessageBox.StandardButton.Yes:
                QDesktopServices.openUrl(url)
                self.logger.info(f"Opened external link: {url.toString()}")

        elif url.scheme() == 'rpg':
            # Internal link - emit signal for parent to handle navigation
            self.internal_link_clicked.emit(url)

        elif url.scheme() == 'file':
            # Audio of an imported module: only an existing local audio file, after a confirmation
            audio = local_audio_path(url)
            if audio is None:
                self.logger.warning(f"Blocked file link: {url.toString()[:120]}")
                return
            reply = QMessageBox.question(
                self, "Open Audio File",
                f"Play this file with your default audio player?\n\n{audio}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(audio)))

        else:
            # Unknown scheme - log warning
            self.logger.warning(f"Unsupported URL scheme clicked: {url.toString()}")

    def _show_insert_link_dialog(self):
        """Show dialog to insert a link (entity or external URL)."""
        from gui.dialogs.link_insertion_dialog import LinkInsertionDialog
        from PyQt6.QtWidgets import QDialog

        if not self.db_manager or self.module_id is None:
            self.logger.warning("Cannot show link dialog: db_manager or module_id not set")
            QMessageBox.warning(
                self,
                "Feature Unavailable",
                "Link insertion is not available in this context."
            )
            return

        try:
            # Capture selected text to pre-populate dialog
            cursor = self.textCursor()
            selected_text = cursor.selectedText() if cursor.hasSelection() else ""

            # Pass selected text to dialog for smart pre-population
            dialog = LinkInsertionDialog(self.db_manager, self.module_id, self, selected_text)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                link_text, link_url = dialog.get_link()
                self._insert_markdown_link(link_text, link_url)
        except Exception as e:
            self.logger.error(f"Error showing link insertion dialog: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Dialog Error",
                f"Failed to open link insertion dialog:\n{str(e)}"
            )

    def _insert_markdown_link(self, text: str, url: str):
        """
        Insert a markdown link at the cursor position.

        Args:
            text: Display text for the link
            url: URL for the link (can be rpg://, http://, or https://)
        """
        from PyQt6.QtGui import QTextCharFormat

        cursor = self.textCursor()

        # Determine the link text to use
        if cursor.hasSelection():
            link_text = cursor.selectedText()
        else:
            link_text = text

        # Create a character format with anchor properties
        char_format = QTextCharFormat()
        char_format.setAnchor(True)
        char_format.setAnchorHref(url)
        char_format.setForeground(self.palette().link())  # Use link color
        char_format.setFontUnderline(True)  # Underline links

        # Insert the link text with the anchor format
        cursor.insertText(link_text, char_format)

        self.logger.info(f"Inserted link: [{link_text}]({url})")

    def _remove_link(self, cursor=None):
        """Remove link formatting from the text at cursor position, keeping the text.

        Args:
            cursor: Optional cursor at the link position. If None, uses current cursor.
        """

        # Use provided cursor or get current cursor
        if cursor is None:
            cursor = self.textCursor()
        else:
            # Create a new cursor to avoid modifying the original
            cursor = QTextCursor(cursor)

        char_format = cursor.charFormat()

        # Check if we're on a link
        if not char_format.isAnchor():
            return

        # Find the boundaries of the link
        # Move to the start of the link
        start_pos = cursor.position()
        while cursor.position() > 0:
            cursor.movePosition(QTextCursor.MoveOperation.PreviousCharacter, QTextCursor.MoveMode.MoveAnchor)
            if not cursor.charFormat().isAnchor():
                # Moved past the link, go back one character
                cursor.movePosition(QTextCursor.MoveOperation.NextCharacter, QTextCursor.MoveMode.MoveAnchor)
                break

        link_start = cursor.position()

        # Move to the end of the link
        cursor.setPosition(start_pos)
        while cursor.position() < len(self.toPlainText()):
            cursor.movePosition(QTextCursor.MoveOperation.NextCharacter, QTextCursor.MoveMode.MoveAnchor)
            if not cursor.charFormat().isAnchor():
                # Moved past the link, go back one character
                cursor.movePosition(QTextCursor.MoveOperation.PreviousCharacter, QTextCursor.MoveMode.MoveAnchor)
                break

        link_end = cursor.position()

        # Select the entire link
        cursor.setPosition(link_start)
        cursor.setPosition(link_end + 1, QTextCursor.MoveMode.KeepAnchor)

        # Get the link text
        link_text = cursor.selectedText()
        link_url = cursor.charFormat().anchorHref()

        # Create a plain text format (no link)
        # Start with the current format to preserve bold, italic, etc.
        plain_format = cursor.charFormat()

        # Remove link-specific formatting
        plain_format.setAnchor(False)
        plain_format.setAnchorHref("")
        plain_format.setFontUnderline(False)  # Remove underline

        # Reset foreground color to default (clear any custom color)
        plain_format.clearForeground()

        # Replace the link with plain text
        cursor.insertText(link_text, plain_format)

        self.logger.info(f"Removed link from text: '{link_text}' (was: {link_url})")

    def get_content(self) -> str:
        """
        Get content in Markdown format.

        Always returns Markdown to preserve formatting in a clean, readable format.
        This is the new standard for content storage (post-migration to v5).
        """
        # QTextEdit.toMarkdown() doesn't accept features parameter
        markdown = self.toMarkdown()
        return markdown.strip()

    def set_content(self, content: str):
        """
        Set content from Markdown, HTML (legacy), or plain text.

        Args:
            content: Text content (Markdown, HTML, or plain text)

        Notes:
            - Markdown format is preferred (new standard)
            - HTML is supported for backward compatibility (pre-v5 databases)
            - Plain text is used when no formatting is present
        """
        if not content:
            self.clear()
            return

        # Detect content type
        content_stripped = content.strip()

        # Check if content is HTML (legacy format - pre-v5 migration)
        # Look for HTML tags (be more specific to avoid false positives)
        html_tags = ['<p>', '<b>', '<i>', '<u>', '<span', '<div', '<br', '<strong>', '<em>']
        is_html = any(tag in content_stripped for tag in html_tags)

        if is_html:
            # HTML detected - set as HTML (backward compatibility)
            self.setHtml(content)
            return

        # Check if content is Markdown (has formatting symbols)
        markdown_indicators = ['**', '*', '- ', '1. ', '# ', '`', '[', '](']
        is_markdown = any(indicator in content for indicator in markdown_indicators)

        if is_markdown:
            # Markdown detected - use setMarkdown
            # Clear existing content first to ensure clean slate
            self.clear()
            # QTextEdit.setMarkdown() doesn't accept features parameter
            self.setMarkdown(content)
        else:
            # Plain text - set directly
            self.setPlainText(content)

    def toggle_bullet_list(self):
        """Toggle bullet list for current line or selection."""
        cursor = self.textCursor()

        # Always work with entire blocks (lines)
        if cursor.hasSelection():
            # Expand selection to include complete lines
            start = cursor.selectionStart()
            end = cursor.selectionEnd()

            # Move to start of first selected block
            cursor.setPosition(start)
            cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)

            # Move to end of last selected block while keeping selection
            cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
            cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)

            # Now work with the expanded selection
            self._toggle_list_for_selection(cursor, QTextListFormat.Style.ListDisc)
        else:
            # No selection - work with current line
            cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
            self._toggle_list_for_selection(cursor, QTextListFormat.Style.ListDisc)

        self.formatting_changed.emit()

    def toggle_numbered_list(self):
        """Toggle numbered list for current line or selection."""
        cursor = self.textCursor()

        # Always work with entire blocks (lines)
        if cursor.hasSelection():
            # Expand selection to include complete lines
            start = cursor.selectionStart()
            end = cursor.selectionEnd()

            # Move to start of first selected block
            cursor.setPosition(start)
            cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)

            # Move to end of last selected block while keeping selection
            cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
            cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)

            # Now work with the expanded selection
            self._toggle_list_for_selection(cursor, QTextListFormat.Style.ListDecimal)
        else:
            # No selection - work with current line
            cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
            self._toggle_list_for_selection(cursor, QTextListFormat.Style.ListDecimal)

        self.formatting_changed.emit()

    def _toggle_list_for_selection(self, cursor, target_list_style):
        """Toggle list formatting for the current selection or block."""

        # Save selection boundaries
        start = cursor.selectionStart()
        end = cursor.selectionEnd()

        # First, check if any blocks in the selection are already in a list
        blocks_with_lists = 0
        total_blocks = 0

        # Count blocks and check for existing list formatting
        temp_cursor = QTextCursor(cursor)
        temp_cursor.setPosition(start)
        temp_cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)

        while temp_cursor.position() <= end:
            # Check if block is in a list by checking currentList()
            if temp_cursor.currentList() is not None:
                blocks_with_lists += 1
            total_blocks += 1

            # Move to next block, but don't go past the selection end
            if not temp_cursor.movePosition(QTextCursor.MoveOperation.NextBlock):
                break

            # Stop if we've gone past the selection
            if temp_cursor.position() > end:
                break

        # If any blocks have list formatting, remove all list formatting
        if blocks_with_lists > 0:
            self._remove_all_list_formatting(cursor)
        else:
            # No lists found, create the requested list type for each block
            # We need to add each block to the same list
            list_fmt = QTextListFormat()
            list_fmt.setStyle(target_list_style)
            list_fmt.setIndent(1)

            # Create the list with the first block
            temp_cursor = QTextCursor(cursor)
            temp_cursor.setPosition(start)
            temp_cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            text_list = temp_cursor.createList(list_fmt)

            # Add remaining blocks to the same list
            while temp_cursor.movePosition(QTextCursor.MoveOperation.NextBlock):
                if temp_cursor.position() > end:
                    break
                # Add this block to the existing list
                text_list.add(temp_cursor.block())

    def _remove_all_list_formatting(self, cursor):
        """Remove all list formatting from the current selection."""
        # Save selection boundaries
        start = cursor.selectionStart()
        end = cursor.selectionEnd()

        # Work with each block in the selection
        temp_cursor = QTextCursor(cursor)
        temp_cursor.setPosition(start)
        temp_cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)

        while temp_cursor.position() <= end:
            # Remove block from list if it's in one
            current_list = temp_cursor.currentList()
            if current_list is not None:
                # Get the index of the block in the list and remove it
                block_index = current_list.itemNumber(temp_cursor.block())
                if block_index >= 0:
                    current_list.removeItem(block_index)

            # Get the current block format and reset indent/margin
            block_fmt = temp_cursor.blockFormat()
            block_fmt.setIndent(0)
            block_fmt.setLeftMargin(0)

            # Apply the format
            temp_cursor.setBlockFormat(block_fmt)

            # Move to next block
            if not temp_cursor.movePosition(QTextCursor.MoveOperation.NextBlock):
                break

            # Stop if we've gone past the selection
            if temp_cursor.position() > end:
                break


