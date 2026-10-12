"""
Application settings management for RPG Database Manager.
"""

import json
from utils.logger import get_logger
import sys
from typing import Any, Dict, Optional, Tuple
from dataclasses import dataclass, field

from PyQt6.QtCore import QSettings, QPoint, QSize
from config.paths import get_data_dir


@dataclass
class WindowSettings:
    """Window geometry and state settings."""
    position: QPoint = field(default_factory=lambda: QPoint(100, 100))
    size: QSize = field(default_factory=lambda: QSize(1200, 800))
    is_maximized: bool = False
    is_fullscreen: bool = False


@dataclass
class DatabaseSettings:
    """Database configuration settings."""


@dataclass
class SpeechToTextSettings:
    """Speech-to-text settings."""
    provider: str = "whisper"  # whisper (local, offline) or google (cloud)
    language: str = "hu-HU"  # Default to Hungarian
    timeout: int = 5  # Listening timeout in seconds
    phrase_limit: int = 120  # Maximum recording duration in seconds (30-480)
    device_index: Optional[int] = None  # Microphone device index (None = default)
    whisper_model: str = "small"  # tiny, base, small, medium, large-v3-turbo, large-v3, or auto
    whisper_device: str = "auto"  # auto (GPU if usable), cuda, cpu
    gpu_prompt_declined: bool = False  # the user said no to downloading the CUDA libraries; do not ask again


@dataclass
class UISettings:
    """User interface settings."""
    theme: str = "auto"  # auto, dark, light
    font_size: int = 11  # Increased from 10 for better readability
    font_family: str = "Segoe UI" if sys.platform == "win32" else ""  # "" = system default font
    show_tooltips: bool = True
    confirm_deletions: bool = True
    compact_mode: bool = False  # Reduced spacing
    show_icons: bool = True  # Enable/disable icons
    animation_speed: str = "normal"  # slow, normal, fast, off

    # Typography scale settings
    typography_scale: str = "normal"  # small, normal, large, extra-large, custom
    # Custom typography sizes (used when typography_scale is "custom")
    custom_h1_size: int = 18
    custom_h2_size: int = 14
    custom_h3_size: int = 12
    custom_body_size: int = 11
    custom_caption_size: int = 9


