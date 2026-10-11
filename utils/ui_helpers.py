"""
UI helper utilities for RPG Database Manager.
"""

from typing import Optional

from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtCore import Qt


def show_error(parent, title: str, message: str, detailed_text: Optional[str] = None):
    """
    Show an error message box with selectable text.

    Args:
        parent: Parent widget
        title: Dialog title
        message: Main error message
        detailed_text: Optional detailed error text
    """
    msg_box = QMessageBox(parent)
    msg_box.setIcon(QMessageBox.Icon.Critical)
    msg_box.setWindowTitle(title)
    msg_box.setTextFormat(Qt.TextFormat.PlainText)  # messages contain document/campaign names: never render them as HTML
    msg_box.setText(message)

    if detailed_text:
        msg_box.setDetailedText(detailed_text)

    # Make text selectable
    msg_box.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard)

    msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
    msg_box.exec()


def show_warning(parent, title: str, message: str, detailed_text: Optional[str] = None):
    """
    Show a warning message box with selectable text.

    Args:
        parent: Parent widget
        title: Dialog title
        message: Main warning message
        detailed_text: Optional detailed warning text
    """
    msg_box = QMessageBox(parent)
    msg_box.setIcon(QMessageBox.Icon.Warning)
    msg_box.setWindowTitle(title)
    msg_box.setTextFormat(Qt.TextFormat.PlainText)  # messages contain document/campaign names: never render them as HTML
    msg_box.setText(message)

    if detailed_text:
        msg_box.setDetailedText(detailed_text)

    # Make text selectable
    msg_box.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard)

    msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
    msg_box.exec()


def show_info(parent, title: str, message: str, detailed_text: Optional[str] = None):
    """
    Show an information message box with selectable text.

    Args:
        parent: Parent widget
        title: Dialog title
        message: Main information message
        detailed_text: Optional detailed information text
    """
    msg_box = QMessageBox(parent)
    msg_box.setIcon(QMessageBox.Icon.Information)
    msg_box.setWindowTitle(title)
    msg_box.setTextFormat(Qt.TextFormat.PlainText)  # messages contain document/campaign names: never render them as HTML
    msg_box.setText(message)

    if detailed_text:
        msg_box.setDetailedText(detailed_text)

    # Make text selectable
    msg_box.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard)

    msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
    msg_box.exec()


def show_question(parent, title: str, message: str) -> bool:
    """
    Show a yes/no question dialog with selectable text.

    Args:
        parent: Parent widget
        title: Dialog title
        message: Question message

    Returns:
        bool: True if user clicked Yes, False otherwise
    """
    msg_box = QMessageBox(parent)
    msg_box.setIcon(QMessageBox.Icon.Question)
    msg_box.setWindowTitle(title)
    msg_box.setTextFormat(Qt.TextFormat.PlainText)  # messages contain document/campaign names: never render them as HTML
    msg_box.setText(message)

    # Make text selectable
    msg_box.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard)

    msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    msg_box.setDefaultButton(QMessageBox.StandardButton.No)

    return msg_box.exec() == QMessageBox.StandardButton.Yes
