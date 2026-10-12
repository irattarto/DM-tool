"""Creating one entry quickly (from a name found in a text, a selection, or a capture): template if there is one."""

from typing import Optional

from config.entity_types import get_registry


def create_entry(db, template_service, campaign_id: int, kind: str, title: str) -> Optional[int]:
    """A new entry of ``kind`` called ``title``: from the default template of the type, else a short blank text."""
    title = title.strip()
    if not title:
        return None
    template = template_service.get_default_template(kind) if template_service is not None else None
    if template:
        doc_id = template_service.create_document_from_template(template, {}, title, campaign_id)
        if doc_id:
            return doc_id
    return db.create_document(campaign_id, kind, title, f"{get_registry().label(kind)}: {title}\n\n[Add your content here...]",
                              created_by="user", status="draft")
