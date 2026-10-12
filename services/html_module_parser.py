"""
Parser for the single-file HTML adventure modules ("Temple Dungeons" format).

Two input paths produce the same ``ParsedModule``:

1. an embedded ``<script type="application/json" id="dm-module-data">`` block
   (``format: "dm-module"``), written by the generator's ``export-module.mjs``;
2. a heuristic parse of the markup. Entities are recognised by the id prefix of
   the element, which has been stable across every module so far:

   ====== ===================== ==============================================
   prefix entity type           markup
   ====== ===================== ==============================================
   c-     npc                   details.npc-card / vamp-card / ..., table row
   g-     npc (minor)           table row, name in the first cell
   m-     npc (monster)         details.creature-card
   f-     faction               div.card
   l-     location              details.room
   item-  item                  details.card / div.card
   gift-  item (subtype gift)   div.card
   pw-    item (subtype spell)  div.card
   h-     item (subtype handout) details.room
   hook-  character (hook)      div.hook-box (one per player character)
   j-     scene (importer: event) div.scene
   ====== ===================== ==============================================

The parser is stdlib only (``html.parser``) and never touches the database.
"""

import json
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, Optional, Set

FORMAT_NAME = "dm-module"
FORMAT_VERSION = 1

# id prefix -> (entity type, subtype)
PREFIX_MAP = {
    'c': ('npc', ''),
    'g': ('npc', 'minor'),
    'm': ('npc', 'monster'),
    'f': ('faction', ''),
    'l': ('location', ''),
    'item': ('item', ''),
    'gift': ('item', 'gift'),
    'pw': ('item', 'spell'),
    'h': ('item', 'handout'),
    'hook': ('character', 'hook'),     # "Karakterhorgok": one hook box per player character
}
SESSION_PREFIX = 'j'
_ID_RE = re.compile(r'^(c|g|m|f|l|item|gift|pw|h|hook|j)-[\w-]+$')

_VOID = frozenset({'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link',
                   'meta', 'param', 'source', 'track', 'wbr'})
_SKIP = frozenset({'script', 'style', 'svg', 'button', 'audio', 'img', 'noscript', 'head'})
_BLOCK = frozenset({'p', 'div', 'section', 'li', 'ul', 'ol', 'tr', 'table', 'h1', 'h2', 'h3',
                    'h4', 'h5', 'h6', 'details', 'summary', 'br', 'blockquote', 'header', 'footer'})
_MAX_SECTION_CHARS = 60000


# ---------------------------------------------------------------- DOM

class Node:
    __slots__ = ('tag', 'attrs', 'children', 'parent')

    def __init__(self, tag: str, attrs: Optional[Dict[str, Optional[str]]] = None, parent: 'Node' = None):
        self.tag = tag
        self.attrs = attrs or {}
        self.children: list = []
        self.parent = parent

    @property
    def id(self) -> str:
        return self.attrs.get('id') or ''

    def classes(self) -> List[str]:
        return (self.attrs.get('class') or '').split()

    def has_class(self, name: str) -> bool:
        return name in self.classes()

    def elements(self):
        return (c for c in self.children if isinstance(c, Node))

    def walk(self):
        """Depth-first iteration over this node and all descendant elements."""
        yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.walk()

    def find_all(self, tag: Optional[str] = None, cls: Optional[str] = None) -> List['Node']:
        return [n for n in self.walk() if n is not self
                and (tag is None or n.tag == tag) and (cls is None or n.has_class(cls))]

    def find(self, tag: Optional[str] = None, cls: Optional[str] = None) -> Optional['Node']:
        found = self.find_all(tag, cls)
        return found[0] if found else None

    def inside(self, tag: str) -> bool:
        node = self.parent
        while node is not None:
            if node.tag == tag:
                return True
            node = node.parent
        return False


class _TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node('#root')
        self._stack = [self.root]

    def _open(self, tag, attrs, push):
        node = Node(tag, dict(attrs), self._stack[-1])
        self._stack[-1].children.append(node)
        if push:
            self._stack.append(node)

    def handle_starttag(self, tag, attrs):
        self._open(tag, attrs, push=tag not in _VOID)

    def handle_startendtag(self, tag, attrs):
        self._open(tag, attrs, push=False)

    def handle_endtag(self, tag):
        for i in range(len(self._stack) - 1, 0, -1):
            if self._stack[i].tag == tag:
                del self._stack[i:]
                return

    def handle_data(self, data):
        self._stack[-1].children.append(data)


