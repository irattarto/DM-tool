"""Finding names of entries in text: completion while typing, links for known names, and new names worth an entry."""

import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

from utils.natural_sort import fold_text, natural_key

MIN_CHARS = 3             # typing this many letters starts a suggestion
MAX_SUGGESTIONS = 8


@dataclass(frozen=True)
class NameEntry:
    """One entry whose name can be suggested or linked."""
    title: str
    entity_type: str
    doc_id: int
    priority: int = 0     # lower comes first (pinned entries)

    @property
    def folded(self) -> str:
        return fold_text(self.title)

    @property
    def url(self) -> str:
        return f"rpg://{self.entity_type}/{self.doc_id}"


def _word_starts(tail: str) -> List[int]:
    """Positions in ``tail`` where a word starts (the start of the text, or after a non-letter)."""
    starts = [0] if tail and tail[0].isalnum() else []
    starts += [i + 1 for i, ch in enumerate(tail[:-1]) if not ch.isalnum() and tail[i + 1].isalnum()]
    return starts


def suggest(before: str, entries: Iterable[NameEntry], min_chars: int = MIN_CHARS,
            limit: int = MAX_SUGGESTIONS) -> Tuple[int, List[NameEntry]]:
    """Entries whose name continues what was just typed.

    ``before`` is the text left of the cursor. Returns (number of typed characters the suggestion replaces, matches);
    the longest typed text that matches something wins, so "Mira Th" finds "Mira Thornwood" before "Th" finds "Thorn".
    Names that merely contain the typed word come after the names that start with it.
    """
    tail = before[-60:]
    if not tail or not tail[-1].isalnum():
        return 0, []                       # a space or punctuation ends the word: nothing to complete
    pool = list(entries)
    for start in _word_starts(tail):
        typed = tail[start:]
        if len(typed) < min_chars:
            continue
        key = fold_text(typed)
        starting = [e for e in pool if e.folded.startswith(key)]
        if starting:
            starting.sort(key=lambda e: (e.priority, len(e.title), natural_key(e.title)))
            return len(typed), starting[:limit]
    # no name starts with it: names with a later word that starts with it ("thorn" -> "Mira Thornwood")
    last_start = max(_word_starts(tail), default=0)
    typed = tail[last_start:]
    if len(typed) >= min_chars and ' ' not in typed:
        key = fold_text(typed)
        inside = [e for e in pool if re.search(r'(?<![^\W_])' + re.escape(key), e.folded)]
        if inside:
            inside.sort(key=lambda e: (e.priority, len(e.title), natural_key(e.title)))
            return len(typed), inside[:limit]
    return 0, []


def link_known_names(text: str, entries: Iterable[NameEntry]) -> str:
    """Turn the names of entries found in ``text`` into Markdown links (longest names first, whole words only,
    text that is already inside a link is left alone)."""
    ordered = sorted((e for e in entries if len(e.title) >= 3), key=lambda e: -len(e.title))
    if not ordered:
        return text
    pattern = re.compile(r'(?<![\w\[(])(' + '|'.join(re.escape(e.title) for e in ordered) + r')(?![\w\]])', re.IGNORECASE)
    by_name = {e.title.casefold(): e for e in ordered}
    skip = [m.span() for m in re.finditer(r'\[[^\]]*\]\([^)]*\)', text)]

    def inside_link(position: int) -> bool:
        return any(a <= position < b for a, b in skip)

    out, last = [], 0
    for match in pattern.finditer(text):
        if inside_link(match.start()):
            continue
        entry = by_name.get(match.group(1).casefold())
        if entry is None:
            continue
        out.append(text[last:match.start()])
        out.append(f"[{match.group(1)}]({entry.url})")
        last = match.end()
    out.append(text[last:])
    return ''.join(out)


