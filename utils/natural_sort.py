"""Natural sorting: numbers inside text are ordered by value ("Room 2" before "Room 10"), accents and case are ignored."""

import re
import unicodedata
from typing import List, Union

_DIGITS = re.compile(r"(\d+)")


def fold_text(text: str) -> str:
    """Lower case without accents: "Ágnes" sorts next to "Agnes", not after "Zed"."""
    decomposed = unicodedata.normalize("NFKD", (text or "").casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def natural_key(text: str) -> List[Union[str, int]]:
    """A sort key for `text` that ignores case and accents and compares runs of digits as numbers.

    "1", "2", "10" sort in that order (plain text sorting gives "1", "10", "2"), and "item 9" comes before
    "Item 10". The key alternates text and number parts, so two keys always compare without type errors.
    """
    parts = _DIGITS.split(fold_text(text))  # text at even positions, digit runs at odd positions
    return [int(part) if index % 2 else part for index, part in enumerate(parts)]
