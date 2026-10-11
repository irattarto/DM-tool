"""
Template management service for RPG Database Manager.
"""

from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime

from models.database import DatabaseManager
from models.document import DocumentTemplate
from utils.logger import get_logger


class TemplateService:
    """
    Service for managing document templates.

    Handles template creation, editing, deletion, and application
    for different entity types in the RPG system.
    """

    def __init__(self, database_manager: DatabaseManager):
        """
        Initialize template service.

        Args:
            database_manager: Database manager instance
        """
        self.db = database_manager
        self.logger = get_logger('template_service')

    def get_templates(self, entity_type: Optional[str] = None) -> List[DocumentTemplate]:
        """Get all templates or templates for a specific entity type."""
        try:
            self.logger.debug(f"Getting templates for entity_type: {entity_type}")
            template_data = self.db.get_templates(entity_type)
            self.logger.debug(f"Database returned {len(template_data)} template records")

            templates = [DocumentTemplate.from_dict(data) for data in template_data]
            self.logger.debug(f"Converted to {len(templates)} DocumentTemplate objects")
            return templates
        except Exception as e:
            self.logger.error(f"Error getting templates: {e}")
            return []

    def get_template(self, template_id: int) -> Optional[DocumentTemplate]:
        """Get a specific template by ID."""
        try:
            # This would need to be implemented in DatabaseManager
            templates = self.get_templates()
            for template in templates:
                if template.id == template_id:
                    return template
            return None
        except Exception as e:
            self.logger.error(f"Error getting template {template_id}: {e}")
            return None

    def get_default_template(self, entity_type: str) -> Optional[DocumentTemplate]:
        """Get the default template for an entity type."""
        try:
            template_data = self.db.get_default_template(entity_type)
            if template_data:
                return DocumentTemplate.from_dict(template_data)
            return None
        except Exception as e:
            self.logger.error(f"Error getting default template for {entity_type}: {e}")
            return None

    def save_template(self, template_name: str, entity_type: str,
                      template_content: str, is_default: bool = False) -> Optional[int]:
        """Save a template (create or update)."""
        try:
            template_id = self.db.save_template(
                template_name, entity_type, template_content, is_default
            )

            self.logger.info(f"Saved template '{template_name}' for {entity_type}")
            return template_id

        except Exception as e:
            self.logger.error(f"Error saving template: {e}")
            return None

    def delete_template(self, template_id: int) -> bool:
        """Delete a template."""
        try:
            # Check if template exists
            template = self.get_template(template_id)
            if not template:
                self.logger.warning(f"Template {template_id} not found")
                return False

            # Don't allow deletion of default templates
            if template.is_default:
                self.logger.warning(f"Cannot delete default template {template_id}")
                return False

            # Delete from database
            with self.db.connection.transaction() as conn:
                cursor = conn.execute("DELETE FROM document_templates WHERE id = ?", (template_id,))
                if cursor.rowcount > 0:
                    self.logger.info(f"Deleted template {template_id}: {template.template_name}")
                    return True
                else:
                    self.logger.warning(f"No template deleted with ID {template_id}")
                    return False

        except Exception as e:
            self.logger.error(f"Error deleting template {template_id}: {e}")
            return False

    def apply_template(self, template: DocumentTemplate,
                      field_values: Dict[str, str]) -> str:
        """Apply field values to a template to generate document content."""
        try:
            return template.apply_template(field_values)
        except Exception as e:
            self.logger.error(f"Error applying template: {e}")
            return template.template_content

    def create_document_from_template(self, template: DocumentTemplate,
                                     field_values: Dict[str, str],
                                     title: str, module_id: int) -> Optional[int]:
        """Create a new document from a template with field values."""
        try:
            # Apply template
            content = self.apply_template(template, field_values)

            # Create document
            self.logger.debug(f"Creating document: module_id={module_id}, entity_type={template.entity_type}, title={title}")
            document_id = self.db.create_document(
                module_id=module_id,
                entity_type=template.entity_type,
                title=title,
                content=content,
                created_by="user",
                status="draft"
            )

            self.logger.info(f"Created document from template '{template.template_name}' with ID: {document_id}")
            return document_id

        except Exception as e:
            self.logger.error(f"Error creating document from template: {e}")
            return None

    def validate_template(self, template_content: str) -> List[str]:
        """Validate template content and return any issues."""
        issues = []

        try:
            # Check for balanced placeholders
            import re
            placeholders = re.findall(r'\[([^\]]+)\]', template_content)

            if not placeholders:
                issues.append("No placeholders found in template")

            # Check for duplicate placeholders
            seen = set()
            duplicates = set()
            for placeholder in placeholders:
                if placeholder in seen:
                    duplicates.add(placeholder)
                seen.add(placeholder)

            if duplicates:
                issues.append(f"Duplicate placeholders: {', '.join(duplicates)}")

            # Check for common template issues
            lines = template_content.split('\n')
            for i, line in enumerate(lines, 1):
                if line.count('[') != line.count(']'):
                    issues.append(f"Unbalanced brackets on line {i}: {line}")

        except Exception as e:
            issues.append(f"Error validating template: {e}")

        return issues

    def import_templates(self, file_path: str) -> Dict[str, Any]:
        """Import templates from a file."""
        result = {
            'success': False,
            'imported': 0,
            'errors': []
        }

        try:
            if not Path(file_path).exists():
                result['errors'].append(f"File not found: {file_path}")
                return result

            # Simple JSON import for now
            # Could be enhanced to support other formats
            import json

            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if not isinstance(data, list):
                result['errors'].append("Invalid file format - expected list of templates")
                return result

            for template_data in data:
                try:
                    template = DocumentTemplate.from_dict(template_data)
                    saved_id = self.save_template(
                        template_name=template.template_name,
                        entity_type=template.entity_type,
                        template_content=template.template_content,
                        is_default=template.is_default
                    )
                    if saved_id is None:
                        result['errors'].append(f"Could not save template '{template.template_name}'")
                        continue
                    result['imported'] += 1

                except Exception as e:
                    result['errors'].append(f"Error importing template: {e}")

            result['success'] = True

        except Exception as e:
            result['errors'].append(f"Error importing templates: {e}")

        return result

    def export_templates(self, entity_type: Optional[str] = None,
                        file_path: str = None) -> Dict[str, Any]:
        """Export templates to a file."""
        result = {
            'success': False,
            'exported': 0,
            'file_path': file_path
        }

        try:
            templates = self.get_templates(entity_type)

            if not templates:
                result['errors'] = ["No templates to export"]
                return result

            # Convert to exportable format
            export_data = []
            for template in templates:
                export_data.append(template.to_dict())

            # Default file path if not provided
            if file_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                file_path = f"templates_export_{timestamp}.json"

            # Export to JSON
            import json
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)

            result['success'] = True
            result['exported'] = len(templates)
            result['file_path'] = file_path

        except Exception as e:
            result['errors'] = [f"Error exporting templates: {e}"]

        return result
