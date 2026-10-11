"""
Centralized style management for RPG Database Manager.

Provides theme-aware colors, typography, spacing, and component styles
that automatically adapt to light/dark themes.
"""

from typing import Dict, Literal, Optional


from gui.theme.tokens import DARK_PALETTE, LIGHT_PALETTE  # noqa: F401  (re-exported for callers)


# Typography System - Default (Normal scale)
DEFAULT_TYPOGRAPHY = {
    'h1': {'size': 18, 'weight': 'bold', 'line_height': 1.4},
    'h2': {'size': 14, 'weight': 'bold', 'line_height': 1.4},
    'h3': {'size': 12, 'weight': 'bold', 'line_height': 1.4},
    'body': {'size': 11, 'weight': 'normal', 'line_height': 1.5},
    'body-large': {'size': 12, 'weight': 'normal', 'line_height': 1.5},
    'caption': {'size': 9, 'weight': 'normal', 'line_height': 1.4},
    'button': {'size': 11, 'weight': '500', 'line_height': 1.2},
}

# Typography scale presets
TYPOGRAPHY_SCALES = {
    'small': {
        'h1': 16, 'h2': 13, 'h3': 11,
        'body': 10, 'body-large': 11, 'caption': 8, 'button': 10
    },
    'normal': {
        'h1': 18, 'h2': 14, 'h3': 12,
        'body': 11, 'body-large': 12, 'caption': 9, 'button': 11
    },
    'large': {
        'h1': 20, 'h2': 16, 'h3': 14,
        'body': 12, 'body-large': 13, 'caption': 10, 'button': 12
    },
    'extra-large': {
        'h1': 24, 'h2': 18, 'h3': 16,
        'body': 13, 'body-large': 14, 'caption': 11, 'button': 13
    }
}

# Backward compatibility
TYPOGRAPHY = DEFAULT_TYPOGRAPHY


# Spacing System (8px base unit)
SPACING = {
    'xs': 4,
    'sm': 8,
    'md': 16,
    'lg': 24,
    'xl': 32,
    'xxl': 48,
}


# Border Radius
RADIUS = {
    'none': 0,
    'sm': 2,
    'md': 4,
    'lg': 8,
    'xl': 12,
    'round': 9999,
}


# Shadows
SHADOWS = {
    'none': 'none',
    'sm': '0 1px 2px rgba(0, 0, 0, 0.15)',
    'md': '0 2px 4px rgba(0, 0, 0, 0.2)',
    'lg': '0 4px 8px rgba(0, 0, 0, 0.25)',
}


# Layout Constants for Dialog Button Standardization
LAYOUT = {
    # Dialog margins and spacing
    'dialog-margin': 10,
    'dialog-content-spacing': 10,
    'dialog-button-bar-top-margin': 15,

    # Button-specific
    'button-spacing': 8,  # Space between buttons
    'button-min-width': 80,
    'button-height': 32,

    # Standard positions (documentation)
    'button-position-bottom-right': 'bottom-right',  # Default for dialog actions
    'button-position-bottom-left': 'bottom-left',    # For simple forms
    'button-position-top': 'top',                    # For toolbars (CRUD operations)

    # Standard button orders (documentation)
    'button-order-ok-cancel': ['ok', 'cancel'],
    'button-order-apply-ok-cancel': ['apply', 'ok', 'cancel'],
    'button-order-save-delete': ['save', 'delete'],
    'button-order-create-cancel': ['create', 'cancel'],
}


