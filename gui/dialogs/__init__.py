"""
Dialog windows for the RPG Database Manager GUI.
"""

from .document_viewer import DocumentViewerWindow
from .template_editor import TemplateEditorDialog
from .document_creation_dialog import DocumentCreationDialog
from .base_dialog import StandardDialog
from .link_insertion_dialog import LinkInsertionDialog

__all__ = [
    'DocumentViewerWindow',
    'TemplateEditorDialog',
    'DocumentCreationDialog',
    'StandardDialog',
    'LinkInsertionDialog'
]
