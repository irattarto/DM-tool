"""Helpers for opening local files that a document links to (audio from imported modules)."""

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QUrl

AUDIO_EXTENSIONS = frozenset({'.mp3', '.wav', '.ogg', '.m4a', '.flac'})


def local_audio_path(url: QUrl) -> Optional[Path]:
    """The file a ``file:`` link points at, or None when it is not safe to open.

    Documents (imported ones especially) are untrusted, so only an existing audio file on a local
    drive qualifies: no network shares (``file://server/...``, UNC), no other file types.
    """
    if url.scheme().lower() != 'file' or url.host() or url.path().startswith('//'):
        return None
    local = url.toLocalFile()
    if not local or local.startswith(('\\\\', '//')):
        return None
    path = Path(local)
    if path.suffix.lower() not in AUDIO_EXTENSIONS:
        return None
    try:
        return path.resolve() if path.is_file() else None
    except OSError:
        return None
