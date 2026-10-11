"""
Base dialog class with standardized button placement.

Provides a standard layout structure for all dialogs:
- Main content area (expandable)
- Button bar at bottom-right (consistent positioning)
- Pre-configured margins and spacing
"""

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QWidget
from typing import Optional
from gui.components.dialog_button_bar import DialogButtonBar


class StandardDialog(QDialog):
    """Base dialog with standardized button placement.

    This base class provides:
    - Pre-configured vertical layout
    - Content area for dialog-specific widgets
    - Standard button bar at bottom-right
    - Consistent margins and spacing

    Example usage:
        class MyDialog(StandardDialog):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.setWindowTitle("My Dialog")

                # Add content to content_layout
                label = QLabel("Dialog content")
                self.content_layout.addWidget(label)

                # Add buttons
                buttons = self.button_bar.set_standard_buttons(['cancel', 'ok'])
                buttons['ok'].clicked.connect(self.accept)
                buttons['cancel'].clicked.connect(self.reject)
    """

    # Layout constants
    DIALOG_MARGIN = 10
    CONTENT_SPACING = 10
    BUTTON_BAR_TOP_MARGIN = 15  # Extra space above button bar

    def __init__(self, parent: Optional[QWidget] = None,
                 button_alignment: str = 'right'):
        """Initialize standard dialog.

        Args:
            parent: Parent widget
            button_alignment: Button alignment ('left', 'right', or 'center')
        """
        super().__init__(parent)

        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(
            self.DIALOG_MARGIN,
            self.DIALOG_MARGIN,
            self.DIALOG_MARGIN,
            self.DIALOG_MARGIN
        )
        self.main_layout.setSpacing(self.CONTENT_SPACING)

        # Content layout (for dialog-specific content)
        self.content_layout = QVBoxLayout()
        self.content_layout.setSpacing(self.CONTENT_SPACING)
        self.main_layout.addLayout(self.content_layout, stretch=1)

        # Add spacing before button bar
        self.main_layout.addSpacing(self.BUTTON_BAR_TOP_MARGIN)

        # Button bar (at bottom)
        self.button_bar = DialogButtonBar(alignment=button_alignment)
        self.main_layout.addWidget(self.button_bar)
