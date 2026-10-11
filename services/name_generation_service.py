"""
Name Generation Service for RPG Database Manager.

Provides embedded name lists for offline name generation.
"""

import random
from typing import List
from utils.logger import get_logger


class NameGenerationService:
    """Service for generating character/entity names using various methods."""

    def __init__(self):
        self.logger = get_logger('name_generation_service')

        # Embedded name lists for all supported styles
        self.embedded_names = {
            'fantasy': {
                'male': ['Theron Brightblade', 'Gareth Ironheart', 'Aldric Stormwind',
                        'Dorian Shadowmane', 'Cedric Flameheart', 'Marcus Steelborn',
                        'Roland Swiftblade', 'Tristan Nightshade', 'Benedict Starfall',
                        'Lucian Darkwood'],
                'female': ['Elara Moonwhisper', 'Lyanna Starfire', 'Seraphina Dawnbringer',
                          'Isolde Frostwind', 'Morgana Nightbloom', 'Aria Silverleaf',
                          'Rowena Sunshadow', 'Celestia Stormborn', 'Freya Emberlight',
                          'Astrid Crystalvale']
            },
            'english': {
                'male': ['James Smith', 'William Turner', 'Thomas Baker', 'George Carter',
                        'Henry Walker', 'Edward Miller', 'Charles Cooper', 'Robert Ward',
                        'John Fletcher', 'Richard Mason'],
                'female': ['Elizabeth Johnson', 'Margaret Brown', 'Sarah Williams', 'Anne Davis',
                          'Mary Wilson', 'Catherine Moore', 'Emma Taylor', 'Jane Anderson',
                          'Alice Thompson', 'Hannah White']
            },
            'hungarian': {
                'male': ['Kovács János', 'Nagy Péter', 'Szabó László', 'Tóth István',
                        'Horváth Gábor', 'Varga András', 'Kiss Zoltán', 'Molnár Attila',
                        'Németh Balázs', 'Farkas Tamás'],
                'female': ['Nagy Katalin', 'Kovács Anna', 'Szabó Erzsébet', 'Tóth Mária',
                          'Horváth Éva', 'Varga Judit', 'Kiss Eszter', 'Molnár Zsófia',
                          'Németh Réka', 'Farkas Petra']
            },
            'nordic': {
                'male': ['Bjorn Ironside', 'Erik Bloodaxe', 'Ragnar Lothbrok', 'Thorin Oakenshield',
                        'Leif Erikson', 'Ivar Boneless', 'Sigurd Serpent-Eye', 'Harald Fairhair',
                        'Olaf Tryggvason', 'Magnus Barefoot'],
                'female': ['Freya Stormborn', 'Astrid Shieldmaiden', 'Sigrid Winterborn',
                          'Brynhild Frostmane', 'Gunnhild Ravenhair', 'Hilde Battleborn',
                          'Thyra Fireheart', 'Ingrid Snowfell', 'Ragna Ironwill',
                          'Yrsa Stormblade']
            },
            'celtic': {
                'male': ['Caelen Mac Brennan', 'Finn O\'Connor', 'Declan Mac Faelan',
                        'Ronan O\'Neill', 'Kieran Mac Loughlin', 'Cormac O\'Brien',
                        'Aidan Mac Carthy', 'Eamon O\'Sullivan', 'Liam Mac Dermott',
                        'Seamus O\'Reilly'],
                'female': ['Rhiannon ni Faelan', 'Brigid O\'Connor', 'Maeve Mac Brennan',
                          'Aisling ni Neill', 'Siobhan O\'Brien', 'Niamh Mac Carthy',
                          'Grainne O\'Sullivan', 'Fiona Mac Loughlin', 'Ciara ni Reilly',
                          'Deirdre O\'Donnell']
            },
            'asian': {
                'male': ['Li Wei', 'Takeshi Yamamoto', 'Chen Ming', 'Kenji Tanaka',
                        'Zhang Yong', 'Hiroshi Nakamura', 'Wang Lei', 'Satoshi Kobayashi',
                        'Liu Feng', 'Masato Suzuki'],
                'female': ['Kim Sun-Hi', 'Mei Chen', 'Yuki Tanaka', 'Lin Xiao',
                          'Sakura Watanabe', 'Park Min-Ji', 'Hua Wang', 'Ayumi Nakamura',
                          'Lee Ji-Woo', 'Yui Kobayashi']
            },
            'german': {
                'male': ['Max Müller', 'Heinrich von Brandenburg', 'Felix Weber',
                        'Klaus Zimmermann', 'Hans Schmidt', 'Friedrich Krüger',
                        'Wolfgang von Hohenzollern', 'Ludwig Becker', 'Karl Eisenhauer',
                        'Otto Fischer'],
                'female': ['Anna Schmidt', 'Gisela von Hohenstaufen', 'Sophie Fischer',
                          'Margarete Zimmermann', 'Helga Müller', 'Ingrid Wagner',
                          'Brunhilde von Schwaben', 'Liesel Becker', 'Gertrud Hoffmann',
                          'Edeltraud Schneider']
            }
        }

    def generate_names(self, style: str, gender: str = 'any', count: int = 10) -> List[str]:
        """
        Generate names from embedded name lists.

        Args:
            style: Name style ('fantasy', 'english', 'hungarian', 'nordic', 'celtic', 'asian')
            gender: Gender filter ('any', 'male', 'female')
            count: Number of names to generate

        Returns:
            List of generated names
        """
        # Get appropriate name list
        style_names = self.embedded_names.get(style, self.embedded_names['fantasy'])

        if gender == 'any':
            # Combine male and female names
            all_names = style_names.get('male', []) + style_names.get('female', [])
        else:
            all_names = style_names.get(gender, style_names.get('male', []))

        if not all_names:
            # Ultimate fallback
            all_names = ['Character Name', 'Hero Name', 'Adventurer Name']

        # Generate requested count with random selection
        if count <= len(all_names):
            # Random sample without replacement
            names_list = random.sample(all_names, count)
        else:
            # If requesting more names than available, use all names and add variations
            names_list = all_names.copy()
            remaining = count - len(all_names)
            for i in range(remaining):
                base_name = random.choice(all_names)
                variation_num = (i % 99) + 1  # Cycle through 1-99
                names_list.append(f"{base_name} {variation_num}")

        return names_list