_CAPITAL_WORD = r"[A-ZÁÉÍÓÖŐÚÜŰ][\wáéíóöőúüűÁÉÍÓÖŐÚÜŰ'’-]+"
_NAME_RE = re.compile(rf"(?<![\w])({_CAPITAL_WORD}(?:\s+(?:of|the|de|von|van|{_CAPITAL_WORD}))*)")
_STOP_WORDS = frozenset(w.casefold() for w in (
    "The A An And Or But If In On At To Of For With From By As It Its He She They We You I His Her Their Our Your "
    "This That These Those There Here When Where What Who Why How Then Than So Not No Yes Is Are Was Were Be Been "
    "Monday Tuesday Wednesday Thursday Friday Saturday Sunday January February March April May June July August "
    "September October November December Session Notes Note Race Faction Name Description Tags Modules Date Status "
    "Participants Plan Summary Goals Goal Hook Hooks Scene Scenes Quest Location NPC Item Event Setting Module "
    "Roll Check DC HP AC Some Each Every After Before During While Once Meanwhile Suddenly Later Finally Also "
    "See Because However Therefore Otherwise Although Though Since Until Unless Yet Still Now Today Tomorrow Yesterday "
    "Goal Reward Given Appearance Background Personality Motivation Secrets Secret Stats Equipment Gear Loot Hooks "
    "Az Egy És Vagy De Hogy Nem Igen Ez Ott Itt Aztán Majd Közben Később Lásd Pl Azaz Illetve Továbbá Ezért Mert "
    "Viszont Ha Amikor Miközben Azután Ekkor Minden Néhány Sok Kevés Mivel Bár Hiszen Tehát Vagyis Ráadásul Szintén "
    "Csak Még Már Is Nincs Van Lehet Kell Fontos Megjegyzés Jegyzet Cél Jutalom Állapot Státusz Leírás Megjelenés "
    "Háttér Személyiség Képességek Felszerelés Kapcsolatok Teendők Ezek Azok Ők Ő Mi Ti Én Te Ön Ki Mit Hol Mikor "
    "Miért Hogyan Melyik Valaki Valami Senki Semmi Hétfő Kedd Szerda Csütörtök Péntek Szombat Vasárnap".split()))


@dataclass
class NameCandidate:
    """A name found in a text that is not a link yet: new, or a (short) form of existing entries."""
    text: str                                   # as written in the text
    matches: List[NameEntry] = field(default_factory=list)   # existing entries it may mean, best first
    exact: bool = False                         # the text is the full title of the first match
    count: int = 1


def _words(text: str) -> Tuple[str, ...]:
    return tuple(re.findall(r'\w+', fold_text(text)))


