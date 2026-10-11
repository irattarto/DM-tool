"""
Text processing utilities for RPG Database Manager.
"""

import os
import ntpath
import re
import unicodedata
from typing import List, Dict, Any, Optional
from collections import Counter


class TextUtils:
    """
    Utility class for text processing and analysis.

    Provides common text processing functions used throughout
    the RPG Database Manager application.
    """

    @staticmethod
    def clean_text(text: str) -> str:
        """Clean and normalize text content."""
        if not text:
            return ""

        # Normalize unicode characters
        text = unicodedata.normalize('NFKD', text)

        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text.strip())

        return text

    @staticmethod
    def extract_words(text: str, min_length: int = 3) -> List[str]:
        """Extract words from text."""
        if not text:
            return []

        # Find all words (sequences of alphanumeric characters)
        words = re.findall(r'\b\w+\b', text.lower())

        # Filter by minimum length
        words = [word for word in words if len(word) >= min_length]

        return words

    @staticmethod
    def calculate_word_frequency(text: str) -> Dict[str, int]:
        """Calculate word frequency in text."""
        words = TextUtils.extract_words(text)
        return dict(Counter(words))

    @staticmethod
    def find_similar_words(word: str, word_list: List[str], threshold: float = 0.8) -> List[str]:
        """Find similar words using simple string similarity."""
        similar = []

        for other_word in word_list:
            similarity = TextUtils._calculate_similarity(word.lower(), other_word.lower())
            if similarity >= threshold:
                similar.append(other_word)

        return similar

    @staticmethod
    def _calculate_similarity(str1: str, str2: str) -> float:
        """Calculate simple string similarity."""
        if str1 == str2:
            return 1.0

        # Calculate Jaccard similarity for character overlap
        if not str1 or not str2:
            return 0.0

        # Create character sets
        set1 = set(str1)
        set2 = set(str2)

        intersection = set1.intersection(set2)
        union = set1.union(set2)

        return len(intersection) / len(union) if union else 0.0

    @staticmethod
    def extract_sentences(text: str) -> List[str]:
        """Extract sentences from text."""
        if not text:
            return []

        # Split on sentence endings
        sentences = re.split(r'[.!?]+', text)

        # Clean and filter sentences
        sentences = [sentence.strip() for sentence in sentences if sentence.strip()]

        return sentences

    @staticmethod
    def extract_paragraphs(text: str) -> List[str]:
        """Extract paragraphs from text."""
        if not text:
            return []

        # Split on double newlines or paragraph breaks
        paragraphs = re.split(r'\n\s*\n', text)

        # Clean paragraphs
        paragraphs = [paragraph.strip() for paragraph in paragraphs if paragraph.strip()]

        return paragraphs

    @staticmethod
    def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
        """Truncate text to maximum length."""
        if not text or len(text) <= max_length:
            return text

        return text[:max_length - len(suffix)] + suffix

    @staticmethod
    def format_text_for_display(text: str, max_line_length: int = 80) -> str:
        """Format text for display with line wrapping."""
        if not text:
            return ""

        words = text.split()
        lines = []
        current_line = ""

        for word in words:
            # Check if adding this word would exceed line length
            if len(current_line) + len(word) + 1 <= max_line_length:
                if current_line:
                    current_line += " "
                current_line += word
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word

        # Add remaining text
        if current_line:
            lines.append(current_line)

        return "\n".join(lines)

    @staticmethod
    def remove_html_tags(text: str) -> str:
        """Remove HTML tags from text."""
        if not text:
            return ""

        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)

        # Decode HTML entities (decode &amp; last to avoid double-decoding)
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&quot;', '"')
        text = text.replace("&apos;", "'")
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&amp;', '&')  # Must be last!

        return text

    @staticmethod
    def html_to_markdown(html_content: str) -> str:
        """
        Convert HTML content to Markdown format.
        Preserves formatting (bold, italic, lists) without raw HTML tags.

        Args:
            html_content: HTML string to convert

        Returns:
            Markdown formatted string, or plain text if conversion fails
        """
        if not html_content:
            return ""

        try:
            from PyQt6.QtWidgets import QTextEdit, QApplication

            # Need QApplication instance for QTextEdit
            app = QApplication.instance()
            if app is None:
                # Fallback to HTML stripping if no Qt app available
                return TextUtils.remove_html_tags(html_content)

            # Create temporary QTextEdit to use toMarkdown()
            temp_editor = QTextEdit()
            temp_editor.setHtml(html_content)
            markdown = temp_editor.toMarkdown()

            # Clean up
            temp_editor.deleteLater()

            return markdown.strip()

        except Exception:
            # Fallback to HTML stripping on any error
            return TextUtils.remove_html_tags(html_content)

    @staticmethod
    def extract_metadata_from_content(content: str) -> Dict[str, Any]:
        """Extract metadata information from document content."""
        metadata = {}

        try:
            lines = content.split('\n')

            for line in lines:
                line = line.strip()
                if ': ' in line:
                    parts = line.split(': ', 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip()

                        # Convert to appropriate types
                        if value.lower() in ['true', 'false']:
                            metadata[key] = value.lower() == 'true'
                        elif value.isdigit():
                            metadata[key] = int(value)
                        elif TextUtils._is_float(value):
                            metadata[key] = float(value)
                        else:
                            metadata[key] = value

        except Exception:
            pass

        return metadata

    @staticmethod
    def _is_float(value: str) -> bool:
        """Check if a string represents a float."""
        try:
            float(value)
            return True
        except ValueError:
            return False

    @staticmethod
    def count_text_statistics(text: str) -> Dict[str, Any]:
        """Count various text statistics."""
        if not text:
            return {
                'characters': 0,
                'words': 0,
                'sentences': 0,
                'paragraphs': 0,
                'lines': 0,
                'avg_words_per_sentence': 0,
                'avg_characters_per_word': 0
            }

        characters = len(text)
        words = len(TextUtils.extract_words(text))
        sentences = len(TextUtils.extract_sentences(text))
        paragraphs = len(TextUtils.extract_paragraphs(text))
        lines = len([line for line in text.split('\n') if line.strip()])

        avg_words_per_sentence = words / sentences if sentences > 0 else 0
        avg_characters_per_word = characters / words if words > 0 else 0

        return {
            'characters': characters,
            'words': words,
            'sentences': sentences,
            'paragraphs': paragraphs,
            'lines': lines,
            'avg_words_per_sentence': avg_words_per_sentence,
            'avg_characters_per_word': avg_characters_per_word
        }

    @staticmethod
    def validate_document_content(content: str) -> Dict[str, Any]:
        """Validate document content and return issues."""
        issues = []
        warnings = []

        if not content or not content.strip():
            issues.append("Document content is empty")
            return {'valid': False, 'issues': issues, 'warnings': warnings}

        # Check length
        if len(content.strip()) < 10:
            warnings.append("Document content is very short")

        if len(content) > 100000:  # 100KB limit
            warnings.append("Document content is very large")

        # Check for placeholder patterns
        placeholder_pattern = r'\[([^\]]+)\]'
        placeholders = re.findall(placeholder_pattern, content)

        if placeholders:
            warnings.append(f"Document contains {len(placeholders)} placeholder fields")

        # Check for common issues
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            if len(line) > 200:  # Very long lines
                warnings.append(f"Very long line ({len(line)} characters) at line {i}")

        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'warnings': warnings,
            'statistics': TextUtils.count_text_statistics(content)
        }

    @staticmethod
    def generate_text_preview(text: str, max_length: int = 200) -> str:
        """Generate a preview/summary of text content."""
        if not text:
            return ""

        # Clean the text
        clean_text = TextUtils.clean_text(text)

        # Truncate to max length
        if len(clean_text) <= max_length:
            return clean_text

        # Try to find a good break point
        preview = clean_text[:max_length]

        # Look for sentence or paragraph break
        for separator in ['. ', '\n\n', '\n', '.']:
            last_separator = preview.rfind(separator)
            if last_separator > max_length * 0.7:  # Don't break too early
                return preview[:last_separator + 1].strip() + "..."

        return preview + "..."

    @staticmethod
    def find_and_replace_placeholders(text: str, replacements: Dict[str, str]) -> str:
        """Find and replace placeholder patterns in text."""
        result = text

        for placeholder, replacement in replacements.items():
            pattern = f"[{placeholder}]"
            result = result.replace(pattern, replacement)

        return result

    @staticmethod
    def extract_quest_objectives(content: str) -> List[str]:
        """Extract quest objectives from content."""
        objectives = []

        # Look for numbered lists
        numbered_pattern = r'\d+\.\s*(.+?)(?=\n|\r|$)'
        numbered_matches = re.findall(numbered_pattern, content)

        for match in numbered_matches:
            objectives.append(match.strip())

        # Look for bullet points
        if not objectives:
            bullet_pattern = r'[•\-\*]\s*(.+?)(?=\n|\r|$)'
            bullet_matches = re.findall(bullet_pattern, content)

            for match in bullet_matches:
                objectives.append(match.strip())

        return objectives

    @staticmethod
    def extract_npc_traits(content: str) -> Dict[str, List[str]]:
        """Extract NPC traits and characteristics."""
        traits = {
            'personality': [],
            'appearance': [],
            'abilities': [],
            'background': []
        }

        content_lower = content.lower()

        # Personality traits
        personality_indicators = [
            'personality', 'traits', 'behavior', 'attitude', 'demeanor'
        ]

        for indicator in personality_indicators:
            if indicator in content_lower:
                # Find the section
                pattern = f'{indicator}[:\\s]*([^\\n]+)'
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    trait_text = match.group(1).strip()
                    traits['personality'].extend([t.strip() for t in trait_text.split(',')])

        # Appearance indicators
        appearance_indicators = [
            'appearance', 'looks', 'description', 'physical'
        ]

        for indicator in appearance_indicators:
            if indicator in content_lower:
                pattern = f'{indicator}[:\\s]*([^\\n]+)'
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    trait_text = match.group(1).strip()
                    traits['appearance'].extend([t.strip() for t in trait_text.split(',')])

        return traits

    @staticmethod
    def format_document_for_export(document_data: Dict[str, Any]) -> str:
        """Format document data for export."""
        lines = []

        # Header
        lines.append(f"Document: {document_data.get('title', 'Untitled')}")
        lines.append(f"Type: {document_data.get('entity_type', 'unknown').upper()}")
        lines.append(f"Created: {document_data.get('created_date', 'Unknown')}")
        lines.append(f"Status: {document_data.get('status', 'unknown')}")
        lines.append("")

        # Content
        content = document_data.get('content', '')
        if content:
            lines.append("Content:")
            lines.append("-" * 20)
            lines.append(content)
            lines.append("")

        # Metadata
        metadata = document_data.get('metadata', {})
        if metadata:
            lines.append("Metadata:")
            lines.append("-" * 20)
            for key, value in metadata.items():
                lines.append(f"{key}: {value}")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename for safe file operations."""
        if not filename:
            return "untitled"

        # Remove or replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        sanitized = filename

        for char in invalid_chars:
            sanitized = sanitized.replace(char, '_')

        # Remove multiple spaces and leading/trailing spaces
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()

        # Limit length
        if len(sanitized) > 100:
            sanitized = sanitized[:100].rstrip('_')

        return sanitized or "untitled"

    @staticmethod
    def validate_file_path(file_path: str, allowed_extensions: Optional[List[str]] = None,
                            allow_absolute: bool = False) -> Dict[str, Any]:
        """
        Validate file path for security and safety.

        Args:
            file_path: Path to validate
            allowed_extensions: List of allowed file extensions (e.g., ['.txt', '.json'])
            allow_absolute: Whether absolute paths are permitted (default False - untrusted
                input should stay relative; trusted callers with legitimately absolute paths
                should pass True)

        Returns:
            Dict with validation results
        """
        issues = []
        warnings = []

        if not file_path or not file_path.strip():
            issues.append("File path is empty")
            return {'valid': False, 'issues': issues, 'warnings': warnings}

        file_path = file_path.strip()

        # Check for path traversal attempts
        if '..' in file_path:
            issues.append("Path contains directory traversal (..)")

        if not allow_absolute and (os.path.isabs(file_path) or ntpath.isabs(file_path)):
            issues.append("Absolute paths not allowed")

        # Check for suspicious characters
        suspicious_chars = ['<', '>', '|', '"', '*', '?']
        for char in suspicious_chars:
            if char in file_path:
                issues.append(f"Path contains suspicious character: {char}")

        # Check file extension if specified
        if allowed_extensions:
            from pathlib import Path
            path_obj = Path(file_path)
            if path_obj.suffix.lower() not in [ext.lower() for ext in allowed_extensions]:
                issues.append(f"File extension not allowed. Allowed: {', '.join(allowed_extensions)}")

        # Check path length
        if len(file_path) > 260:  # Windows MAX_PATH
            warnings.append("File path is very long")

        # Check for hidden files
        path_parts = file_path.replace('\\', '/').split('/')
        for part in path_parts:
            if part.startswith('.'):
                warnings.append("Path contains hidden file/directory")

        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'warnings': warnings,
            'path': file_path
        }

    @staticmethod
    def validate_entity_name(name: str, max_length: int = 255) -> Dict[str, Any]:
        """
        Validate entity name for security and database safety.

        Args:
            name: Entity name to validate
            max_length: Maximum allowed length

        Returns:
            Dict with validation results
        """
        issues = []
        warnings = []

        if not name or not name.strip():
            issues.append("Entity name is empty")
            return {'valid': False, 'issues': issues, 'warnings': warnings}

        name = name.strip()

        # Check length
        if len(name) > max_length:
            issues.append(f"Entity name too long (max {max_length} characters)")

        # (No SQL pattern check: every query is parameterised, and text such as "Arrive; update the map"
        # is a legitimate title.)

        name_lower = name.lower()

        # Check for script injection
        # Note: More specific patterns to avoid false positives
        script_patterns = [
            r'<script',  # Script tags
            r'javascript\s*:',  # JavaScript URLs
            r'<[^>]+\s+on\w+\s*=',  # Event handlers in HTML tags
        ]

        for pattern in script_patterns:
            if re.search(pattern, name_lower, re.IGNORECASE):
                issues.append("Entity name contains script injection patterns")

        # Check for control characters
        for char in name:
            if ord(char) < 32 and char not in ['\t', '\n', '\r']:
                issues.append("Entity name contains control characters")

        # Check for excessive special characters
        special_chars = re.findall(r'[^a-zA-Z0-9\s\-_\.]', name)
        if len(special_chars) > len(name) * 0.3:  # More than 30% special chars
            warnings.append("Entity name contains many special characters")

        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'warnings': warnings,
            'name': name
        }

    @staticmethod
    def sanitize_entity_name(name: str, max_length: int = 255) -> str:
        """
        Sanitize entity name for safe storage.

        Args:
            name: Entity name to sanitize
            max_length: Maximum allowed length

        Returns:
            Sanitized entity name
        """
        if not name:
            return "unnamed_entity"

        # Remove control characters
        sanitized = ''.join(char for char in name if ord(char) >= 32 or char in ['\t', '\n', '\r'])

        # Remove suspicious patterns
        sanitized = re.sub(r'<[^>]*>', '', sanitized)  # Remove HTML tags
        sanitized = re.sub(r'javascript:', '', sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r'on\w+\s*=', '', sanitized, flags=re.IGNORECASE)

        # Remove excessive whitespace
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()

        # Limit length
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length].rstrip()

        return sanitized or "unnamed_entity"

    @staticmethod
    def create_search_index(text: str) -> Dict[str, List[int]]:
        """Create a simple search index for text."""
        index = {}
        words = TextUtils.extract_words(text)

        for position, word in enumerate(words):
            if word not in index:
                index[word] = []
            index[word].append(position)

        return index

    @staticmethod
    def search_in_text(text: str, query: str) -> List[int]:
        """Search for query in text and return word positions."""
        if not text or not query:
            return []

        query_words = TextUtils.extract_words(query)
        text_words = TextUtils.extract_words(text)

        if not query_words or not text_words:
            return []

        # Find positions where query words appear
        positions = []

        for i, word in enumerate(text_words):
            if word in query_words:
                positions.append(i)

        return positions

    @staticmethod
    def highlight_search_terms(text: str, search_terms: List[str]) -> str:
        """Highlight search terms in text."""
        if not text or not search_terms:
            return text

        highlighted = text

        for term in search_terms:
            # Case-insensitive replacement
            pattern = f"({re.escape(term)})"
            replacement = f"**{term}**"
            highlighted = re.sub(pattern, replacement, highlighted, flags=re.IGNORECASE)

        return highlighted

    @staticmethod
    def calculate_text_complexity(text: str) -> Dict[str, Any]:
        """Calculate text complexity metrics."""
        if not text:
            return {'complexity_score': 0, 'readability_level': 'unknown'}

        stats = TextUtils.count_text_statistics(text)

        # Simple complexity calculation
        avg_sentence_length = stats['avg_words_per_sentence']
        avg_word_length = stats['avg_characters_per_word']

        # Complexity score (0-100)
        complexity_score = min(100, (avg_sentence_length * avg_word_length) / 2)

        # Readability level
        if complexity_score < 30:
            readability_level = "easy"
        elif complexity_score < 60:
            readability_level = "medium"
        else:
            readability_level = "hard"

        return {
            'complexity_score': complexity_score,
            'readability_level': readability_level,
            'avg_sentence_length': avg_sentence_length,
            'avg_word_length': avg_word_length
        }