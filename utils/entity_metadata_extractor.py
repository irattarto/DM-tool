"""
Utility for extracting metadata from entity content.
"""

import re
from typing import Dict, Optional


def extract_npc_metadata(content: str) -> Dict[str, Optional[str]]:
    """
    Extract faction and race from NPC content.

    Args:
        content: The NPC document content

    Returns:
        Dictionary with 'faction' and 'race' keys
    """
    metadata = {
        'faction': None,
        'race': None
    }

    if not content:
        return metadata

    # Common patterns for Race
    race_patterns = [
        r'Race:\s*([^\n,;]+)',
        r'Species:\s*([^\n,;]+)',
        r'race:\s*([^\n,;]+)',
        r'species:\s*([^\n,;]+)',
        r'\*\*Race\*\*:\s*([^\n,;]+)',
        r'\*\*Species\*\*:\s*([^\n,;]+)',
        # Pattern for "a [race] [class/role]"
        r'(?:is\s+)?(?:a|an)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:warrior|mage|wizard|rogue|cleric|fighter|ranger|paladin|druid|barbarian|monk|sorcerer|warlock|bard|merchant|noble|peasant|scholar|priest)',
    ]

    # Common patterns for Faction
    faction_patterns = [
        r'Faction:\s*([^\n,;]+)',
        r'Allegiance:\s*([^\n,;]+)',
        r'Organization:\s*([^\n,;]+)',
        r'Group:\s*([^\n,;]+)',
        r'faction:\s*([^\n,;]+)',
        r'allegiance:\s*([^\n,;]+)',
        r'\*\*Faction\*\*:\s*([^\n,;]+)',
        r'\*\*Allegiance\*\*:\s*([^\n,;]+)',
        r'\*\*Organization\*\*:\s*([^\n,;]+)',
        # Pattern for "member of [faction]"
        r'member\s+of\s+(?:the\s+)?([A-Z][^\n,;.]+?)(?:\.|,|\n|;)',
        r'belongs\s+to\s+(?:the\s+)?([A-Z][^\n,;.]+?)(?:\.|,|\n|;)',
        r'serves\s+(?:the\s+)?([A-Z][^\n,;.]+?)(?:\.|,|\n|;)',
    ]

    # Try to extract race
    for pattern in race_patterns:
        match = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)
        if match:
            race = match.group(1).strip()
            # Clean up markdown formatting
            race = re.sub(r'\*\*|\*|__|_', '', race)
            # Limit length
            if len(race) < 50:  # Reasonable length for a race name
                metadata['race'] = race
                break

    # Try to extract faction
    for pattern in faction_patterns:
        match = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)
        if match:
            faction = match.group(1).strip()
            # Clean up markdown formatting
            faction = re.sub(r'\*\*|\*|__|_', '', faction)
            # Limit length
            if len(faction) < 100:  # Reasonable length for a faction name
                metadata['faction'] = faction
                break

    return metadata


def extract_faction_metadata(content: str) -> Dict[str, Optional[str]]:
    """
    Extract race and other metadata from Faction content.

    Args:
        content: The Faction document content

    Returns:
        Dictionary with 'race' key
    """
    metadata = {
        'race': None
    }

    if not content:
        return metadata

    # Common patterns for Race in factions
    race_patterns = [
        r'Race:\s*([^\n,;]+)',
        r'Primary Race:\s*([^\n,;]+)',
        r'Dominant Race:\s*([^\n,;]+)',
        r'Species:\s*([^\n,;]+)',
        r'Primarily:\s*([^\n,;]+)',
        r'Composed of:\s*([^\n,;]+)',
        r'Majority:\s*([^\n,;]+)',
        r'Racial Affiliation:\s*([^\n,;]+)',
        r'race:\s*([^\n,;]+)',
        r'primary race:\s*([^\n,;]+)',
        r'dominant race:\s*([^\n,;]+)',
        r'\*\*Race\*\*:\s*([^\n,;]+)',
        r'\*\*Primary Race\*\*:\s*([^\n,;]+)',
        r'\*\*Dominant Race\*\*:\s*([^\n,;]+)',
        r'\*\*Species\*\*:\s*([^\n,;]+)',
        # Pattern for "an [adjective] [race] faction/guild/order"
        r'(?:a|an)\s+(?:\w+\s+)?([A-Z][a-z]+)\s+(?:faction|guild|order|clan|organization)',
    ]

    # Try to extract race
    for pattern in race_patterns:
        match = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)
        if match:
            race = match.group(1).strip()
            # Clean up markdown formatting
            race = re.sub(r'\*\*|\*|__|_', '', race)
            # Limit length
            if len(race) < 50:  # Reasonable length for a race name
                metadata['race'] = race
                break

    return metadata


def format_date(date_value) -> str:
    """
    Format a date value for display.

    Args:
        date_value: Date string or datetime object

    Returns:
        Formatted date string
    """
    if not date_value:
        return ""

    # If it's already a string, just format it
    if isinstance(date_value, str):
        # Try to parse and reformat
        try:
            from datetime import datetime
            # Try various formats
            for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d']:
                try:
                    dt = datetime.strptime(date_value, fmt)
                    return dt.strftime('%Y-%m-%d %H:%M')
                except ValueError:
                    continue
            # If no format works, return as-is
            return date_value
        except Exception:
            return date_value

    # If it's a datetime object
    try:
        return date_value.strftime('%Y-%m-%d %H:%M')
    except Exception:
        return str(date_value)
