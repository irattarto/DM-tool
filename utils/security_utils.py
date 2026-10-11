"""
Security utilities for RPG Database Manager.
"""

import json
import re
from typing import Dict, Any
from utils.logger import get_logger


class SecurityValidator:
    """
    Security validator for various inputs and operations.
    """

    def __init__(self):
        self.logger = get_logger('security_validator')

    def validate_json_input(self, json_str: str, max_size: int = 1048576) -> Dict[str, Any]:
        """
        Validate JSON input for security.

        Args:
            json_str: JSON string to validate
            max_size: Maximum allowed size in bytes

        Returns:
            Dict with validation results
        """
        issues = []
        warnings = []

        if not json_str or not json_str.strip():
            issues.append("JSON input is empty")
            return {'valid': False, 'issues': issues, 'warnings': warnings}

        # Check size
        if len(json_str.encode('utf-8')) > max_size:
            issues.append(f"JSON input too large (max {max_size} bytes)")

        # Check for suspicious patterns
        suspicious_patterns = [
            r'<script',  # Script tags
            r'javascript:',  # JavaScript URLs
            r'\bon\w+\s*=',  # Event handlers
        ]

        for pattern in suspicious_patterns:
            if re.search(pattern, json_str, re.IGNORECASE):
                issues.append("JSON contains suspicious patterns")

        # The text must actually be JSON; nesting depth is measured on the parsed value
        try:
            parsed = json.loads(json_str)
        except (ValueError, RecursionError):
            issues.append("JSON input is not valid JSON")
            return {'valid': False, 'issues': issues, 'warnings': warnings}

        def depth(value, level=1):
            if isinstance(value, dict):
                return max([depth(v, level + 1) for v in value.values()] or [level])
            if isinstance(value, list):
                return max([depth(v, level + 1) for v in value] or [level])
            return level

        max_nesting = depth(parsed)
        if max_nesting > 10:
            warnings.append("JSON has deep nesting structure")

        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'warnings': warnings,
            'size': len(json_str.encode('utf-8')),
            'max_nesting': max_nesting
        }

    def validate_text_content(self, content: str, max_length: int = 1000000) -> Dict[str, Any]:
        """
        Validate text content for security.

        Args:
            content: Text content to validate
            max_length: Maximum allowed length

        Returns:
            Dict with validation results
        """
        issues = []
        warnings = []

        if content is None:
            issues.append("Content is None")
            return {'valid': False, 'issues': issues, 'warnings': warnings}

        # Check length
        if len(content) > max_length:
            issues.append(f"Content too long (max {max_length} characters)")

        # Check for null bytes (potential injection)
        if '\x00' in content:
            issues.append("Content contains null bytes")

        # Check for suspicious Unicode characters
        suspicious_unicode = []
        for char in content:
            code = ord(char)
            # Control characters except common whitespace
            if code < 32 and char not in '\t\n\r':
                suspicious_unicode.append(f"U+{code:04X}")

        if suspicious_unicode:
            issues.append(f"Content contains suspicious control characters: {', '.join(suspicious_unicode[:5])}")

        # Check for script injection patterns
        # Note: These patterns are designed to catch actual HTML/JS injection attempts
        # while minimizing false positives from legitimate content
        script_patterns = [
            r'<script[^>]*>',  # Script tag opening (don't need closing tag)
            r'javascript\s*:',  # JavaScript URLs (with whitespace handling)
            r'<[^>]+\s+on\w+\s*=',  # Event handlers in HTML tags (must be inside < >)
            r'<iframe[^>]*>',  # Iframe tags
            r'<object[^>]*>',  # Object tags
            r'<embed[^>]*>',  # Embed tags
        ]

        for pattern in script_patterns:
            if re.search(pattern, content, re.IGNORECASE | re.DOTALL):
                issues.append("Content contains script injection patterns")

        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'warnings': warnings,
            'length': len(content)
        }


# Global instance
_security_validator = None


def get_security_validator() -> SecurityValidator:
    """Get global security validator instance."""
    global _security_validator
    if _security_validator is None:
        _security_validator = SecurityValidator()
    return _security_validator

