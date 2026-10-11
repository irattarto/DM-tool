"""
Configuration package for the RPG Database Manager.
"""

from .constants import DB_LARGE_CONTENT_THRESHOLD
from .version import (
    __version__,
    APP_NAME,
    APP_VERSION,
    get_version_string,
    get_full_version_info,
)

__all__ = [
    'DB_LARGE_CONTENT_THRESHOLD',
    '__version__',
    'APP_NAME',
    'APP_VERSION',
    'get_version_string',
    'get_full_version_info',
]
