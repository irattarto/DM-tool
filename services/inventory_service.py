"""
Inventory item management service for RPG Database Manager.
"""

import json
from typing import List, Optional

from models.database import DatabaseManager
from models.inventory_item import InventoryItem
from utils.logger import get_logger


class InventoryService:
    """
    Service for managing inventory items (weapons, armor, consumables, etc.).

    Handles inventory creation, retrieval, updates, and deletion for characters/NPCs.
    """

    def __init__(self, database_manager: DatabaseManager):
        """
        Initialize inventory service.

        Args:
            database_manager: Database manager instance
        """
        self.db = database_manager
        self.logger = get_logger('inventory_service')

    def create_inventory_item(self, module_id: int, parent_document_id: int, title: str,
                               content: str = "", item_type: str = "misc",
                               quantity: int = 1, equipped: bool = False) -> Optional[int]:
        """Create a new inventory item as a document."""
        try:
            # Create inventory document with metadata
            metadata = {
                'parent_document_id': parent_document_id,
                'item_type': item_type,
                'quantity': quantity,
                'equipped': equipped,
            }

            # Create the inventory document with metadata
            document_id = self.db.create_document(
                module_id=module_id,
                entity_type='inventory_item',
                title=title,
                content=content,
                created_by='user',
                status='active',
                metadata=json.dumps(metadata)
            )

            if document_id:
                self.logger.info(f"Created inventory item: {title} for character {parent_document_id}")
                return document_id
            else:
                self.logger.error("Failed to create inventory item document")
                return None

        except Exception as e:
            self.logger.error(f"Error creating inventory item: {e}")
            return None

    def get_inventory_items(self, module_id: Optional[int] = None,
                            parent_document_id: Optional[int] = None,
                            item_type: Optional[str] = None,
                            equipped_only: bool = False) -> List[InventoryItem]:
        """Get inventory items from documents."""
        try:
            # Get inventory item documents
            inventory_docs = self.db.get_documents(module_id, 'inventory_item')

            items = []
            for doc in inventory_docs:
                try:
                    # Parse metadata to extract inventory information
                    metadata = {}
                    if doc.get('metadata'):
                        metadata = json.loads(doc['metadata'])
                        self.logger.debug(f"Loaded metadata for inventory item {doc['id']}: {metadata}")

                    # Skip if parent_document_id filter is specified and doesn't match
                    if parent_document_id and metadata.get('parent_document_id') != parent_document_id:
                        continue

                    # Skip if item_type filter is specified and doesn't match
                    if item_type and metadata.get('item_type') != item_type:
                        continue

                    # Skip if equipped_only filter is specified and item is not equipped
                    if equipped_only and not metadata.get('equipped', False):
                        continue

                    # Create InventoryItem object from document
                    item = InventoryItem.from_document(doc)
                    items.append(item)
                except Exception as e:
                    self.logger.warning(f"Error parsing inventory item document {doc['id']}: {e}")

            return items
        except Exception as e:
            self.logger.error(f"Error getting inventory items: {e}")
            return []

    def get_inventory_item(self, item_id: int) -> Optional[InventoryItem]:
        """Get a specific inventory item by ID."""
        try:
            doc = self.db.get_document(item_id)
            if doc and doc.get('entity_type') == 'inventory_item':
                return InventoryItem.from_document(doc)
            return None
        except Exception as e:
            self.logger.error(f"Error getting inventory item {item_id}: {e}")
            return None

    def update_inventory_item(self, item_id: int, title: str, content: str,
                               item_type: Optional[str] = None,
                               quantity: Optional[int] = None,
                               equipped: Optional[bool] = None) -> bool:
        """Update an existing inventory item document."""
        try:
            # Get current document to preserve metadata
            current_doc = self.db.get_document(item_id)
            if not current_doc:
                self.logger.error(f"Inventory item document {item_id} not found")
                return False

            # Parse existing metadata
            metadata = {}
            if current_doc.get('metadata'):
                metadata = json.loads(current_doc['metadata'])

            self.logger.debug(f"Current metadata for inventory item {item_id}: {metadata}")

            # Update metadata
            if item_type is not None:
                metadata['item_type'] = item_type
            if quantity is not None:
                metadata['quantity'] = max(1, quantity)  # Ensure at least 1
            if equipped is not None:
                metadata['equipped'] = equipped

            # Update document with metadata
            metadata_str = json.dumps(metadata)
            success = self.db.update_document(
                document_id=item_id,
                title=title,
                content=content,
                metadata=metadata_str
            )

            if success:
                self.logger.info(f"Updated inventory item document {item_id}")
            else:
                self.logger.error(f"Failed to update inventory item document {item_id}")

            return success
        except Exception as e:
            self.logger.error(f"Error updating inventory item {item_id}: {e}")
            return False

    def toggle_equipped(self, item_id: int) -> bool:
        """Toggle the equipped status of an inventory item."""
        try:
            item = self.get_inventory_item(item_id)
            if not item:
                return False

            return self.update_inventory_item(
                item_id=item_id,
                title=item.title,
                content=item.content,
                equipped=not item.equipped
            )
        except Exception as e:
            self.logger.error(f"Error toggling equipped status for item {item_id}: {e}")
            return False
