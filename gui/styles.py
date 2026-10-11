"""Compatibility alias: the style manager lives in ``gui.theme.style_manager``."""

from gui.theme.style_manager import (  # noqa: F401
    DARK_PALETTE, LIGHT_PALETTE, StyleManager, get_style_manager, update_theme, update_typography,
)

__all__ = ['DARK_PALETTE', 'LIGHT_PALETTE', 'StyleManager', 'get_style_manager', 'update_theme', 'update_typography']
