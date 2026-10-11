"""
Reusable button bar component for standardized dialog button placement.

This component ensures consistent button positioning across all dialogs:
- Bottom-right alignment by default
- Standard button order: [Negative] [Positive]
- Automatic styling from StyleManager
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton
from typing import Optional, Literal, Callable
from gui.theme.style_manager import get_style_manager


class DialogButtonBar(QWidget):
    """Reusable button bar for standard dialog footers.

    Provides consistent button placement with automatic styling and alignment.

    Example usage:
        button_bar = DialogButtonBar(alignment='right')
        cancel_btn = button_bar.add_button("Cancel", role='negative')
        ok_btn = button_bar.add_button("OK", role='positive')

        # Or use presets:
        button_bar = DialogButtonBar()
        button_bar.set_standard_buttons(['cancel', 'ok'])
    """

    # Button spacing constant
    BUTTON_SPACING = 8

    def __init__(self, alignment: Literal['left', 'right', 'center'] = 'right',
                 parent: Optional[QWidget] = None):
        """Initialize button bar.

        Args:
            alignment: Button alignment ('left', 'right', or 'center')
            parent: Parent widget
        """
        super().__init__(parent)

        self.alignment = alignment
        self.style_manager = get_style_manager()
        self._buttons = {}  # Store buttons by name for easy access

        # Create layout
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(self.BUTTON_SPACING)

        # Apply alignment
        if alignment == 'right':
            self.layout.addStretch()
        elif alignment == 'center':
            self.layout.addStretch()

    def add_button(self, text: str,
                   role: Literal['positive', 'negative', 'neutral'] = 'neutral',
                   callback: Optional[Callable] = None,
                   name: Optional[str] = None) -> QPushButton:
        """Add a button to the bar.

        Args:
            text: Button text
            role: Button role for styling:
                - 'positive': Primary actions (OK, Save, Accept, Create)
                - 'negative': Destructive actions (Delete, Discard)
                - 'neutral': Secondary actions (Cancel, Close, Apply)
            callback: Optional click handler
            name: Optional name for retrieving button later

        Returns:
            Created QPushButton
        """
        button = QPushButton(text)

        # All buttons use standard unstyled design (no colored styling)
        # Role parameter kept for semantic clarity but doesn't affect styling

        # Connect callback if provided
        if callback:
            button.clicked.connect(callback)

        # Store button for later access
        if name:
            self._buttons[name] = button

        # Add to layout (before the trailing stretch if center-aligned)
        if self.alignment == 'center':
            # Insert before the last stretch
            self.layout.insertWidget(self.layout.count() - 1, button)
        else:
            self.layout.addWidget(button)

        return button

    def set_standard_buttons(self, buttons: list[str]) -> dict[str, QPushButton]:
        """Create a standard set of buttons.

        Args:
            buttons: List of button types. Supported values:
                - 'ok': OK button (positive role)
                - 'cancel': Cancel button (neutral role)
                - 'apply': Apply button (neutral role)
                - 'close': Close button (neutral role)
                - 'save': Save button (positive role)
                - 'create': Create button (positive role)
                - 'delete': Delete button (negative role)
                - 'accept': Accept button (positive role)
                - 'discard': Discard button (negative role)

        Returns:
            Dictionary mapping button type to QPushButton instance

        Example:
            buttons = button_bar.set_standard_buttons(['cancel', 'ok'])
            buttons['ok'].clicked.connect(self.accept)
            buttons['cancel'].clicked.connect(self.reject)
        """
        button_configs = {
            'ok': ('OK', 'positive'),
            'cancel': ('Cancel', 'neutral'),
            'apply': ('Apply', 'neutral'),
            'close': ('Close', 'neutral'),
            'save': ('Save', 'positive'),
            'create': ('Create', 'positive'),
            'delete': ('Delete', 'negative'),
            'accept': ('Accept', 'positive'),
            'discard': ('Discard', 'negative'),
        }

        created_buttons = {}
        for button_type in buttons:
            if button_type not in button_configs:
                raise ValueError(f"Unknown button type: {button_type}")

            text, role = button_configs[button_type]
            button = self.add_button(text, role=role, name=button_type)
            created_buttons[button_type] = button

        return created_buttons
