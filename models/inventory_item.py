"""
Inventory item models for RPG Database Manager.
"""

import json
from typing import Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime



@dataclass
class InventoryItem:
    """
    Represents an individual inventory item for a character or NPC.
    """

    id: Optional[int] = None
    module_id: Optional[int] = None
    parent_document_id: Optional[int] = None  # Character/NPC ID
    title: str = ""
    content: str = ""  # Rich text description
    item_type: str = "misc"  # 'weapon', 'armor', 'magic', 'consumable', 'quest', 'misc'
    quantity: int = 1
    equipped: bool = False
    created_date: Optional[datetime] = None
    modified_date: Optional[datetime] = None

    def __post_init__(self):
        """Convert date strings and ensure quantity is int."""
        if isinstance(self.created_date, str):
            self.created_date = datetime.fromisoformat(self.created_date)

        if isinstance(self.modified_date, str):
            self.modified_date = datetime.fromisoformat(self.modified_date)

        # Ensure quantity is at least 1
        if self.quantity < 1:
            self.quantity = 1

    @classmethod
    def from_document(cls, document: Dict[str, Any]) -> 'InventoryItem':
        """Create InventoryItem from document dictionary."""
        # Parse metadata JSON
        metadata = {}
        if 'metadata' in document and document['metadata']:
            try:
                metadata = json.loads(document['metadata']) if isinstance(document['metadata'], str) else document['metadata']
            except json.JSONDecodeError:
                metadata = {}

        return cls(
            id=document.get('id'),
            module_id=document.get('module_id'),
            parent_document_id=metadata.get('parent_document_id'),
            title=document.get('title', ''),
            content=document.get('content', ''),
            item_type=metadata.get('item_type', 'misc'),
            quantity=metadata.get('quantity', 1),
            equipped=metadata.get('equipped', False),
            created_date=document.get('created_date'),
            modified_date=document.get('modified_date')
        )

    def to_document_dict(self) -> Dict[str, Any]:
        """Convert InventoryItem to document dictionary for database storage."""
        metadata = {
            'parent_document_id': self.parent_document_id,
            'item_type': self.item_type,
            'quantity': self.quantity,
            'equipped': self.equipped,
        }

        return {
            'id': self.id,
            'module_id': self.module_id,
            'entity_type': 'inventory_item',
            'title': self.title,
            'content': self.content,
            'metadata': json.dumps(metadata),
            'status': 'active',
        }

    def get_summary(self, max_length: int = 100) -> str:
        """Get a summary of the item description."""
        # Strip HTML tags and get plain text
        import re
        plain_text = re.sub('<[^<]+?>', '', self.content)
        plain_text = ' '.join(plain_text.split())

        if len(plain_text) <= max_length:
            return plain_text

        # Find a good break point
        summary = plain_text[:max_length]
        last_space = summary.rfind(' ')

        if last_space > max_length * 0.8:
            summary = summary[:last_space] + "..."
        else:
            summary += "..."

        return summary

    def get_display_text(self) -> str:
        """Get formatted text for list display."""
        type_label = self.item_type.capitalize()
        equipped_marker = " [E]" if self.equipped else ""
        quantity_text = f" x{self.quantity}" if self.quantity > 1 else ""
        return f"{self.title}{quantity_text} ({type_label}){equipped_marker}"

    def toggle_equipped(self) -> None:
        """Toggle equipped status."""
        self.equipped = not self.equipped
