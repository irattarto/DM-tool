"""
Game session models for RPG Database Manager.
"""

import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime



@dataclass
class GameSession:
    """
    Represents a game session with logging and progress tracking.
    """

    id: Optional[int] = None
    module_id: Optional[int] = None
    session_date: Optional[str] = None  # Date in YYYY-MM-DD format
    title: str = ""
    content: str = ""  # Rich text session log
    participants: Optional[List[str]] = None
    duration_minutes: Optional[int] = None
    created_date: Optional[datetime] = None
    status: str = "planned"  # 'planned', 'active', or 'played'

    def __post_init__(self):
        """Convert date strings and participants JSON if needed."""
        if isinstance(self.created_date, str):
            self.created_date = datetime.fromisoformat(self.created_date)

        if isinstance(self.participants, str):
            try:
                self.participants = json.loads(self.participants)
            except json.JSONDecodeError:
                self.participants = []

        if self.participants is None:
            self.participants = []

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GameSession':
        """Create GameSession from dictionary."""
        # Handle participants conversion
        if 'participants' in data and isinstance(data['participants'], str):
            try:
                data['participants'] = json.loads(data['participants'])
            except json.JSONDecodeError:
                data['participants'] = []

        # Handle date conversion
        if 'created_date' in data and data['created_date']:
            if isinstance(data['created_date'], str):
                data['created_date'] = datetime.fromisoformat(data['created_date'])

        return cls(**data)

    def to_dict(self) -> Dict[str, Any]:
        """Convert GameSession to dictionary for database storage."""
        data = {
            'id': self.id,
            'module_id': self.module_id,
            'session_date': self.session_date,
            'title': self.title,
            'content': self.content,
            'participants': json.dumps(self.participants) if self.participants else None,
            'duration_minutes': self.duration_minutes,
            'created_date': self.created_date.isoformat() if self.created_date else None,
            'status': self.status,
        }
        return data

    def get_summary(self, max_length: int = 200) -> str:
        """Get a summary of the session content."""
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
