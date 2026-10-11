"""
Game session management service for RPG Database Manager.
"""

import json
from typing import List, Optional
from datetime import datetime, date

from models.database import DatabaseManager
from models.session import GameSession
from services.parsing_service import ParsingService
from utils.logger import get_logger


class SessionService:
    """
    Service for managing game sessions and progress tracking.

    Handles session creation, logging, progress analysis, and
    integration with the document-centric RPG database.
    """

    def __init__(self, database_manager: DatabaseManager):
        """
        Initialize session service.

        Args:
            database_manager: Database manager instance
        """
        self.db = database_manager
        self.parsing_service = ParsingService()
        self.logger = get_logger('session_service')

    def create_session(self, module_id: int, session_date: date, title: str,
                        content: str = "", participants: Optional[List[str]] = None,
                        duration_minutes: Optional[int] = None, status: str = "planned") -> Optional[int]:
        """Create a new game session as a document."""
        try:
            # Create session document with metadata
            metadata = {
                'session_date': session_date.isoformat(),
                'participants': participants or [],
                'duration_minutes': duration_minutes,
                'session_type': 'game_session',
                'status': status
            }

            # Create the session document with metadata
            document_id = self.db.create_document(
                module_id=module_id,
                entity_type='session',
                title=title,
                content=content,
                created_by='user',
                status='draft',
                metadata=json.dumps(metadata)
            )

            if document_id:
                self.logger.info(f"Created session document: {title} for module {module_id} with metadata: {metadata}")
                return document_id
            else:
                self.logger.error("Failed to create session document")
                return None

        except Exception as e:
            self.logger.error(f"Error creating session: {e}")
            return None

    def get_sessions(self, module_id: Optional[int] = None, status: Optional[str] = None) -> List[GameSession]:
        """Get game sessions from documents."""
        try:
            # Get session documents
            session_docs = self.db.get_documents(module_id, 'session')

            sessions = []
            for doc in session_docs:
                try:
                    # Parse metadata to extract session information (for backward compatibility)
                    metadata = {}
                    if doc.get('metadata'):
                        metadata = json.loads(doc['metadata'])
                        self.logger.debug(f"Loaded metadata for session {doc['id']}: {metadata}")
                    else:
                        self.logger.debug(f"No metadata found for session {doc['id']}, using defaults")

                    # Skip if status filter is specified and doesn't match
                    if status and metadata.get('status') != status:
                        continue

                    # Create GameSession object from document
                    session = GameSession(
                        id=doc['id'],
                        module_id=doc['module_id'],
                        session_date=metadata.get('session_date'),
                        title=doc['title'],
                        content=doc['content'],
                        participants=metadata.get('participants', []),
                        duration_minutes=metadata.get('duration_minutes'),
                        created_date=datetime.fromisoformat(doc['created_date']) if doc.get('created_date') else None,
                        status=metadata.get('status', 'planned')
                    )
                    sessions.append(session)
                except Exception as e:
                    self.logger.warning(f"Error parsing session document {doc['id']}: {e}")

            return sessions
        except Exception as e:
            self.logger.error(f"Error getting sessions: {e}")
            return []

    def get_session(self, session_id: int) -> Optional[GameSession]:
        """Get a specific session by ID."""
        try:
            # This would need to be implemented in DatabaseManager
            sessions = self.get_sessions()
            for session in sessions:
                if session.id == session_id:
                    return session
            return None
        except Exception as e:
            self.logger.error(f"Error getting session {session_id}: {e}")
            return None

    def delete_session(self, session_id: int) -> bool:
        """Delete a session document."""
        try:
            success = self.db.delete_document(session_id)
            if success:
                self.logger.info(f"Deleted session document {session_id}")
            else:
                self.logger.error(f"Failed to delete session document {session_id}")
            return success
        except Exception as e:
            self.logger.error(f"Error deleting session {session_id}: {e}")
            return False
