"""
Central data directory resolution for RPG Database Manager.

Uses QStandardPaths.DocumentsLocation instead of AppDataLocation so that
both the compiled EXE and MS Store Python resolve to the same physical path.
AppDataLocation is VFS-redirected for sandboxed processes (MS Store Python),
while DocumentsLocation is not subject to the sandbox redirect.
"""

import os
import sys
from pathlib import Path
from PyQt6.QtCore import QStandardPaths


def resolve_image_path(image_data: dict) -> str:
    """Return the best available file path for an image record.

    If the stored file_path exists on disk, return it unchanged.
    Otherwise reconstruct the path from get_data_dir() using the
    module_id and filename fields — handles data moved after migration.
    """
    file_path = image_data.get('file_path', '')
    if file_path and Path(file_path).exists():
        return file_path
    filename = image_data.get('filename', '')
    module_id = image_data.get('module_id', '')
    if filename and module_id:
        candidate = get_data_dir() / 'rpg_images' / 'modules' / str(module_id) / filename
        if candidate.exists():
            return str(candidate)
    return file_path  # Return original even if not found (caller handles missing)


def get_data_dir() -> Path:
    """Return the application data directory, creating it if necessary.

    Order: the RPG_DB_DATA_DIR environment variable (portable installs, tests), then
    Documents/RPG Database Manager/ (not subject to the MS Store Python VFS sandbox
    redirect, so EXE and Python agree on the same physical folder). On Linux a new
    install uses XDG (~/.local/share); the legacy Documents folder is only kept when it
    really contains a database, so merely creating a folder of that name never moves the data.
    """
    override = os.environ.get("RPG_DB_DATA_DIR")
    if override:
        data_dir = Path(override).expanduser()
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir

    docs_location = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
    docs = Path(docs_location) if docs_location else Path.home() / "Documents"
    data_dir = docs / "RPG Database Manager"
    if sys.platform.startswith("linux") and not (data_dir / "rpg_database_manager.db").exists():
        xdg = os.environ.get("XDG_DATA_HOME", "")
        base = Path(xdg) if xdg and Path(xdg).is_absolute() else Path.home() / ".local" / "share"
        data_dir = base / "RPG Database Manager"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def resource_path(relative: str) -> Path:
    """Locate a bundled resource both from source and from a PyInstaller build."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / relative
