"""
Central configuration constants for the RPG Database Manager.

This module contains all hard-coded configuration values extracted
from throughout the codebase for easier maintenance and configuration.
"""

# Content size thresholds
DB_LARGE_CONTENT_THRESHOLD = 50000  # Bytes - threshold for "large" document content

# Size limits
IMAGE_MAX_SIZE_BYTES = 50 * 1024 * 1024  # Maximum image file size (50 MB)