class StyleManager:
    """
    Central style management for the application.
    Provides theme-aware colors and consistent styling.
    """

    def __init__(self, theme: Literal['dark', 'light', 'auto'] = 'auto', ui_settings=None):
        self._theme = theme
        self._ui_settings = ui_settings
        self._current_palette = self._get_palette()
        self._typography = self._build_typography()

    def _get_palette(self) -> Dict[str, str]:
        """Get the appropriate color palette based on theme."""
        if self._theme == 'light':
            return LIGHT_PALETTE
        elif self._theme == 'dark':
            return DARK_PALETTE
        else:  # auto: follow the OS colour scheme
            from gui.theme.manager import resolve_scheme
            return LIGHT_PALETTE if resolve_scheme('auto') == 'light' else DARK_PALETTE

    def _build_typography(self) -> Dict[str, Dict]:
        """Build typography dictionary based on settings."""
        if self._ui_settings is None:
            return DEFAULT_TYPOGRAPHY.copy()

        scale = self._ui_settings.typography_scale

        # If custom scale, use custom sizes
        if scale == 'custom':
            sizes = {
                'h1': self._ui_settings.custom_h1_size,
                'h2': self._ui_settings.custom_h2_size,
                'h3': self._ui_settings.custom_h3_size,
                'body': self._ui_settings.custom_body_size,
                'body-large': self._ui_settings.custom_body_size + 1,
                'caption': self._ui_settings.custom_caption_size,
                'button': self._ui_settings.custom_body_size,
            }
        # Otherwise use preset scale
        elif scale in TYPOGRAPHY_SCALES:
            sizes = TYPOGRAPHY_SCALES[scale]
        else:
            sizes = TYPOGRAPHY_SCALES['normal']

        # Build full typography dict with sizes and metadata
        return {
            'h1': {'size': sizes['h1'], 'weight': 'bold', 'line_height': 1.4},
            'h2': {'size': sizes['h2'], 'weight': 'bold', 'line_height': 1.4},
            'h3': {'size': sizes['h3'], 'weight': 'bold', 'line_height': 1.4},
            'body': {'size': sizes['body'], 'weight': 'normal', 'line_height': 1.5},
            'body-large': {'size': sizes['body-large'], 'weight': 'normal', 'line_height': 1.5},
            'caption': {'size': sizes['caption'], 'weight': 'normal', 'line_height': 1.4},
            'button': {'size': sizes['button'], 'weight': '500', 'line_height': 1.2},
        }

    def set_theme(self, theme: Literal['dark', 'light', 'auto']):
        """Update the current theme."""
        self._theme = theme
        self._current_palette = self._get_palette()

    def update_typography(self, ui_settings):
        """Update typography based on new settings."""
        self._ui_settings = ui_settings
        self._typography = self._build_typography()

    def color(self, name: str) -> str:
        """Get a color by name from the current palette."""
        return self._current_palette.get(name, '#000000')

    def spacing(self, size: str) -> int:
        """Get spacing value by size name."""
        return SPACING.get(size, SPACING['md'])

    def radius(self, size: str) -> int:
        """Get border radius by size name."""
        return RADIUS.get(size, RADIUS['md'])

    def typography(self, style: str) -> Dict:
        """Get typography settings by style name."""
        return self._typography.get(style, self._typography['body'])

    def layout(self, key: str):
        """Get layout constant by key name."""
        return LAYOUT.get(key)

    # Button Styles

    # Label Styles

    # Status/Badge Styles

    # List/Item Styles

    # Input Styles

    # Utility Methods


# Global instance - can be updated when theme/typography changes
_style_manager: Optional[StyleManager] = None


def get_style_manager(theme: Optional[str] = None, ui_settings=None) -> StyleManager:
    """
    Get the global StyleManager instance.

    Args:
        theme: Optional theme to set ('dark', 'light', 'auto')
        ui_settings: Optional UISettings instance for typography configuration

    Returns:
        StyleManager instance
    """
    global _style_manager

    if _style_manager is None:
        _style_manager = StyleManager(theme or 'auto', ui_settings)
    else:
        if theme is not None:
            _style_manager.set_theme(theme)
        if ui_settings is not None:
            _style_manager.update_typography(ui_settings)

    return _style_manager


def update_theme(theme: Literal['dark', 'light', 'auto']):
    """Update the global theme."""
    if _style_manager is not None:
        _style_manager.set_theme(theme)


def update_typography(ui_settings):
    """Update the global typography settings."""
    if _style_manager is not None:
        _style_manager.update_typography(ui_settings)
