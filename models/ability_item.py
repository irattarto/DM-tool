"""
Ability item models for RPG Database Manager.
"""

import json
from typing import Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime



@dataclass
class AbilityItem:
    """
    Represents an individual ability (skill, spell, feat, trait) for a character or NPC.
    """

    id: Optional[int] = None
    module_id: Optional[int] = None
    parent_document_id: Optional[int] = None  # Character/NPC ID
    title: str = ""
    content: str = ""  # Rich text description
    ability_type: str = "other"  # 'skill', 'spell', 'feat', 'trait', 'other'
    created_date: Optional[datetime] = None
    modified_date: Optional[datetime] = None

    def __post_init__(self):
        """Convert date strings if needed."""
        if isinstance(self.created_date, str):
            self.created_date = datetime.fromisoformat(self.created_date)

        if isinstance(self.modified_date, str):
            self.modified_date = datetime.fromisoformat(self.modified_date)

    @classmethod
    def from_document(cls, document: Dict[str, Any]) -> 'AbilityItem':
        """Create AbilityItem from document dictionary."""
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
            ability_type=metadata.get('ability_type', 'skill'),
            created_date=document.get('created_date'),
            modified_date=document.get('modified_date')
        )

    def to_document_dict(self) -> Dict[str, Any]:
        """Convert AbilityItem to document dictionary for database storage."""
        metadata = {
            'parent_document_id': self.parent_document_id,
            'ability_type': self.ability_type,
        }

        return {
            'id': self.id,
            'module_id': self.module_id,
            'entity_type': 'ability_item',
            'title': self.title,
            'content': self.content,
            'metadata': json.dumps(metadata),
            'status': 'active',
        }

    def get_summary(self, max_length: int = 100) -> str:
        """Get a summary of the ability description."""
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
        type_label = self.ability_type.capitalize()
        return f"{self.title} ({type_label})"