def find_name_candidates(text: str, entries: Iterable[NameEntry], ignored: Iterable[str] = (),
                         exclude_ids: Iterable[int] = (), limit: int = 20) -> List[NameCandidate]:
    """Capitalised names in ``text`` that are not links: possible new entries, and mentions of existing entries.

    - A name that is the title of an entry, or a part of a title ("Abernaty" for "Dr. Walter Abernaty", also with an
      ending such as "Abernatyval"), comes with those entries as ``matches`` so it can be linked instead of created.
    - A known title inside a longer run of capitalised words ("Find Mira Thornwood") is cut out: the candidate is the
      known part.
    - A single capitalised word that matches nothing counts only if it shows up inside a sentence at least once
      ("Lásd", "Meanwhile" only ever start sentences).
    Text inside links is ignored. ``exclude_ids`` (the entry being edited) never matches itself.
    """
    skip_ids = set(exclude_ids)
    pool = [e for e in entries if e.title]                  # the entry being edited stays in: its own name is no news
    plain = re.sub(r'\[([^\]]*)\]\([^)]*\)', ' ', text)                  # links are known already
    plain = re.sub(r'```.*?```|`[^`]*`', ' ', plain, flags=re.S)
    plain = plain.replace('*', '')                                       # **Goal:** and *emphasis*
    plain = re.sub(r'^[ \t]*(?:[A-Za-zÁ-ű ]{1,30}):[ \t]', ' ', plain, flags=re.M)   # "Race: " style labels
    ignored_folded = {fold_text(i) for i in ignored}
    entry_words = [(e, _words(e.title)) for e in pool]
    exact_index: Dict[Tuple[str, ...], List[NameEntry]] = {}
    for entry, words in entry_words:
        exact_index.setdefault(words, []).append(entry)

    def partial_matches(candidate: Tuple[str, ...]) -> List[NameEntry]:
        found = []
        for entry, words in entry_words:
            have = set(words)
            if all(w in have or any(len(x) >= 5 and w.startswith(x) for x in have) for w in candidate):
                found.append(entry)
        return sorted(found, key=lambda e: (len(e.title), natural_key(e.title)))

    results: Dict[str, NameCandidate] = {}
    mid_sentence: Dict[str, bool] = {}
    for match in _NAME_RE.finditer(plain):
        words = match.group(1).strip().split()
        while words and words[0].casefold() in _STOP_WORDS:               # "The Pale Court" -> keep it, "Then Kaz" -> Kaz
            if words[0].casefold() == 'the' and len(words) > 1:
                break
            words = words[1:]
        while words and words[-1].casefold() in _STOP_WORDS | {'of', 'the', 'de', 'von', 'van'}:
            words = words[:-1]
        if not words or len(words) > 4:
            continue
        if len(words) == 1 and (words[0].isupper() and len(words[0]) <= 5 or len(words[0]) < 3):   # HP, DC, NPC...
            continue
        name, matches, exact = ' '.join(words), [], False
        # a known title inside the run of words: the longest one wins ("Find Mira Thornwood" -> "Mira Thornwood")
        found = None
        for length in range(len(words), 0, -1):
            for start in range(0, len(words) - length + 1):
                segment = words[start:start + length]
                if length == 1 and segment[0].casefold() in _STOP_WORDS:
                    continue
                known = exact_index.get(_words(' '.join(segment)))
                if known:
                    found = (' '.join(segment), known)
                    break
            if found:
                break
        if found:
            name, matches, exact = found[0], list(found[1]), True
        else:
            matches = partial_matches(_words(name))
        if len(name) < 3 or name.casefold() in _STOP_WORDS or fold_text(name) in ignored_folded:
            continue
        others = [e for e in matches if e.doc_id not in skip_ids]
        if matches and not others:
            continue                                                       # only the entry itself
        matches = others
        before = plain[:match.start()].rstrip(' \t')
        starts_sentence = (not before) or before[-1] in '.!?\n:;"“'
        key = fold_text(name)
        if key in results:
            results[key].count += 1
        else:
            results[key] = NameCandidate(name, matches, exact)
        mid_sentence[key] = mid_sentence.get(key, False) or not starts_sentence
    found_names = [c for key, c in results.items()
                   if c.matches or len(c.text.split()) > 1 or mid_sentence.get(key)]
    found_names.sort(key=lambda c: (not c.matches, -c.count, natural_key(c.text)))
    return found_names[:limit]


def find_new_names(text: str, known_titles: Iterable[str], ignored: Iterable[str] = (),
                   limit: int = 12) -> List[str]:
    """The names in ``text`` that match no existing title at all: candidates for new entries."""
    entries = [NameEntry(title, '', index) for index, title in enumerate(known_titles)]
    return [c.text for c in find_name_candidates(text, entries, ignored, limit=limit * 2) if not c.matches][:limit]


def mention_spans(text: str, entry: NameEntry) -> Optional[Tuple[int, int]]:
    """Where the name of ``entry`` first appears in ``text`` as a whole word outside a link, or None."""
    skip = [m.span() for m in re.finditer(r'\[[^\]]*\]\([^)]*\)', text)]
    for match in re.finditer(r'(?<![\w])' + re.escape(entry.title) + r'(?![\w])', text, re.IGNORECASE):
        if not any(a <= match.start() < b for a, b in skip):
            return match.span()
    return None
