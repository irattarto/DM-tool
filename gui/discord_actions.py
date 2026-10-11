"""Entry points used by the UI to send things to Discord (always through the confirm dialog)."""

import os
from typing import Any, Dict, List, Optional

from PyQt6.QtWidgets import QWidget

from config.paths import resolve_image_path
from gui.dialogs.discord_entity_picker import DiscordEntityPickerDialog, EntityChoice
from gui.dialogs.discord_send_dialog import DiscordSendDialog, SendItem
from services.discord_service import clean_text
from utils.logger import get_logger
from utils.ui_helpers import show_warning


def entity_name_for(db, document_id: Optional[int], fallback: str = "") -> str:
    """The name that travels with an image: the entity's title."""
    if document_id and db is not None:
        try:
            document = db.get_document(document_id)
            if document and document.get('title'):
                return document['title']
        except Exception as e:
            get_logger('discord_actions').debug(f"Could not look up the entity name: {e}")
    return fallback


def send_images_to_discord(parent: Optional[QWidget], db, module_id: Optional[int],
                           images: List[Dict[str, Any]], entity_name: str = "") -> None:
    """Open the preview dialog for images (caption = the entity name)."""
    items = []
    for image in images:
        path = resolve_image_path(image)
        if not path or not os.path.isfile(path):
            continue
        caption = entity_name or image.get('original_name') or ""
        items.append(SendItem(kind='image', path=path, caption=caption))
    if not items:
        show_warning(parent, "Nothing to send", "No image file was found on disk for this selection.")
        return
    DiscordSendDialog(db, module_id, items, parent).exec()


def send_text_to_discord(parent: Optional[QWidget], db, module_id: Optional[int], text: str) -> None:
    """Open the preview dialog for a piece of text."""
    text = clean_text(text)
    if not text:
        show_warning(parent, "Nothing to send", "Select some text first.")
        return
    DiscordSendDialog(db, module_id, [SendItem(kind='text', text=text)], parent).exec()


DISCORD_ENTITY_TYPES = ('npc', 'location')   # tabs that offer "Send to Discord..."


def entity_choices(db, module_id: Optional[int], entity_type: str) -> List[EntityChoice]:
    """Every entity of the type with its primary image file (``path`` is '' when it has none)."""
    choices = []
    for document in db.get_documents(module_id, entity_type):
        image = db.get_primary_image(document['id'])
        path = resolve_image_path(image) if image else ''
        if path and not os.path.isfile(path):
            path = ''
        choices.append(EntityChoice(id=document['id'], name=document.get('title') or '', path=path))
    return choices


def send_entities_to_discord(parent: Optional[QWidget], db, module_id: Optional[int], entity_type: str,
                             label: str, preselected_ids=()) -> None:
    """Pick entities (name + primary picture), then show the usual preview-and-confirm dialog."""
    if not module_id:
        show_warning(parent, "No Campaign", "Please create or open a campaign first.")
        return
    choices = entity_choices(db, module_id, entity_type)
    if not choices:
        show_warning(parent, "Nothing to send", f"This campaign has no {label.lower()} yet.")
        return
    picker = DiscordEntityPickerDialog(choices, label, preselected_ids, parent)
    if picker.exec() != picker.DialogCode.Accepted:
        return
    items = [SendItem(kind='embed', path=choice.path, caption=choice.name) for choice in picker.selected_choices()]
    if items:
        DiscordSendDialog(db, module_id, items, parent).exec()
