"""Application stylesheet generated from design tokens.

Base colours come from the QPalette (Fusion style); this stylesheet only adds
what a palette cannot express: semantic variants selected with dynamic
properties, e.g. ``button.setProperty("variant", "danger")``.

Properties:
  QPushButton[variant]   primary | secondary | success | danger | flat
  QLabel[role]           muted | hint | caption | heading | h1 | status | strong | accent | badge-warning
  QLabel[state]          ok | warning | error
  QWidget[role]          card | dropzone (+ [dragActive="true"]) | code
  QPlainTextEdit[variant] warning
Dynamic property changes at runtime need ``repolish(widget)`` (gui.theme.manager).
"""

from typing import Dict


def build_qss(t: Dict[str, str], typography: Dict[str, Dict]) -> str:
    """Return the application stylesheet for a token set."""
    radius = 4
    typography['body']['size']
    caption = typography['caption']['size']
    h1 = typography['h1']['size']
    h2 = typography['h2']['size']
    button = typography['button']['size']

    def variant(name: str, base: str, hover: str, pressed: str) -> str:
        return f"""
QPushButton[variant="{name}"] {{
    background-color: {t[base]};
    color: {t['on-primary']};
    border: 1px solid {t[base]};
    border-radius: {radius}px;
    padding: 5px 14px;
    font-size: {button}pt;
}}
QPushButton[variant="{name}"]:hover {{ background-color: {t[hover]}; border-color: {t[hover]}; }}
QPushButton[variant="{name}"]:pressed {{ background-color: {t[pressed]}; border-color: {t[pressed]}; }}
QPushButton[variant="{name}"]:disabled {{
    background-color: {t['surface-elevated']};
    border-color: {t['border']};
    color: {t['text-disabled']};
}}
"""

    qss = f"""
QToolTip {{
    background-color: {t['surface-elevated']};
    color: {t['text-primary']};
    border: 1px solid {t['border']};
    padding: 4px 6px;
}}
"""
    qss += variant('primary', 'primary', 'primary-hover', 'primary-pressed')
    qss += variant('secondary', 'secondary', 'secondary-hover', 'secondary-pressed')
    qss += variant('success', 'success', 'success-hover', 'success-pressed')
    qss += variant('danger', 'danger', 'danger-hover', 'danger-pressed')
    qss += f"""
QPushButton[variant="flat"] {{
    background: transparent;
    border: none;
    color: {t['text-primary']};
}}
QPushButton[variant="flat"]:hover {{ background-color: {t['hover-overlay']}; }}

QLabel[role="muted"] {{ color: {t['muted']}; }}
QLabel[role="hint"] {{ color: {t['muted']}; font-size: {caption}pt; font-style: italic; }}
QLabel[role="status"] {{ font-size: {h2}pt; font-weight: bold; }}
QCheckBox[role="caption"] {{ font-size: {caption}pt; }}
QLabel[role="caption"] {{ color: {t['muted']}; font-size: {caption}pt; }}
QLabel[role="heading"] {{ font-size: {h2}pt; font-weight: bold; }}
QLabel[role="h1"] {{ font-size: {h1}pt; font-weight: bold; }}
QLabel[role="strong"] {{ font-weight: bold; }}
QLabel[role="accent"] {{ color: {t['primary']}; font-weight: bold; }}
QLabel[role="badge-warning"] {{
    background-color: {t['warning-bg']};
    color: {t['warning']};
    border: 1px solid {t['warning']};
    border-radius: {radius}px;
    padding: 6px 8px;
}}

QPlainTextEdit[variant="warning"] {{
    background-color: {t['warning-bg']};
    color: {t['warning']};
    border: 2px solid {t['warning']};
    border-radius: {radius}px;
    padding: 10px;
    font-weight: bold;
}}

QLabel[state="ok"] {{ color: {t['success']}; }}
QLabel[state="warning"] {{ color: {t['warning']}; }}
QLabel[state="error"] {{ color: {t['danger']}; font-weight: bold; }}

QFrame[role="card"], QLabel[role="card"] {{
    padding: 4px;
    background-color: {t['surface']};
    border: 1px solid {t['border']};
    border-radius: {radius}px;
}}
QFrame[role="dropzone"], QLabel[role="dropzone"] {{
    background-color: {t['dropzone-bg']};
    border: 2px dashed {t['dropzone-border']};
    border-radius: {radius + 2}px;
    color: {t['muted']};
}}
QFrame[role="dropzone"][dragActive="true"], QLabel[role="dropzone"][dragActive="true"] {{
    background-color: {t['dropzone-hover-bg']};
    border-color: {t['dropzone-hover-border']};
}}
QWidget[role="code"] {{
    padding: 8px;
    background-color: {t['code-bg']};
    color: {t['text-primary']};
}}
"""
    return qss
