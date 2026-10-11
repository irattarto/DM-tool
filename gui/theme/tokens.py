"""
Design tokens for the application theme.

One flat token dictionary per colour scheme. Everything visual (QPalette, the
application stylesheet, rich-text colours) is derived from these.
"""

import re
from typing import Dict

from PyQt6.QtGui import QColor, QPalette

# Color Palettes
DARK_PALETTE = {
    # Base colors
    'background': '#1e1e1e',
    'surface': '#2d2d2d',
    'surface-elevated': '#3e3e3e',
    'border': '#404040',
    'divider': '#2a2a2a',

    # Text colors
    'text-primary': '#e4e4e4',
    'text-secondary': '#b0b0b0',
    'text-disabled': '#6e6e6e',
    'text-hint': '#8a8a8a',

    # Accent colors
    'primary': '#4a9eff',
    'primary-hover': '#6db1ff',
    'primary-pressed': '#2884e8',
    'primary-light': '#7db8ff',

    'secondary': '#6c757d',
    'secondary-hover': '#828a91',
    'secondary-pressed': '#5a6268',

    'success': '#28a745',
    'success-hover': '#48c765',
    'success-pressed': '#20873a',
    'success-bg': '#1e3a25',

    'warning': '#ffc107',
    'warning-hover': '#ffd454',
    'warning-pressed': '#e0a800',
    'warning-bg': '#3d3420',

    'danger': '#dc3545',
    'danger-hover': '#e25563',
    'danger-pressed': '#bd2130',
    'danger-bg': '#3a1f23',

    'info': '#17a2b8',
    'info-hover': '#3fb5c7',
    'info-pressed': '#138496',
    'info-bg': '#1d3033',

    # RPG-specific
    'magic': '#9c27b0',
    'gold': '#ffd700',

    # State colors
    'hover-overlay': 'rgba(255, 255, 255, 0.05)',
    'selected': '#4a9eff33',
    'focus': '#4a9eff80',

    # Semantic extras (used by property-based QSS variants)
    'muted': '#9a9a9a',
    'on-primary': '#ffffff',
    'alt-base': '#262626',
    'link': '#7db8ff',
    'code-bg': '#2a2a2a',
    'dropzone-bg': '#262626',
    'dropzone-border': '#555555',
    'dropzone-hover-bg': '#1d2a3a',
    'dropzone-hover-border': '#4a9eff',
}

LIGHT_PALETTE = {
    # Base colors
    'background': '#ffffff',
    'surface': '#f5f5f5',
    'surface-elevated': '#e8e8e8',
    'border': '#d0d0d0',
    'divider': '#e0e0e0',

    # Text colors
    'text-primary': '#212529',
    'text-secondary': '#6c757d',
    'text-disabled': '#adb5bd',
    'text-hint': '#868e96',

    # Accent colors
    'primary': '#0066cc',
    'primary-hover': '#0052a3',
    'primary-pressed': '#004080',
    'primary-light': '#3385d6',

    'secondary': '#6c757d',
    'secondary-hover': '#5a6268',
    'secondary-pressed': '#4e555b',

    'success': '#28a745',
    'success-hover': '#218838',
    'success-pressed': '#1e7e34',
    'success-bg': '#d4edda',

    'warning': '#fd7e14',
    'warning-hover': '#e8590c',
    'warning-pressed': '#d44a06',
    'warning-bg': '#fff3cd',

    'danger': '#dc3545',
    'danger-hover': '#c82333',
    'danger-pressed': '#bd2130',
    'danger-bg': '#f8d7da',

    'info': '#17a2b8',
    'info-hover': '#138496',
    'info-pressed': '#0f6c7a',
    'info-bg': '#d1ecf1',

    # RPG-specific
    'magic': '#9c27b0',
    'gold': '#d4af37',

    # State colors
    'hover-overlay': 'rgba(0, 0, 0, 0.03)',
    'selected': '#0066cc20',
    'focus': '#0066cc60',

    # Semantic extras (used by property-based QSS variants)
    'muted': '#6c757d',
    'on-primary': '#ffffff',
    'alt-base': '#f5f5f5',
    'link': '#0066cc',
    'code-bg': '#eceff1',
    'dropzone-bg': '#f5f5f5',
    'dropzone-border': '#aaaaaa',
    'dropzone-hover-bg': '#e3f2fd',
    'dropzone-hover-border': '#4a90e2',
}


def tokens_for(scheme: str) -> Dict[str, str]:
    """Token dictionary for a concrete scheme ('dark' or 'light')."""
    return LIGHT_PALETTE if scheme == 'light' else DARK_PALETTE


_RGBA_RE = re.compile(r'rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([0-9.]+)\s*)?\)')


def to_qcolor(value: str) -> QColor:
    """Convert a token value to QColor.

    Tokens use CSS notation: '#RRGGBB', '#RRGGBBAA' (alpha LAST, unlike QColor's
    '#AARRGGBB') and 'rgba(r, g, b, a)' with a in 0..1.
    """
    value = value.strip()
    match = _RGBA_RE.fullmatch(value)
    if match:
        r, g, b = (int(match.group(i)) for i in (1, 2, 3))
        alpha = float(match.group(4)) if match.group(4) is not None else 1.0
        return QColor(r, g, b, round(alpha * 255))
    if value.startswith('#') and len(value) == 9:
        return QColor(int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16), int(value[7:9], 16))
    return QColor(value)


def tokens_to_qpalette(tokens: Dict[str, str]) -> QPalette:
    """Build a complete QPalette (including the Disabled group) from tokens."""
    c = {name: to_qcolor(value) for name, value in tokens.items()}
    window, base = c['surface'], c['background']

    # QPalette(button, window) derives light/mid/dark/shadow shades for Fusion bevels
    palette = QPalette(c['surface-elevated'], window)

    roles = {
        QPalette.ColorRole.Window: window,
        QPalette.ColorRole.WindowText: c['text-primary'],
        QPalette.ColorRole.Base: base,
        QPalette.ColorRole.AlternateBase: c['alt-base'],
        QPalette.ColorRole.Text: c['text-primary'],
        QPalette.ColorRole.Button: c['surface-elevated'],
        QPalette.ColorRole.ButtonText: c['text-primary'],
        QPalette.ColorRole.BrightText: c['danger'],
        QPalette.ColorRole.ToolTipBase: c['surface-elevated'],
        QPalette.ColorRole.ToolTipText: c['text-primary'],
        QPalette.ColorRole.PlaceholderText: c['text-hint'],
        QPalette.ColorRole.Highlight: c['primary'],
        QPalette.ColorRole.HighlightedText: c['on-primary'],
        QPalette.ColorRole.Link: c['link'],
        QPalette.ColorRole.LinkVisited: c['magic'],
    }
    for role, color in roles.items():
        palette.setColor(role, color)

    disabled = QPalette.ColorGroup.Disabled
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText):
        palette.setColor(disabled, role, c['text-disabled'])
    palette.setColor(disabled, QPalette.ColorRole.Highlight, c['border'])
    palette.setColor(disabled, QPalette.ColorRole.HighlightedText, c['text-disabled'])
    return palette
