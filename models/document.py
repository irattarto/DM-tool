"""
Document and template models for RPG Database Manager.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

from utils.logger import get_logger


@dataclass
class DocumentTemplate:
    """
    Represents a document template for creating new entities.
    """

    id: Optional[int] = None
    template_name: str = ""
    entity_type: str = ""
    template_content: str = ""
    is_default: bool = False
    created_date: Optional[datetime] = None
    modified_date: Optional[datetime] = None

    def __post_init__(self):
        """Convert date strings to datetime objects if needed."""
        if isinstance(self.created_date, str):
            self.created_date = datetime.fromisoformat(self.created_date)
        if isinstance(self.modified_date, str):
            self.modified_date = datetime.fromisoformat(self.modified_date)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DocumentTemplate':
        """Create DocumentTemplate from dictionary."""
        # Handle date conversion
        if 'created_date' in data and data['created_date']:
            if isinstance(data['created_date'], str):
                data['created_date'] = datetime.fromisoformat(data['created_date'])
        if 'modified_date' in data and data['modified_date']:
            if isinstance(data['modified_date'], str):
                data['modified_date'] = datetime.fromisoformat(data['modified_date'])

        return cls(**data)

    def to_dict(self) -> Dict[str, Any]:
        """Convert DocumentTemplate to dictionary."""
        data = {
            'id': self.id,
            'template_name': self.template_name,
            'entity_type': self.entity_type,
            'template_content': self.template_content,
            'is_default': self.is_default,
            'created_date': self.created_date.isoformat() if self.created_date else None,
            'modified_date': self.modified_date.isoformat() if self.modified_date else None,
        }
        return data

    def get_placeholders(self) -> List[str]:
        """Extract placeholder fields from template content."""
        import re

        # Find all placeholders in format [Field Name]
        placeholder_pattern = r'\[([^\]]+)\]'
        placeholders = re.findall(placeholder_pattern, self.template_content)

        return placeholders

    def apply_template(self, field_values: Dict[str, str]) -> str:
        """Apply field values to template to generate document content."""
        import re

        # Single pass so substituted values are never re-scanned for placeholders
        def _sub(match):
            key = match.group(1)
            if key in field_values:
                return str(field_values[key])
            return match.group(0)

        return re.sub(r'\[([^\]]+)\]', _sub, self.template_content)


@dataclass
class Document:
    """
    Represents an RPG entity document (NPC, faction, character, etc.).
    """

    id: Optional[int] = None
    module_id: Optional[int] = None
    entity_type: str = ""  # npc, faction, character, quest, etc.
    title: str = ""
    content: str = ""
    metadata: Optional[str] = None  # JSON metadata for additional fields
    created_date: Optional[datetime] = None
    modified_date: Optional[datetime] = None
    created_by: str = "user"  # 'user' or 'ai'
    status: str = "draft"  # 'draft', 'approved', 'archived'

    def __post_init__(self):
        """Convert date strings and metadata JSON if needed."""
        if isinstance(self.created_date, str):
            self.created_date = datetime.fromisoformat(self.created_date)
        if isinstance(self.modified_date, str):
            self.modified_date = datetime.fromisoformat(self.modified_date)



    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Document':
        """Create Document from dictionary."""
        data = data.copy()

        # Handle date conversion with error handling
        for date_field in ['created_date', 'modified_date']:
            if date_field in data and data[date_field]:
                if isinstance(data[date_field], str):
                    try:
                        data[date_field] = datetime.fromisoformat(data[date_field])
                    except ValueError as e:
                        get_logger('document').warning(f"Failed to parse date {date_field}: {e}")
                        data[date_field] = None

        # Filter out any keys that aren't valid Document fields
        # This handles database queries with extra columns (like abilities_content, etc.)
        valid_fields = {
            'id', 'module_id', 'entity_type', 'title', 'content',
            'metadata', 'created_date', 'modified_date', 'created_by', 'status'
        }
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}

        return cls(**filtered_data)

    def to_dict(self) -> Dict[str, Any]:
        """Convert Document to dictionary for database storage."""
        data = {
            'id': self.id,
            'module_id': self.module_id,
            'entity_type': self.entity_type,
            'title': self.title,
            'content': self.content,
            'metadata': self.metadata,
            'created_date': self.created_date.isoformat() if self.created_date else None,
            'modified_date': self.modified_date.isoformat() if self.modified_date else None,
            'created_by': self.created_by,
            'status': self.status,
        }
        return data

    def get_summary(self, max_length: int = 200) -> str:
        """Get a summary of the document content."""
        # Remove extra whitespace and get first paragraph or first N characters
        content = ' '.join(self.content.split())

        if len(content) <= max_length:
            return content

        # Try to find a good break point
        summary = content[:max_length]
        last_space = summary.rfind(' ')

        if last_space > max_length * 0.8:
            summary = summary[:last_space] + "..."
        else:
            summary += "..."

        return summary

    def approve(self) -> None:
        """Mark document as approved."""
        self.status = "approved"

    def archive(self) -> None:
        """Mark document as archived."""
        self.status = "archived"
