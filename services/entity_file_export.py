"""Export entries as an entity file (Markdown or JSON) that File > Import Entities reads again."""

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

from config.entity_types import get_registry
from config.paths import resolve_image_path
from services.entity_file_service import FORMAT_NAME, SUBTYPES, EntityEntry, ParsedEntityFile, _slug
from utils.natural_sort import natural_key

_RPG_LINK = re.compile(r'\[([^\]]*)\]\(rpg://([a-z0-9_]+)/(\d+)\)')
_IMAGE_EXTS = ('.jpg', '.jpeg', '.png', '.webp')


@dataclass
class ExportResult:
    path: Path
    entries: int = 0
    images: int = 0
    warnings: List[str] = field(default_factory=list)


def _meta(doc: dict) -> dict:
    try:
        value = json.loads(doc['metadata']) if doc.get('metadata') else {}
        return value if isinstance(value, dict) else {}
    except (TypeError, ValueError):
        return {}


def build_export(db, documents: List[dict], pack: str) -> ParsedEntityFile:
    """The entries of ``documents`` as an entity file: ids, properties, modules and links between them."""
    campaign_id = documents[0]['module_id'] if documents else None
    everything = {d['id']: d for d in db.get_documents(campaign_id)} if campaign_id is not None else {}
    links = db.get_module_links(campaign_id) if campaign_id is not None else {}
    parents = db.get_parent_links(campaign_id) if campaign_id is not None else {}
    ids: Dict[int, str] = {}
    used = set()
    for doc in documents:
        wanted = str(_meta(doc).get('source_id') or '') or f"{doc['entity_type']}-{doc['id']}"
        wanted = re.sub(r'[^\w.\-]+', '-', wanted)
        while wanted in used:
            wanted += f"-{doc['id']}"
        used.add(wanted)
        ids[doc['id']] = wanted

    def rewrite(match: re.Match) -> str:
        target = int(match.group(3))
        return f"[{match.group(1)}](#{ids[target]})" if target in ids else match.group(1)

    parsed = ParsedEntityFile(pack=_slug(pack), format='markdown')
    parsed.ids_by_document = ids
    for doc in sorted(documents, key=lambda d: (d['entity_type'], natural_key(d['title']))):
        meta = _meta(doc)
        entry = EntityEntry(kind=doc['entity_type'], title=doc['title'], source_id=ids[doc['id']],
                            body=_RPG_LINK.sub(rewrite, doc.get('content') or '').strip('\n'))
        faction = everything.get(meta.get('faction_id'))
        if faction is not None:
            entry.faction = faction['title']
        if doc['entity_type'] == 'location' and parents.get(doc['id']) in everything:
            entry.located_in = everything[parents[doc['id']]]['title']
        if meta.get('subtype') in SUBTYPES:
            entry.subtype = meta['subtype']
        entry.tags = [str(t) for t in meta.get('tags', []) if isinstance(t, (str, int))] if isinstance(meta.get('tags'), list) else []
        entry.modules = sorted((everything[m]['title'] for m in links.get(doc['id'], []) if m in everything), key=natural_key)
        if doc['entity_type'] == 'session':
            entry.session_date = str(meta.get('session_date') or '')[:10]
            entry.status = str(meta.get('status') or '')
            participants = meta.get('participants')
            entry.participants = [str(p) for p in participants] if isinstance(participants, list) else []
        parsed.entries.append(entry)
    return parsed


def to_markdown(parsed: ParsedEntityFile) -> str:
    registry = get_registry()
    lines = ["---", f"format: {FORMAT_NAME}", f"pack: {parsed.pack}", "---", ""]
    for entry in parsed.entries:
        lines.append(f"## {registry.label(entry.kind)}: {entry.title} {{#{entry.source_id}}}")
        if entry.subtype:
            lines.append(f"subtype: {entry.subtype}")
        if entry.faction:
            lines.append(f"faction: {entry.faction}")
        if entry.located_in:
            lines.append(f"located_in: {entry.located_in}")
        if entry.tags:
            lines.append(f"tags: {', '.join(entry.tags)}")
        if entry.image:
            lines.append(f"image: {entry.image}")
        if entry.modules:
            lines.append(f"modules: [{', '.join(entry.modules)}]")
        if entry.session_date:
            lines.append(f"date: {entry.session_date}")
        if entry.status:
            lines.append(f"status: {entry.status}")
        if entry.participants:
            lines.append(f"participants: {', '.join(entry.participants)}")
        lines.append("")
        if entry.body:
            lines.append(entry.body)
            lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def to_json(parsed: ParsedEntityFile) -> dict:
    registry = get_registry()
    entities = []
    for entry in parsed.entries:
        item = {"type": registry.label(entry.kind), "id": entry.source_id, "title": entry.title}
        if entry.subtype:
            item["subtype"] = entry.subtype
        if entry.faction:
            item["faction"] = entry.faction
        if entry.located_in:
            item["located_in"] = entry.located_in
        if entry.tags:
            item["tags"] = entry.tags
        if entry.image:
            item["image"] = entry.image
        if entry.modules:
            item["modules"] = entry.modules
        if entry.session_date:
            item["date"] = entry.session_date
        if entry.status:
            item["status"] = entry.status
        if entry.participants:
            item["participants"] = entry.participants
        item["content"] = entry.body
        entities.append(item)
    return {"format": FORMAT_NAME, "pack": parsed.pack, "entities": entities}


def export_documents(db, documents: List[dict], path, include_images: bool = True) -> ExportResult:
    """Write ``documents`` to ``path`` (.md or .json); primary pictures go to an ``images`` folder next to it."""
    path = Path(path)
    parsed = build_export(db, documents, path.stem)
    result = ExportResult(path=path, entries=len(parsed.entries))
    if include_images:
        entries = {e.source_id: e for e in parsed.entries}
        primaries = db.get_primary_images_for_documents([d['id'] for d in documents])
        for doc in documents:
            image = primaries.get(doc['id'])
            entry = entries.get(parsed.ids_by_document[doc['id']])
            source = resolve_image_path(image) if image else None
            if entry is None or not source or not Path(source).is_file() or Path(source).suffix.lower() not in _IMAGE_EXTS:
                continue
            target = path.parent / "images" / f"{entry.source_id}{Path(source).suffix.lower()}"
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
                entry.image = f"images/{target.name}"
                result.images += 1
            except OSError as e:
                result.warnings.append(f"Picture of '{doc['title']}' not copied: {e}")
    if path.suffix.lower() == '.json':
        path.write_text(json.dumps(to_json(parsed), ensure_ascii=False, indent=2), encoding='utf-8')
    else:
        path.write_text(to_markdown(parsed), encoding='utf-8')
    return result
