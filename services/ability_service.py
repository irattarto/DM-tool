"""
Ability item management service for RPG Database Manager.
"""

import json
from typing import List, Optional

from models.database import DatabaseManager
from models.ability_item import AbilityItem
from utils.logger import get_logger


class AbilityService:
    """
    Service for managing ability items (skills, spells, feats, traits).

    Handles ability creation, retrieval, updates, and deletion for characters/NPCs.
    """

    def __init__(self, database_manager: DatabaseManager):
        """
        Initialize ability service.

        Args:
            database_manager: Database manager instance
        """
        self.db = database_manager
        self.logger = get_logger('ability_service')

    def create_ability(self, module_id: int, parent_document_id: int, title: str,
                       content: str = "", ability_type: str = "skill") -> Optional[int]:
        """Create a new ability item as a document."""
        try:
            # Create ability document with metadata
            metadata = {
                'parent_document_id': parent_document_id,
                'ability_type': ability_type,
            }

            # Create the ability document with metadata
            document_id = self.db.create_document(
                module_id=module_id,
                entity_type='ability_item',
                title=title,
                content=content,
                created_by='user',
                status='active',
                metadata=json.dumps(metadata)
            )

            if document_id:
                self.logger.info(f"Created ability item: {title} for character {parent_document_id}")
                return document_id
            else:
                self.logger.error("Failed to create ability item document")
                return None

        except Exception as e:
            self.logger.error(f"Error creating ability item: {e}")
            return None

    def get_abilities(self, module_id: Optional[int] = None,
                      parent_document_id: Optional[int] = None,
                      ability_type: Optional[str] = None) -> List[AbilityItem]:
        """Get ability items from documents."""
        try:
            # Get ability item documents
            ability_docs = self.db.get_documents(module_id, 'ability_item')

            abilities = []
            for doc in ability_docs:
                try:
                    # Parse metadata to extract ability information
                    metadata = {}
                    if doc.get('metadata'):
                        metadata = json.loads(doc['metadata'])
                        self.logger.debug(f"Loaded metadata for ability {doc['id']}: {metadata}")

                    # Skip if parent_document_id filter is specified and doesn't match
                    if parent_document_id and metadata.get('parent_document_id') != parent_document_id:
                        continue

                    # Skip if ability_type filter is specified and doesn't match
                    if ability_type and metadata.get('ability_type') != ability_type:
                        continue

                    # Create AbilityItem object from document
                    ability = AbilityItem.from_document(doc)
                    abilities.append(ability)
                except Exception as e:
                    self.logger.warning(f"Error parsing ability item document {doc['id']}: {e}")

            return abilities
        except Exception as e:
            self.logger.error(f"Error getting ability items: {e}")
            return []

    def update_ability(self, ability_id: int, title: str, content: str,
                       ability_type: Optional[str] = None) -> bool:
        """Update an existing ability item document."""
        try:
            # Get current document to preserve metadata
            current_doc = self.db.get_document(ability_id)
            if not current_doc:
                self.logger.error(f"Ability item document {ability_id} not found")
                return False

            # Parse existing metadata
            metadata = {}
            if current_doc.get('metadata'):
                metadata = json.loads(current_doc['metadata'])

            self.logger.debug(f"Current metadata for ability {ability_id}: {metadata}")

            # Update metadata
            if ability_type is not None:
                metadata['ability_type'] = ability_type

            # Update document with metadata
            metadata_str = json.dumps(metadata)
            success = self.db.update_document(
                document_id=ability_id,
                title=title,
                content=content,
                metadata=metadata_str
            )

            if success:
                self.logger.info(f"Updated ability item document {ability_id}")
            else:
                self.logger.error(f"Failed to update ability item document {ability_id}")

            return success
        except Exception as e:
            self.logger.error(f"Error updating ability item {ability_id}: {e}")
            return False
