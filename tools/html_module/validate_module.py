"""Check an HTML adventure module against the importer's expectations.

    python tools/html_module/validate_module.py path/to/Module.html

Prints what the importer will find and lists problems a module author can fix:
unknown cross-reference targets, NPCs without a faction, pictures that do not
exist, entities without content. Exit code 1 when there are errors.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.html_module_parser import parse_file  # noqa: E402

_IMAGE_DIRS = ('portraits', 'rooms', 'items', 'creatures')
_IMAGE_EXTS = ('.jpg', '.jpeg', '.png', '.webp')


def _is_entity_id(ref: str) -> bool:
    """Links to section anchors (#karavan) are fine; only entity-style ids must exist."""
    return ref.split('-')[0] in ('c', 'g', 'm', 'f', 'l', 'h', 'j', 'item', 'gift', 'pw', 'hook') and '-' in ref


def validate(path) -> tuple:
    """Return (errors, warnings, summary_lines) for one module file."""
    path = Path(path)
    module = parse_file(path)
    folder = path.parent
    errors, warnings = [], list(module.warnings)

    ids = {e.source_id for e in module.entities} | {s.source_id for s in module.sessions}
    for entity in module.entities:
        for ref in entity.refs:
            if _is_entity_id(ref) and ref not in ids:
                errors.append(f'{entity.source_id}: links to unknown id #{ref}')
        if not entity.content.strip():
            warnings.append(f'{entity.source_id}: no body text')
        if entity.entity_type == 'npc':
            if not entity.faction_line:
                warnings.append(f'{entity.source_id}: no faction line (add <div class="npc-faction" '
                                f'data-faction="f-...|none|unknown|undecided">)')
            elif entity.faction_ref and entity.faction_ref not in ids:
                errors.append(f'{entity.source_id}: data-faction points to unknown faction {entity.faction_ref}')
            if not entity.count and re.search(r'\s(és|and)\s', entity.title):
                warnings.append(f'{entity.source_id}: looks like several people on one card '
                                f'(one card per NPC, or data-count for generic extras)')
        for src in [entity.image] + entity.extra_images:
            if src and not src.startswith(('http://', 'https://', 'data:')) and not (folder / src).is_file():
                errors.append(f'{entity.source_id}: picture not found: {src}')
        if entity.entity_type in ('npc', 'location') and not entity.image and not any(
                (folder / 'images' / d / f'{entity.source_id}{x}').is_file()
                for d in _IMAGE_DIRS for x in _IMAGE_EXTS):
            warnings.append(f'{entity.source_id}: no picture (optional)')
    for scene in module.sessions:
        for ref in scene.refs:
            if _is_entity_id(ref) and ref not in ids:
                errors.append(f'{scene.source_id}: links to unknown id #{ref}')

    summary = [f'{module.title} [{module.rule_system or "?"}] parsed from {module.parser}',
               f'  scenes: {len(module.sessions)}  entities: {len(module.entities)}']
    return errors, warnings, summary


def main(argv) -> int:
    if len(argv) != 1:
        print(__doc__)
        return 2
    errors, warnings, summary = validate(argv[0])
    print('\n'.join(summary))
    for message in warnings:
        print(f'  warning: {message}')
    for message in errors:
        print(f'  ERROR: {message}')
    print(f'{len(errors)} error(s), {len(warnings)} warning(s)')
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