class Settings:
    """
    Centralized settings management for the RPG Database Manager.

    Handles loading, saving, and accessing application settings
    including window state, database configuration, and UI preferences.
    """

    def __init__(self, settings_file: Optional[str] = None):
        """Initialize settings manager.

        Args:
            settings_file: Optional custom path to settings file
        """
        if settings_file is None:
            settings_file = str(get_data_dir() / "rpg_database_manager.ini")

        self.settings_file = settings_file
        self._settings = QSettings(settings_file, QSettings.Format.IniFormat)
        self.logger = get_logger('settings')

        # Initialize default settings
        self._window = WindowSettings()
        self._database = DatabaseSettings()
        self._ui = UISettings()
        self._speech_to_text = SpeechToTextSettings()
        self._custom_settings: Dict[str, Any] = {}

    def _value(self, key: str, default=None, type_=None):
        """One setting, never raising: a damaged or mistyped value falls back to its default, so a single
        bad entry cannot reset all the other settings."""
        try:
            if type_ is None:
                return self._settings.value(key, default)
            return self._settings.value(key, default, type_)
        except Exception as e:
            get_logger('settings').warning(f"Ignoring unreadable setting {key!r}: {e}")
            return default

    def load_settings(self) -> None:
        """Load settings from storage."""
        try:
            # Load window settings
            if self._settings.contains("Window/position_x"):
                pos_x = self._value("Window/position_x", 100, int)
                pos_y = self._value("Window/position_y", 100, int)
                self._window.position = QPoint(pos_x, pos_y)

            if self._settings.contains("Window/width"):
                size_w = self._value("Window/width", 1200, int)
                size_h = self._value("Window/height", 800, int)
                self._window.size = QSize(size_w, size_h)

            self._window.is_maximized = self._value(
                "Window/maximized", False, bool
            )
            self._window.is_fullscreen = self._value(
                "Window/fullscreen", False, bool
            )

            # The removed AI features left a settings group behind
            self._settings.remove("AI")

            # Load database settings
            # (No database settings to load currently)

            # Load UI settings
            self._ui.theme = self._value("UI/theme", "auto")
            self._ui.font_size = self._value("UI/font_size", 11, int)
            self._ui.font_family = self._value("UI/font_family", "Segoe UI" if sys.platform == "win32" else "")
            self._ui.show_tooltips = self._value(
                "UI/show_tooltips", True, bool
            )
            self._ui.confirm_deletions = self._value(
                "UI/confirm_deletions", True, bool
            )
            self._ui.compact_mode = self._value(
                "UI/compact_mode", False, bool
            )
            self._ui.show_icons = self._value(
                "UI/show_icons", True, bool
            )
            self._ui.animation_speed = self._value(
                "UI/animation_speed", "normal"
            )

            # Load typography settings
            self._ui.typography_scale = self._value(
                "UI/typography_scale", "normal"
            )
            self._ui.custom_h1_size = self._value(
                "UI/custom_h1_size", 18, int
            )
            self._ui.custom_h2_size = self._value(
                "UI/custom_h2_size", 14, int
            )
            self._ui.custom_h3_size = self._value(
                "UI/custom_h3_size", 12, int
            )
            self._ui.custom_body_size = self._value(
                "UI/custom_body_size", 11, int
            )
            self._ui.custom_caption_size = self._value(
                "UI/custom_caption_size", 9, int
            )

            # Load speech-to-text settings
            self._speech_to_text.provider = self._value(
                "SpeechToText/provider", "whisper"
            )
            if self._speech_to_text.provider not in ("whisper", "google"):
                self._speech_to_text.provider = "whisper"  # e.g. the removed online OpenAI Whisper
            self._speech_to_text.language = self._value(
                "SpeechToText/language", "hu-HU"
            )
            self._speech_to_text.timeout = self._value(
                "SpeechToText/timeout", 5, int
            )
            self._speech_to_text.phrase_limit = min(480, max(30, self._value(
                "SpeechToText/phrase_limit", 120, int
            )))
            # Read device_index once and handle None case properly
            device_value = self._value("SpeechToText/device_index", None)
            try:
                self._speech_to_text.device_index = None if device_value in (None, '') else int(device_value)
            except (TypeError, ValueError):
                self._speech_to_text.device_index = None
            self._speech_to_text.whisper_model = self._value(
                "SpeechToText/whisper_model", "small"
            )
            self._speech_to_text.whisper_device = self._value(
                "SpeechToText/whisper_device", "auto"
            )
            self._speech_to_text.gpu_prompt_declined = self._value(
                "SpeechToText/gpu_prompt_declined", False, bool
            )

            # Load custom settings
            if self._settings.contains("custom_settings"):
                custom_json = self._value("custom_settings", "{}")
                self._custom_settings = json.loads(custom_json)

        except Exception as e:
            self.logger.warning(f"Error loading settings: {e}")
            # Keep default settings

    def save_settings(self) -> None:
        """Save current settings to storage."""
        try:
            # Save window settings
            self._settings.setValue("Window/position_x", self._window.position.x())
            self._settings.setValue("Window/position_y", self._window.position.y())
            self._settings.setValue("Window/width", self._window.size.width())
            self._settings.setValue("Window/height", self._window.size.height())
            self._settings.setValue("Window/maximized", self._window.is_maximized)
            self._settings.setValue("Window/fullscreen", self._window.is_fullscreen)

            # Save database settings
            # (No database settings to save currently)

            # Save UI settings
            self._settings.setValue("UI/theme", self._ui.theme)
            self._settings.setValue("UI/font_size", self._ui.font_size)
            self._settings.setValue("UI/font_family", self._ui.font_family)
            self._settings.setValue("UI/show_tooltips", self._ui.show_tooltips)
            self._settings.setValue("UI/confirm_deletions", self._ui.confirm_deletions)
            self._settings.setValue("UI/compact_mode", self._ui.compact_mode)
            self._settings.setValue("UI/show_icons", self._ui.show_icons)
            self._settings.setValue("UI/animation_speed", self._ui.animation_speed)

            # Save typography settings
            self._settings.setValue("UI/typography_scale", self._ui.typography_scale)
            self._settings.setValue("UI/custom_h1_size", self._ui.custom_h1_size)
            self._settings.setValue("UI/custom_h2_size", self._ui.custom_h2_size)
            self._settings.setValue("UI/custom_h3_size", self._ui.custom_h3_size)
            self._settings.setValue("UI/custom_body_size", self._ui.custom_body_size)
            self._settings.setValue("UI/custom_caption_size", self._ui.custom_caption_size)

            # Save speech-to-text settings
            self._settings.setValue("SpeechToText/provider", self._speech_to_text.provider)
            self._settings.setValue("SpeechToText/language", self._speech_to_text.language)
            self._settings.setValue("SpeechToText/timeout", self._speech_to_text.timeout)
            self._settings.setValue("SpeechToText/phrase_limit", self._speech_to_text.phrase_limit)
            self._settings.setValue("SpeechToText/device_index", self._speech_to_text.device_index)
            self._settings.setValue("SpeechToText/whisper_model", self._speech_to_text.whisper_model)
            self._settings.setValue("SpeechToText/whisper_device", self._speech_to_text.whisper_device)
            self._settings.setValue("SpeechToText/gpu_prompt_declined", self._speech_to_text.gpu_prompt_declined)

            # Save custom settings
            custom_json = json.dumps(self._custom_settings)
            self._settings.setValue("custom_settings", custom_json)

            # Sync to disk
            self._settings.sync()

        except Exception as e:
            self.logger.warning(f"Error saving settings: {e}")

    # Window settings properties
    @property
    def window(self) -> WindowSettings:
        """Get window settings."""
        return self._window

    @window.setter
    def window(self, value: WindowSettings) -> None:
        """Set window settings."""
        self._window = value

    # Database settings properties
    @property
    def database(self) -> DatabaseSettings:
        """Get database settings."""
        return self._database

    @database.setter
    def database(self, value: DatabaseSettings) -> None:
        """Set database settings."""
        self._database = value

    # UI settings properties
    @property
    def ui(self) -> UISettings:
        """Get UI settings."""
        return self._ui

    @ui.setter
    def ui(self, value: UISettings) -> None:
        """Set UI settings."""
        self._ui = value

    # Speech-to-text settings properties
    @property
    def speech_to_text(self) -> SpeechToTextSettings:
        """Get speech-to-text settings."""
        return self._speech_to_text

    @speech_to_text.setter
    def speech_to_text(self, value: SpeechToTextSettings) -> None:
        """Set speech-to-text settings."""
        self._speech_to_text = value

    # Custom settings methods
    def get_custom_setting(self, key: str, default: Any = None) -> Any:
        """Get a custom setting value."""
        return self._custom_settings.get(key, default)

    def set_custom_setting(self, key: str, value: Any) -> None:
        """Set a custom setting value."""
        self._custom_settings[key] = value

    # Convenience methods for common settings

    def get_last_module_id(self) -> Optional[int]:
        """Get the last used module ID."""
        module_id = self.get_custom_setting("last_module_id")
        return int(module_id) if module_id is not None else None

    def set_last_module_id(self, module_id: int) -> None:
        """Set the last used module ID."""
        self.set_custom_setting("last_module_id", module_id)

    def get_entity_sort_preference(self, entity_type: str) -> Tuple[int, str]:
        """Get the sort preference for an entity type.

        Args:
            entity_type: The entity type (e.g., 'npc', 'location', 'quest')

        Returns:
            Tuple of (column_index, sort_order) where sort_order is 'asc' or 'desc'
            Defaults to (0, 'asc') if not set
        """
        key = f"entity_sort_{entity_type}"
        value = self.get_custom_setting(key, "0,asc")
        parts = value.split(',')
        try:
            column = max(0, int(parts[0]))
        except (TypeError, ValueError):
            column = 0
        order = parts[1] if len(parts) > 1 and parts[1] in ('asc', 'desc') else 'asc'
        return (column, order)

    def set_entity_sort_preference(self, entity_type: str, column: int, sort_order: str) -> None:
        """Set the sort preference for an entity type.

        Args:
            entity_type: The entity type (e.g., 'npc', 'location', 'quest')
            column: The column index to sort by
            sort_order: The sort order ('asc' or 'desc')
        """
        key = f"entity_sort_{entity_type}"
        value = f"{column},{sort_order}"
        self.set_custom_setting(key, value)

    def get_entity_group_preference(self, entity_type: str) -> str:
        """Get how an entity list is grouped: '' (not grouped), 'module' or 'faction'."""
        value = self.get_custom_setting(f"entity_group_{entity_type}", "")
        return value if value in ('module', 'faction') else ''

    def set_entity_group_preference(self, entity_type: str, group: str) -> None:
        """Set how an entity list is grouped: '' (not grouped), 'module' or 'faction'."""
        self.set_custom_setting(f"entity_group_{entity_type}", group if group in ('module', 'faction') else '')

    def get_session_sort_preference(self) -> Tuple[int, str]:
        """Get the sort preference for the sessions tab.

        Returns:
            Tuple of (column_index, sort_order) where sort_order is 'asc' or 'desc'
            Defaults to (1, 'desc') - Date column, descending (newest first)
        """
        value = self.get_custom_setting("session_sort", "1,desc")
        parts = value.split(',')
        column = int(parts[0])
        order = parts[1] if len(parts) > 1 else 'desc'
        return (column, order)

    def set_session_sort_preference(self, column: int, sort_order: str) -> None:
        """Set the sort preference for the sessions tab.

        Args:
            column: The column index to sort by
            sort_order: The sort order ('asc' or 'desc')
        """
        value = f"{column},{sort_order}"
        self.set_custom_setting("session_sort", value)

    def get_column_widths(self, widget_name: str) -> Optional[list]:
        """Get saved column widths for a widget.

        Args:
            widget_name: Identifier for the widget (e.g., 'entity_npc', 'sessions')

        Returns:
            List of column widths or None if not saved
        """
        key = f"column_widths_{widget_name}"
        value = self.get_custom_setting(key)
        if value:
            try:
                return [int(w) for w in value.split(',')]
            except (ValueError, AttributeError):
                return None
        return None

    def set_column_widths(self, widget_name: str, widths: list) -> None:
        """Save column widths for a widget.

        Args:
            widget_name: Identifier for the widget (e.g., 'entity_npc', 'sessions')
            widths: List of column widths (integers)
        """
        key = f"column_widths_{widget_name}"
        value = ','.join(str(w) for w in widths)
        self.set_custom_setting(key, value)