def parse_dom(html: str) -> Node:
    builder = _TreeBuilder()
    builder.feed(html)
    builder.close()
    return builder.root


# ---------------------------------------------------------------- text helpers

def _collapse(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip()


def text_of(node, skip_classes=('imgprompt', 'prompt-toggle')) -> str:
    """Plain text of a node with whitespace collapsed (block boundaries become spaces)."""
    parts: List[str] = []

    def rec(n):
        if isinstance(n, str):
            parts.append(n)
            return
        if n.tag in _SKIP or any(n.has_class(c) for c in skip_classes):
            return
        if n.tag in _BLOCK:
            parts.append(' ')
        for child in n.children:
            rec(child)
        if n.tag in _BLOCK:
            parts.append(' ')

    rec(node)
    return _collapse(''.join(parts))


def _svg_summary(svg: Node) -> str:
    """An inline SVG map becomes a text note: its base image and the locations it links to."""
    image = svg.find('image')
    base = (image.attrs.get('href') or image.attrs.get('xlink:href') or '') if image is not None else ''
    links, seen = [], set()
    for a in svg.find_all('a'):
        href = a.attrs.get('href') or a.attrs.get('xlink:href') or ''
        label = _collapse(''.join(t for n in a.walk() for t in n.children if isinstance(t, str)))
        if href.startswith('#') and len(href) > 1 and label and href not in seen:
            seen.add(href)
            links.append(f'[{label}]({href})')
    lines = []
    if base and not base.startswith('data:'):
        lines.append(f'🗺 *Map image: {base}*')
    if links:
        lines.append('**Map locations:** ' + ', '.join(links))
    return '\n\n' + '\n\n'.join(lines) + '\n\n' if lines else ''


def to_markdown(nodes, exclude: Optional[Set[int]] = None) -> str:
    """Convert a node (or list of nodes) to markdown. ``exclude`` holds ``id(node)`` values to omit.

    Anchors to ids are emitted as ``[text](#id)``; the importer rewrites them to
    ``rpg://`` links once the documents exist.
    """
    exclude = exclude or set()

    def inline(n) -> str:
        return ''.join(render(c) for c in n.children)

    def render(n) -> str:
        if isinstance(n, str):
            return re.sub(r'\s+', ' ', n)
        if id(n) in exclude or (n.tag in _SKIP and n.tag not in ('audio', 'svg')):
            return ''
        if n.has_class('imgprompt') or n.has_class('prompt-toggle') or n.has_class('gen-regen-btn'):
            return ''
        tag = n.tag
        if tag == 'audio':
            src = n.attrs.get('src') or (n.find('source').attrs.get('src') if n.find('source') else '')
            return f'\n\n🔊 *Audio: {src}*\n\n' if src else ''
        if tag == 'svg':
            return _svg_summary(n)
        if n.has_class('svg-legend'):
            items = [_single_line(inline(c)) for c in n.elements()]
            items = [i for i in items if i]
            return f'\n\n*Legend: {" · ".join(items)}*\n\n' if items else ''
        if n.has_class('veh-name'):
            inner = _single_line(inline(n))
            return f'\n\n**{inner}**\n\n' if inner else ''
        if n.has_class('veh-line') or 'display:block' in (n.attrs.get('style') or '').replace(' ', ''):
            inner = inline(n).strip()
            return f'\n\n{inner}\n\n' if inner else ''
        if tag == 'br':
            return '\n'
        if tag in ('strong', 'b'):
            inner = inline(n).strip()
            return f'**{inner}**' if inner else ''
        if tag in ('em', 'i'):
            inner = inline(n).strip()
            return f'*{inner}*' if inner else ''
        if tag == 'a':
            inner = inline(n).strip()
            href = n.attrs.get('href') or ''
            if not inner:
                return ''
            if href.startswith('#') and len(href) > 1:
                return f'[{inner}]({href})'
            if href.startswith(('http://', 'https://')):
                return f'[{inner}]({href})'
            return inner
        if tag == 'span' and n.has_class('lbl'):
            inner = inline(n).strip()
            return f'**{inner}:** ' if inner else ''
        if tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            inner = inline(n).strip()
            return f'\n\n### {inner}\n\n' if inner else ''
        if tag in ('ul', 'ol'):
            items = []
            for index, li in enumerate(c for c in n.elements() if c.tag == 'li'):
                bullet = f'{index + 1}.' if tag == 'ol' else '-'
                items.append(f'{bullet} {_single_line(inline(li))}')
            return '\n\n' + '\n'.join(items) + '\n\n' if items else ''
        if tag == 'table':
            return '\n\n' + _table(n) + '\n\n'
        if tag == 'summary':
            inner = _single_line(inline(n))
            return f'\n\n**{inner}**\n\n' if inner else ''
        if n.has_class('readaloud'):
            inner = inline(n).strip()
            return '\n\n' + '\n'.join('> ' + line for line in inner.splitlines()) + '\n\n' if inner else ''
        inner = inline(n)
        if tag in _BLOCK:
            return f'\n\n{inner.strip()}\n\n' if inner.strip() else ''
        return inner

    def _single_line(text: str) -> str:
        return re.sub(r'\s+', ' ', text).strip()

    def _table(table: Node) -> str:
        rows, header_row = [], None
        for row in table.find_all('tr'):
            cells = [c for c in row.elements() if c.tag in ('td', 'th')]
            if not cells:
                continue
            rendered = []
            for cell in cells:
                if cell.has_class('imgprompt') or 'courier' in (cell.attrs.get('style') or '').lower():
                    continue
                if any(c.has_class('veh-name') for c in cell.elements()):
                    rendered.append(to_markdown(cell).replace('\n\n', ' — '))   # keep the row on one line
                    continue
                rendered.append(_single_line(inline(cell)))
            if any(rendered):
                if header_row is None and all(c.tag == 'th' for c in cells):
                    header_row = len(rows)
                rows.append(rendered)
        if not rows:
            return ''
        if all(len(r) == 1 for r in rows):                  # layout table: plain paragraphs
            return '\n\n'.join(r[0] for r in rows)
        width = max(len(r) for r in rows)
        lines = ['| ' + ' | '.join(r + [''] * (width - len(r))) + ' |' for r in rows]
        if header_row == 0:
            lines.insert(1, '|' + ' --- |' * width)
        return '\n'.join(lines)

    items = nodes if isinstance(nodes, list) else [nodes]
    raw = ''.join(render(n) for n in items)
    raw = re.sub(r'[ \t]+\n', '\n', raw)
    raw = re.sub(r'\n{3,}', '\n\n', raw)
    return raw.strip()


# ---------------------------------------------------------------- model

@dataclass
class ParsedGear:
    """One line of an NPC's gear list (``.gear li``); imported as an inventory item."""
    title: str
    content: str = ""


@dataclass
class ParsedEntity:
    source_id: str
    entity_type: str
    title: str
    content: str = ""
    subtype: str = ""
    tags: List[str] = field(default_factory=list)
    faction_ref: str = ""       # source id of a faction this entity references first
    faction_hint: str = ""      # free text that may name a faction (matched against faction titles)
    image_prompt: str = ""
    image: str = ""             # path relative to the html file
    refs: List[str] = field(default_factory=list)   # source ids this entity links to
    extra_images: List[str] = field(default_factory=list)   # other pictures of the card (item, map, ...)
    extra_image_captions: Dict[str, str] = field(default_factory=dict)   # extra picture path -> caption
    gear: List[ParsedGear] = field(default_factory=list)    # NPC gear lines (inventory items)
    faction_state: str = ""     # what the module says when it names no faction: 'none', 'unknown' or 'undecided'
    count: int = 0              # data-count: one entry standing for several identical extras (0/1 = a single person)
    faction_line: bool = False  # the card carries a .npc-faction line or a data-faction attribute (the generation rule)


@dataclass
class ParsedSession:
    source_id: str
    title: str
    label: str = ""
    content: str = ""
    refs: List[str] = field(default_factory=list)   # entity source ids that appear in the scene


@dataclass
class ParsedModule:
    title: str
    source_key: str
    eyebrow: str = ""
    subtitle: str = ""
    rule_system: str = ""
    language: str = ""
    content: str = ""
    source_path: str = ""
    entities: List[ParsedEntity] = field(default_factory=list)
    sessions: List[ParsedSession] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    parser: str = "html"        # 'html' or 'json'


# ---------------------------------------------------------------- entity extraction

def _slug(text: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-') or 'module'


def _xref_ids(node: Node) -> List[str]:
    seen, out = set(), []
    for a in node.find_all('a'):
        href = a.attrs.get('href') or ''
        if href.startswith('#') and len(href) > 1 and href[1:] not in seen:
            seen.add(href[1:])
            out.append(href[1:])
    return out


def _title_for(node: Node) -> str:
    for selector in (('div', 'npc-name'),):
        found = node.find(*selector)
        if found is not None:
            return text_of(found)
    for tag in ('h4', 'h3', 'h2'):
        found = node.find(tag)
        if found is not None and text_of(found):
            return text_of(found)
    strong = node.find('strong')
    return text_of(strong) if strong is not None else node.id


def _header_info(node: Node):
    """(epithet, tags) taken from the summary / card header of an entity."""
    summary = node.find('summary') or node
    epithet_node = summary.find(None, 'npc-epithet')
    epithet = text_of(epithet_node) if epithet_node is not None else ''
    tags = []
    for cls in ('tag', 'room-tag', 'rank', 'badge'):
        for tag_node in summary.find_all(None, cls):
            value = text_of(tag_node)
            if value and value not in tags:
                tags.append(value)
    if node.tag != 'details':       # div.card: badge sits in the body
        for badge in node.find_all('span', 'badge'):
            value = text_of(badge)
            if value and value not in tags:
                tags.append(value)
    return epithet, tags


FACTION_STATES = ('none', 'unknown', 'undecided')


def _faction_declaration(node: Node):
    """(faction id, state) a card declares about its faction.

    ``data-faction`` on the card or on its ``.npc-faction`` line holds a faction id (``f-...``) or one of
    ``none`` / ``unknown`` / ``undecided``; without the attribute a ``#f-...`` link inside the
    ``.npc-faction`` line names the faction.
    """
    line = node.find(None, 'npc-faction')
    declared = (node.attrs.get('data-faction')
                or (line.attrs.get('data-faction') if line is not None else '') or '').strip().lstrip('#')
    if declared.lower() in FACTION_STATES:
        return '', declared.lower()
    if declared:
        return declared, ''
    if line is not None:
        for ref in _xref_ids(line):
            if ref.startswith('f-') and ref != node.id:
                return ref, ''
    return '', ''


def _count_of(node: Node) -> int:
    value = (node.attrs.get('data-count') or '').strip()
    return int(value) if value.isdigit() and int(value) > 1 else 0


_MAIN_IMAGE_CLASSES = ('gen-portrait', 'gen-room', 'gen-creature')


def _pick_images(node: Node):
    """(primary src, its image prompt, other srcs) of an entity.

    The primary picture is the one whose ``data-gen-id`` equals the entity id, then a
    ``gen-portrait``/``gen-room``/``gen-creature`` image, then the first image that is
    not a ``gen-item`` one. Pictures of belongings (``gen-item``) are kept as extras.
    """
    imgs = [i for i in node.find_all('img') if i.attrs.get('src')]
    if not imgs:
        first = node.find(None, 'imgprompt')
        return '', (text_of(first, skip_classes=()) if first is not None else ''), [], {}
    primary = (next((i for i in imgs if i.attrs.get('data-gen-id') == node.id), None)
               or next((i for i in imgs if any(i.has_class(c) for c in _MAIN_IMAGE_CLASSES)), None)
               or next((i for i in imgs if not i.has_class('gen-item')), imgs[0]))
    prompt = ''
    parent = primary.parent
    if parent is not None:      # the prompt that follows the picture belongs to it
        later = parent.children[parent.children.index(primary) + 1:]
        for sibling in later:
            if isinstance(sibling, Node):
                found = sibling if sibling.has_class('imgprompt') else sibling.find(None, 'imgprompt')
                if found is not None:
                    prompt = text_of(found, skip_classes=())
                    break
                if sibling.tag == 'img':
                    break
    if not prompt:
        first = node.find(None, 'imgprompt')
        prompt = text_of(first, skip_classes=()) if first is not None else ''
    extra_imgs = [i for i in imgs if i is not primary and i.attrs['src'] != primary.attrs['src']]
    extras: List[str] = []
    captions: Dict[str, str] = {}
    for img in extra_imgs:
        src = img.attrs['src']
        if src not in extras:
            extras.append(src)
            if img.has_class('gen-item'):
                captions[src] = 'Gear'
    return primary.attrs['src'], prompt, extras, captions


def _gear_items(node: Node) -> List[ParsedGear]:
    """Lines of the ``.gear`` list(s) of a card: one inventory item per ``<li>``."""
    items: List[ParsedGear] = []
    for block in node.find_all(None, 'gear'):
        for li in block.find_all('li'):
            text = to_markdown(li)
            if not text:
                continue
            bold = li.find('b') or li.find('strong')
            title = text_of(bold) if bold is not None else ''
            if not title:
                title = re.sub(r'[*_\[\]]', '', text.splitlines()[0])
            items.append(ParsedGear(title=_collapse(title)[:100] or 'Item', content=text))
    return items


def _row_entity(node: Node, ptype: str, subtype: str) -> ParsedEntity:
    """Table-row entity (g- minor NPCs, status-table c- rows)."""
    table = node.parent
    while table is not None and table.tag != 'table':
        table = table.parent
    headers: List[str] = []
    if table is not None:
        head_row = next((r for r in table.find_all('tr') if r.find('th') is not None), None)
        if head_row is not None:
            headers = [text_of(c) for c in head_row.elements()]
    cells = [c for c in node.elements() if c.tag in ('td', 'th')]
    title = text_of(cells[0]) if cells else node.id
    lines, prompt, tags = [], '', []
    for index, cell in enumerate(cells[1:], start=1):
        label = headers[index] if index < len(headers) else ''
        is_prompt = ('courier' in (cell.attrs.get('style') or '').lower()
                     or 'prompt' in label.lower())
        value = to_markdown(cell)
        for badge in cell.find_all('span', 'badge'):
            tags.append(text_of(badge))
        if is_prompt:
            prompt = text_of(cell)
        elif value:
            lines.append(f'**{label}:** {value}' if label else value)
    img = node.find('img')
    declared, state = _faction_declaration(node)
    count = _count_of(node)
    if count:
        if f'×{count}' not in tags:
            tags.append(f'×{count}')
    return ParsedEntity(
        source_id=node.id, entity_type=ptype, subtype=subtype, title=title,
        content='\n\n'.join(lines), tags=tags, image_prompt=prompt,
        image=(img.attrs.get('src') or '') if img is not None else '',
        refs=_xref_ids(node), faction_ref=declared if ptype == 'npc' else '',
        faction_hint='' if state else ' '.join(tags),
        faction_state=state if ptype == 'npc' else '', count=count,
        faction_line=node.find(None, 'npc-faction') is not None or bool(node.attrs.get('data-faction')))


def _card_entity(node: Node, ptype: str, subtype: str) -> ParsedEntity:
    epithet, tags = _header_info(node)
    title = _title_for(node)
    body = node.find(None, 'card-body')
    if body is not None:
        body_nodes: list = [body]
    else:
        body_nodes = [c for c in node.children
                      if not (isinstance(c, Node) and (c.tag in ('summary', 'h4', 'h3')))]
    exclude: Set[int] = set()
    # the title element is rendered separately
    for candidate in node.find_all('h4')[:1] + node.find_all(None, 'npc-name')[:1]:
        exclude.add(id(candidate))
    if node.tag != 'details':       # div.card: a paragraph holding only a badge duplicates the tags
        for p_node in node.find_all('p'):
            badges = p_node.find_all('span', 'badge')
            if badges and text_of(p_node) == ' '.join(text_of(b) for b in badges):
                exclude.add(id(p_node))
    faction_line = node.find(None, 'npc-faction')
    if faction_line is not None:             # shown once, right after the tags, wherever it sits in the card
        exclude.add(id(faction_line))
    count = _count_of(node)
    if count:
        if f'×{count}' not in tags:
            tags.append(f'×{count}')
    parts = []
    if epithet:
        parts.append(f'*{epithet}*')
    character = (node.attrs.get('data-character') or '').strip()
    if character and subtype == 'hook':
        parts.append(f'**Character:** {character}')
    if tags:
        parts.append('**Tags:** ' + ', '.join(tags))
    if faction_line is not None:
        parts.append(to_markdown(faction_line))
    parts.append(to_markdown(body_nodes, exclude))
    image, prompt, extras, captions = _pick_images(node)
    declared, state = _faction_declaration(node)
    faction_ref = declared or ('' if state else next(
        (r for r in _xref_ids(node) if r.startswith('f-') and r != node.id), ''))
    return ParsedEntity(
        source_id=node.id, entity_type=ptype, subtype=subtype, title=title,
        content='\n\n'.join(p for p in parts if p), tags=tags,
        faction_ref=faction_ref if ptype == 'npc' else '',
        faction_hint=('' if state else ' '.join(tags + ([epithet] if epithet else [])))
        if ptype == 'npc' else '',
        faction_state=state if ptype == 'npc' else '', count=count,
        faction_line=faction_line is not None or bool(node.attrs.get('data-faction')),
        image_prompt=prompt, image=image, extra_images=extras, extra_image_captions=captions,
        gear=_gear_items(node) if ptype in ('npc', 'character') else [],
        refs=[r for r in _xref_ids(node) if r != node.id])


def _scene_session(node: Node, entity_ids_inside: List[str]) -> ParsedSession:
    label_node = node.find(None, 'scene-no')
    title_node = node.find('h4')
    exclude = {id(n) for n in (label_node, title_node) if n is not None}
    title = text_of(title_node) if title_node is not None else node.id
    label = text_of(label_node) if label_node is not None else ''
    number = re.match(r'(\d+)\.', label)
    if number and title:
        title = f'{number.group(1)}. {title}'
    refs = [r for r in _xref_ids(node) if r != node.id]
    for inside in entity_ids_inside:
        if inside not in refs:
            refs.append(inside)
    content = to_markdown(node, exclude)
    if label:
        content = f'*{label}*\n\n{content}'
    return ParsedSession(source_id=node.id, title=title, label=label, content=content, refs=refs)


def _module_header(root: Node):
    h1 = root.find('h1')
    title = text_of(h1) if h1 is not None else ''
    eyebrow_node = root.find(None, 'eyebrow')
    sub_node = root.find(None, 'sub')
    return (title, text_of(eyebrow_node) if eyebrow_node is not None else '',
            text_of(sub_node) if sub_node is not None else '')


def _toc_titles(root: Node) -> Dict[str, str]:
    """Section id -> readable title from the table of contents (falls back to the nav bar)."""
    titles: Dict[str, str] = {}
    for container in root.find_all(None, 'toc') + root.find_all('nav'):
        for a in container.find_all('a'):
            href = a.attrs.get('href') or ''
            if href.startswith('#') and href[1:] not in titles and text_of(a):
                titles[href[1:]] = text_of(a)
    return titles


def _section_prose(root: Node, entity_nodes: Dict[str, Node], session_nodes: Dict[str, Node]) -> str:
    toc = _toc_titles(root)
    exclude = {id(n) for n in entity_nodes.values()} | {id(n) for n in session_nodes.values()}
    out = []
    for section in root.find_all('section'):
        header = section.find(None, 'section-header')
        title_node = (header.find('h2') if header is not None else None) or section.find('h2')
        title = toc.get(section.id) or (text_of(title_node) if title_node is not None else section.id)
        skip = set(exclude)
        if header is not None:
            skip.add(id(header))
        prose = to_markdown(section, skip)
        if not prose:
            continue
        if len(prose) > _MAX_SECTION_CHARS:
            prose = prose[:_MAX_SECTION_CHARS].rstrip() + '\n\n*(truncated on import)*'
        out.append(f'## {title}\n\n{prose}')
    return '\n\n'.join(out)


def parse_html(html: str, source_path: str = "") -> ParsedModule:
    """Parse module HTML (embedded JSON first, then heuristics)."""
    root = parse_dom(html)

    for script in root.find_all('script'):
        if script.id == 'dm-module-data':
            data = json.loads(''.join(c for c in script.children if isinstance(c, str)))
            module = module_from_json(data, source_path)
            return module

    html_el = root.find('html')
    language = (html_el.attrs.get('lang') or '') if html_el is not None else ''
    title, eyebrow, subtitle = _module_header(root)
    stem = Path(source_path).stem if source_path else ''
    if not title:
        title = stem.replace('_', ' ') or 'Untitled module'

    module = ParsedModule(
        title=title, source_key=_slug(stem or title), eyebrow=eyebrow, subtitle=subtitle,
        rule_system=eyebrow.split('·')[0].strip() if eyebrow else '', language=language,
        source_path=source_path, parser='html')

    entity_nodes: Dict[str, Node] = {}
    session_nodes: Dict[str, Node] = {}
    for node in root.walk():
        node_id = node.id
        if not node_id or node.inside('svg') or node.tag == 'svg' or not _ID_RE.match(node_id):
            continue
        prefix = node_id.split('-', 1)[0]
        if prefix == SESSION_PREFIX:
            if node_id in session_nodes:
                module.warnings.append(f'Duplicate id ignored: {node_id}')
            else:
                session_nodes[node_id] = node
        elif prefix in PREFIX_MAP:
            if node_id in entity_nodes:
                module.warnings.append(f'Duplicate id ignored: {node_id}')
            else:
                entity_nodes[node_id] = node

    # an id'd element that is only a heading anchor or has no content is not an entity
    for node_id, node in entity_nodes.items():
        ptype, subtype = PREFIX_MAP[node_id.split('-', 1)[0]]
        if node.tag in ('h2', 'h3', 'a', 'span'):
            continue
        entity = _row_entity(node, ptype, subtype) if node.tag == 'tr' else _card_entity(node, ptype, subtype)
        if not entity.title:
            module.warnings.append(f'Entity without a title skipped: {node_id}')
            continue
        module.entities.append(entity)

    known = {e.source_id for e in module.entities}
    for node_id, node in session_nodes.items():
        inside = [n.id for n in node.walk() if n is not node and n.id in known]
        module.sessions.append(_scene_session(node, inside))

    if not module.entities and not module.sessions:
        module.warnings.append(
            'No entities or scenes found: give cards ids with the prefixes c- g- m- f- l- item- gift- pw- h- hook- j- '
            '(see Help > Guides)')
    warn_node = root.find(None, 'warn')
    notice = text_of(warn_node) if warn_node is not None else ''
    module.content = _compose_module_content(module, _section_prose(root, entity_nodes, session_nodes), notice)
    return module


def _compose_module_content(module: ParsedModule, prose: str, notice: str = '') -> str:
    parts = []
    if module.eyebrow:
        parts.append(f'*{module.eyebrow}*')
    if module.subtitle:
        parts.append(module.subtitle)
    if notice:
        parts.append(f'> {notice}')
    if prose:
        parts.append(prose)
    return '\n\n'.join(parts)


MAX_HTML_BYTES = 50 * 1024 * 1024     # an adventure module is a few MB; this stops a junk or hostile file from freezing the app
MAX_SIDECAR_BYTES = 20 * 1024 * 1024


def _read_capped(path: Path, limit: int) -> str:
    if path.stat().st_size > limit:
        raise ValueError(f'{path.name} is larger than {limit // (1024 * 1024)} MB and was not read')
    return path.read_text(encoding='utf-8')


def parse_file(path) -> ParsedModule:
    path = Path(path)
    html = _read_capped(path, MAX_HTML_BYTES)
    module = parse_html(html, str(path))
    # Own sidecar first ("<name>.module-export.json"); the shared "module-export.json" only counts
    # when it describes THIS file (same module key), so sibling HTML files do not pick it up.
    if module.parser == 'html':
        for sidecar, shared in ((path.with_name(f'{path.stem}.module-export.json'), False),
                                (path.with_name('module-export.json'), True)):
            if not sidecar.exists():
                continue
            try:
                data = json.loads(_read_capped(sidecar, MAX_SIDECAR_BYTES))
                if data.get('format') != FORMAT_NAME:
                    continue
                if shared and _slug((data.get('module') or {}).get('key') or '') not in (
                        _slug(path.stem), module.source_key):
                    continue
                module = module_from_json(data, str(path))
                break
            except (OSError, ValueError, KeyError, TypeError, AttributeError):
                module.warnings.append(f'{sidecar.name} present but unreadable; used the HTML')
    return module


# ---------------------------------------------------------------- JSON contract

def module_from_json(data: dict, source_path: str = "") -> ParsedModule:
    """Build a ParsedModule from the ``dm-module`` JSON contract (formatVersion 1)."""
    if data.get('format') != FORMAT_NAME:
        raise ValueError('Not a dm-module export')
    if int(data.get('formatVersion', 0)) > FORMAT_VERSION:
        raise ValueError(f"dm-module formatVersion {data.get('formatVersion')} is newer than supported ({FORMAT_VERSION})")
    meta = data.get('module') or {}
    stem = Path(source_path).stem if source_path else ''
    title = meta.get('title') or stem or 'Untitled module'
    module = ParsedModule(
        title=title, source_key=_slug(meta.get('key') or stem or title),
        eyebrow=meta.get('eyebrow', ''), subtitle=meta.get('subtitle', ''),
        rule_system=meta.get('ruleSystem', ''), language=meta.get('language', ''),
        content=meta.get('content', ''), source_path=source_path, parser='json')
    for e in data.get('entities', []):
        module.entities.append(ParsedEntity(
            source_id=e['id'], entity_type=e.get('type', 'npc'), subtype=e.get('subtype', ''),
            title=e.get('title', e['id']), content=e.get('content', ''), tags=list(e.get('tags', [])),
            faction_ref=e.get('factionRef', ''), faction_hint=e.get('factionHint', ''),
            image_prompt=e.get('imagePrompt', ''), image=e.get('image', ''), refs=list(e.get('refs', [])),
            extra_images=list(e.get('extraImages', [])),
            extra_image_captions=dict(e.get('extraImageCaptions', {})),
            faction_state=e.get('factionState') or ('none' if e.get('noFaction') else ''),
            count=int(e.get('count', 0) or 0),
            gear=[ParsedGear(title=g['title'], content=g.get('content', '')) for g in e.get('gear', [])]))
    for s in data.get('sessions', []):
        module.sessions.append(ParsedSession(
            source_id=s['id'], title=s.get('title', s['id']), label=s.get('label', ''),
            content=s.get('content', ''), refs=list(s.get('refs', []))))
    return module


def module_to_json(module: ParsedModule) -> dict:
    """Serialise a ParsedModule to the ``dm-module`` JSON contract (inverse of module_from_json)."""
    return {
        'format': FORMAT_NAME,
        'formatVersion': FORMAT_VERSION,
        'module': {
            'key': module.source_key, 'title': module.title, 'eyebrow': module.eyebrow,
            'subtitle': module.subtitle, 'ruleSystem': module.rule_system,
            'language': module.language, 'content': module.content,
        },
        'sessions': [{'id': s.source_id, 'title': s.title, 'label': s.label,
                      'content': s.content, 'refs': s.refs} for s in module.sessions],
        'entities': [{'id': e.source_id, 'type': e.entity_type, 'subtype': e.subtype,
                      'title': e.title, 'content': e.content, 'tags': e.tags,
                      'factionRef': e.faction_ref, 'factionHint': e.faction_hint,
                      'imagePrompt': e.image_prompt, 'image': e.image, 'refs': e.refs,
                      'extraImages': e.extra_images, 'extraImageCaptions': e.extra_image_captions,
                      'factionState': e.faction_state, 'count': e.count,
                      'gear': [{'title': g.title, 'content': g.content} for g in e.gear]}
                     for e in module.entities],
    }


def _main(argv: List[str]) -> int:
    """``python -m services.html_module_parser module.html [--export]``

    Prints what the importer will find in a module file (use it after changing the module
    format). ``--export`` also writes ``module-export.json`` next to the file, which the
    importer prefers over scraping the HTML and which can be edited by hand.
    """
    import collections
    import sys

    args = [a for a in argv if not a.startswith('--')]
    if len(args) != 1:
        print(_main.__doc__)
        return 2
    module = parse_file(args[0])
    kinds = collections.Counter(
        f'{e.entity_type}{"/" + e.subtype if e.subtype else ""}' for e in module.entities)
    print(f'{module.title}  [{module.rule_system or "?"}]  parsed from {module.parser}')
    print(f'  sessions: {len(module.sessions)}')
    for kind, count in sorted(kinds.items()):
        print(f'  {kind}: {count}')
    for warning in module.warnings:
        print(f'  warning: {warning}')
    if '--export' in argv:
        target = Path(args[0]).with_name(f'{Path(args[0]).stem}.module-export.json')
        target.write_text(json.dumps(module_to_json(module), ensure_ascii=False, indent=1), encoding='utf-8')
        print(f'  wrote {target}')
    sys.stdout.flush()
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(_main(sys.argv[1:]))
