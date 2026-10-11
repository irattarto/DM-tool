"""
Text parsing service for RPG Database Manager.
"""

import re
from config.entity_types import get_registry
from typing import Dict, List, Any
from dataclasses import dataclass

from utils.logger import get_logger


@dataclass
class ParsedField:
    """Represents a parsed field from text content."""
    field_name: str
    value: str
    confidence: float
    line_number: int
    context: str = ""


@dataclass
class EntityReference:
    """Represents a reference to another entity in the text."""
    entity_name: str
    entity_type: str
    confidence: float
    context: str = ""


@dataclass
class ParsedDocument:
    """Result of parsing a document."""
    fields: List[ParsedField]
    entities: List[EntityReference]
    relationships: List[Dict[str, Any]]
    metadata: Dict[str, Any]


class ParsingService:
    """
    Service for parsing text content and extracting structured information.

    Handles extraction of fields, entities, relationships, and other
    structured data from RPG documents and session logs.
    """

    def __init__(self):
        self.logger = get_logger('parsing_service')

        # Common field patterns for different entity types (compiled for performance)
        self.field_patterns = {
            'name': [
                re.compile(r'^Name:\s*(.+)$', re.MULTILINE),
                re.compile(r'^Character Name:\s*(.+)$', re.MULTILINE),
                re.compile(r'^NPC:\s*(.+)$', re.MULTILINE),
                re.compile(r'^Title:\s*(.+)$', re.MULTILINE),
            ],
            'age': [
                re.compile(r'^Age:\s*(\d+)', re.MULTILINE),
                re.compile(r'^Born:\s*(\d+)', re.MULTILINE),
            ],
            'location': [
                re.compile(r'^Location:\s*(.+)$', re.MULTILINE),
                re.compile(r'^Home:\s*(.+)$', re.MULTILINE),
                re.compile(r'^Headquarters:\s*(.+)$', re.MULTILINE),
                re.compile(r'^Origin:\s*(.+)$', re.MULTILINE),
            ],
            'faction': [
                re.compile(r'^Faction:\s*(.+)$', re.MULTILINE),
                re.compile(r'^Guild:\s*(.+)$', re.MULTILINE),
                re.compile(r'^Clan:\s*(.+)$', re.MULTILINE),
                re.compile(r'^Organization:\s*(.+)$', re.MULTILINE),
                re.compile(r'^Affiliation:\s*(.+)$', re.MULTILINE),
            ],
            'status': [
                re.compile(r'^Status:\s*(.+)$', re.MULTILINE),
                re.compile(r'^Quest Status:\s*(.+)$', re.MULTILINE),
                re.compile(r'^Progress:\s*(.+)$', re.MULTILINE),
            ],
            'level': [
                re.compile(r'^Level:\s*(\d+)', re.MULTILINE),
                re.compile(r'^Character Level:\s*(\d+)', re.MULTILINE),
            ],
            'class': [
                re.compile(r'^Class:\s*(.+)$', re.MULTILINE),
                re.compile(r'^Occupation:\s*(.+)$', re.MULTILINE),
                re.compile(r'^Role:\s*(.+)$', re.MULTILINE),
                re.compile(r'^Profession:\s*(.+)$', re.MULTILINE),
            ],
            'race': [
                re.compile(r'^Race:\s*(.+)$', re.MULTILINE),
                re.compile(r'^Species:\s*(.+)$', re.MULTILINE),
            ],
        }

        # Entity type indicators
        self.entity_indicators = get_registry().keyword_map()

        # Relationship patterns (compiled for performance)
        self.relationship_patterns = [
            (re.compile(r'ally of ([^\n,]+)', re.IGNORECASE), 'ally'),
            (re.compile(r'allied with ([^\n,]+)', re.IGNORECASE), 'ally'),
            (re.compile(r'enemy of ([^\n,]+)', re.IGNORECASE), 'enemy'),
            (re.compile(r'opposed by ([^\n,]+)', re.IGNORECASE), 'enemy'),
            (re.compile(r'friend of ([^\n,]+)', re.IGNORECASE), 'friend'),
            (re.compile(r'family of ([^\n,]+)', re.IGNORECASE), 'family'),
            (re.compile(r'parent of ([^\n,]+)', re.IGNORECASE), 'parent'),
            (re.compile(r'child of ([^\n,]+)', re.IGNORECASE), 'child'),
            (re.compile(r'employer of ([^\n,]+)', re.IGNORECASE), 'employer'),
            (re.compile(r'employed by ([^\n,]+)', re.IGNORECASE), 'employee'),
            (re.compile(r'member of ([^\n,]+)', re.IGNORECASE), 'member'),
            (re.compile(r'leader of ([^\n,]+)', re.IGNORECASE), 'leader'),
            (re.compile(r'follower of ([^\n,]+)', re.IGNORECASE), 'follower'),
            (re.compile(r'servant of ([^\n,]+)', re.IGNORECASE), 'servant'),
            (re.compile(r'master of ([^\n,]+)', re.IGNORECASE), 'master'),
        ]

    def _parse_with_patterns(self, session_content: str) -> Dict[str, Any]:
        """Pattern-based parsing of session content."""
        # Extract quest progress
        quest_updates = self._extract_quest_updates(session_content)

        # Extract NPC interactions
        npc_interactions = self._extract_npc_interactions(session_content)

        # Extract location visits
        location_visits = self._extract_location_visits(session_content)

        # Extract significant events
        significant_events = self._extract_significant_events(session_content)

        return {
            'quest_updates': quest_updates,
            'npc_interactions': npc_interactions,
            'location_visits': location_visits,
            'significant_events': significant_events,
            'entity_mentions': self._extract_all_entity_mentions(session_content),
        }

    def _extract_quest_updates(self, content: str) -> List[Dict[str, Any]]:
        """Extract quest progress updates from session content."""
        updates = []

        # Quest completion patterns
        completion_patterns = [
            r'completed? (?:the )?quest ["\']?([^"\']+)["\']?',
            r'finished ["\']?([^"\']+)["\']? quest',
            r'accomplished ["\']?([^"\']+)["\']?',
        ]

        for pattern in completion_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                updates.append({
                    'quest_name': match.strip(),
                    'status': 'completed',
                    'confidence': 0.9
                })

        # Quest started patterns
        start_patterns = [
            r'started? (?:the )?quest ["\']?([^"\']+)["\']?',
            r'began ["\']?([^"\']+)["\']? quest',
            r'accepted ["\']?([^"\']+)["\']? quest',
        ]

        for pattern in start_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                updates.append({
                    'quest_name': match.strip(),
                    'status': 'started',
                    'confidence': 0.8
                })

        return updates

    def _extract_npc_interactions(self, content: str) -> List[Dict[str, Any]]:
        """Extract NPC interactions from session content."""
        interactions = []

        # NPC interaction patterns
        interaction_indicators = [
            'spoke with', 'talked to', 'met with', 'encountered', 'negotiated with',
            'fought against', 'battled', 'defeated', 'killed', 'saved', 'helped'
        ]

        # Find sentences containing these indicators
        sentences = re.split(r'[.!?]+', content)

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            lowered = sentence.lower()
            for indicator in interaction_indicators:
                # whole-word match; multi-word indicators ("spoke with") are matched as a phrase
                match = re.search(r'\b' + re.escape(indicator) + r'\b', lowered)
                if match:
                    # the NPC name is the proper noun right after the indicator phrase
                    following = sentence[match.end():].split()
                    if following and following[0].istitle() and len(following[0]) > 2:
                        interactions.append({
                            'npc_name': following[0].strip('",;:'),
                            'interaction_type': indicator,
                            'context': sentence,
                            'confidence': 0.7
                        })

        return interactions

    def _extract_location_visits(self, content: str) -> List[Dict[str, Any]]:
        """Extract location visits from session content."""
        visits = []

        # Location visit patterns
        visit_indicators = [
            'arrived at', 'entered', 'visited', 'explored', 'discovered',
            'traveled to', 'reached', 'found'
        ]

        sentences = re.split(r'[.!?]+', content)

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            for indicator in visit_indicators:
                if indicator in sentence.lower():
                    # Look for location names (proper nouns or quoted)
                    words = sentence.split()
                    for word in words:
                        if (word.istitle() and len(word) > 2) or word.startswith('"'):
                            visits.append({
                                'location_name': word.strip('"'),
                                'visit_type': indicator,
                                'context': sentence,
                                'confidence': 0.6
                            })

        return visits

    def _extract_significant_events(self, content: str) -> List[Dict[str, Any]]:
        """Extract significant events from session content."""
        events = []

        # Significant event patterns
        event_indicators = [
            'discovered', 'found', 'revealed', 'learned', 'realized',
            'defeated', 'killed', 'destroyed', 'created', 'built',
            'alliance', 'treaty', 'war', 'battle', 'victory', 'defeat'
        ]

        sentences = re.split(r'[.!?]+', content)

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # Check if sentence contains significant indicators
            has_significant_indicator = any(
                indicator in sentence.lower() for indicator in event_indicators
            )

            if has_significant_indicator and len(sentence) > 20:
                events.append({
                    'description': sentence,
                    'significance': 'medium',  # Could be enhanced with more analysis
                    'confidence': 0.6
                })

        return events

    def _extract_all_entity_mentions(self, content: str) -> Dict[str, List[str]]:
        """Extract all entity mentions from content."""
        mentions = {entity_type: [] for entity_type in self.entity_indicators.keys()}

        for entity_type, indicators in self.entity_indicators.items():
            for indicator in indicators:
                # Find sentences containing the indicator
                sentences = re.split(r'[.!?]+', content)
                for sentence in sentences:
                    if indicator in sentence.lower():
                        # Extract potential entity names from this sentence
                        words = sentence.split()
                        for word in words:
                            if (word.istitle() and len(word) > 2 and
                                word.lower() not in indicators):
                                if word not in mentions[entity_type]:
                                    mentions[entity_type].append(word)

        return mentions
