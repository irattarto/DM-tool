"""
One-time cleanup of data left behind by features that were removed from the application.
"""

from pathlib import Path

from utils.logger import get_logger


def remove_legacy_ai_data(data_dir: Path) -> int:
    """Delete the stored AI provider configuration (and its quarantined copies); returns the file count.

    The shared encryption key in the OS keyring is left alone: the Discord token is encrypted with it too.
    """
    logger = get_logger('legacy_cleanup')
    removed = 0
    for path in Path(data_dir).glob("ai_providers.json*"):
        try:
            path.unlink()
            removed += 1
        except OSError as e:
            logger.warning(f"Could not remove {path.name}: {e}")
    if removed:
        logger.info(f"Removed {removed} leftover AI configuration file(s)")
    return removed
