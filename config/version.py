"""
Version information for RPG Database Manager.
"""

__version__ = "1.7.1"
__version_info__ = (1, 7, 1)

# Additional version metadata
APP_NAME = "RPG Database Manager"
APP_VERSION = __version__
APP_AUTHOR = "RPG Database Manager Team"
APP_COPYRIGHT = "Copyright © 2024-2025"
APP_DESCRIPTION = "A desktop application for managing RPG campaigns, sessions and entities"

def get_version_string() -> str:
    """Get formatted version string."""
    return f"{APP_NAME} v{APP_VERSION}"

def get_full_version_info() -> str:
    """Get full version information string."""
    return f"{APP_NAME} v{APP_VERSION}\n{APP_COPYRIGHT}\n{APP_DESCRIPTION}"
