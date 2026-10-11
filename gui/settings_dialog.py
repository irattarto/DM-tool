"""
Settings dialog for RPG Database Manager application preferences.
"""

from gui.theme import set_props
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QComboBox,
    QLabel, QSpinBox, QTabWidget, QWidget,
    QFormLayout
)
from PyQt6.QtCore import Qt

from config.settings import Settings
from utils.ui_helpers import show_error, show_info
from utils.logger import get_logger
from gui.components.dialog_button_bar import DialogButtonBar


class SettingsDialog(QDialog):
    """
    Dialog for managing application settings including UI and database preferences.
    """

    def __init__(self, settings: Settings, db_manager=None, image_service=None, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.db_manager = db_manager
        self.image_service = image_service
        self.logger = get_logger('settings_dialog')

        self.entity_types_modified = False

        self.setWindowTitle("Preferences")
        self.setModal(True)
        self.resize(700, 600)

        self._setup_ui()
        self._load_current_settings()

    def _setup_ui(self):
        """Setup the settings dialog UI with tabs."""
        layout = QVBoxLayout(self)

        # Create tab widget
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # General tab
        self._setup_general_tab()

        # Speech-to-Text tab
        self._setup_speech_to_text_tab()
        if self.db_manager is not None:
            self._setup_entity_types_tab()
            self._setup_discord_tab()

        # Buttons - standardized bottom-right layout
        layout.addSpacing(15)  # Extra space before button bar
        button_bar = DialogButtonBar(alignment='right')
        buttons = button_bar.set_standard_buttons(['apply', 'ok', 'cancel'])

        self.apply_btn = buttons['apply']
        self.apply_btn.clicked.connect(lambda: self._on_apply())

        self.ok_btn = buttons['ok']
        self.ok_btn.clicked.connect(self._on_ok)

        self.cancel_btn = buttons['cancel']
        self.cancel_btn.clicked.connect(self.reject)

        layout.addWidget(button_bar)

    def _setup_general_tab(self):
        """Setup the general settings tab."""
        general_tab = QWidget()
        layout = QVBoxLayout(general_tab)

        # Application settings
        app_group = QGroupBox("Application Settings")
        app_layout = QVBoxLayout(app_group)

        # Theme selection
        theme_layout = QHBoxLayout()
        theme_label = QLabel("Theme:")
        theme_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        theme_layout.addWidget(theme_label)
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Auto", "Dark", "Light"])
        theme_layout.addWidget(self.theme_combo)
        app_layout.addLayout(theme_layout)

        # Font size
        font_layout = QHBoxLayout()
        font_size_label = QLabel("Font Size:")
        font_size_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        font_layout.addWidget(font_size_label)
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 18)
        self.font_size_spin.setValue(10)
        font_layout.addWidget(self.font_size_spin)
        app_layout.addLayout(font_layout)

        layout.addWidget(app_group)

        # Typography settings
        typography_group = QGroupBox("Typography Scale")
        typography_layout = QVBoxLayout(typography_group)

        # Typography scale preset
        scale_layout = QHBoxLayout()
        scale_label = QLabel("Heading & Text Scale:")
        scale_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        scale_layout.addWidget(scale_label)
        self.typography_scale_combo = QComboBox()
        self.typography_scale_combo.addItems(["Small", "Normal", "Large", "Extra Large", "Custom"])
        self.typography_scale_combo.currentTextChanged.connect(self._on_typography_scale_changed)
        scale_layout.addWidget(self.typography_scale_combo)
        typography_layout.addLayout(scale_layout)

        # Custom typography sizes (collapsed by default)
        self.custom_typography_group = QGroupBox("Custom Sizes")
        self.custom_typography_group.setCheckable(False)
        self.custom_typography_group.setVisible(False)
        custom_layout = QFormLayout(self.custom_typography_group)

        self.custom_h1_spin = QSpinBox()
        self.custom_h1_spin.setRange(12, 32)
        self.custom_h1_spin.setSuffix(" pt")
        custom_layout.addRow("Heading 1:", self.custom_h1_spin)

        self.custom_h2_spin = QSpinBox()
        self.custom_h2_spin.setRange(10, 24)
        self.custom_h2_spin.setSuffix(" pt")
        custom_layout.addRow("Heading 2:", self.custom_h2_spin)

        self.custom_h3_spin = QSpinBox()
        self.custom_h3_spin.setRange(9, 20)
        self.custom_h3_spin.setSuffix(" pt")
        custom_layout.addRow("Heading 3:", self.custom_h3_spin)

        self.custom_body_spin = QSpinBox()
        self.custom_body_spin.setRange(8, 18)
        self.custom_body_spin.setSuffix(" pt")
        custom_layout.addRow("Body Text:", self.custom_body_spin)

        self.custom_caption_spin = QSpinBox()
        self.custom_caption_spin.setRange(7, 14)
        self.custom_caption_spin.setSuffix(" pt")
        custom_layout.addRow("Caption:", self.custom_caption_spin)

        typography_layout.addWidget(self.custom_typography_group)

        # Help text
        help_label = QLabel("Adjust heading and text sizes for better readability.")
        help_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        set_props(help_label, role="hint")
        help_label.setWordWrap(True)
        typography_layout.addWidget(help_label)

        layout.addWidget(typography_group)

        layout.addStretch()

        self.tab_widget.addTab(general_tab, "General")


    def _load_speech_to_text_settings(self):
        """Load speech-to-text settings into the dialog."""
        # Set provider combo
        current_provider = self.settings.speech_to_text.provider
        provider_options = ["whisper", "google"]
        if current_provider in provider_options:
            index = provider_options.index(current_provider)
            self.stt_provider_combo.setCurrentIndex(index)

        # Set language combo
        language_options = [item.split(' - ')[0] for item in [
            "hu-HU - Hungarian",
            "en-US - English (US)",
            "en-GB - English (UK)",
            "de-DE - German",
            "fr-FR - French",
            "es-ES - Spanish",
            "it-IT - Italian",
            "pt-BR - Portuguese (Brazil)",
            "ru-RU - Russian",
            "ja-JP - Japanese",
            "ko-KR - Korean",
            "zh-CN - Chinese (Simplified)"
        ]]

        current_language = self.settings.speech_to_text.language
        if current_language in language_options:
            index = language_options.index(current_language)
            self.stt_language_combo.setCurrentIndex(index)

        # Set Whisper model combo
        current_model = self.settings.speech_to_text.whisper_model
        model_options = ["auto", "tiny", "base", "small", "medium", "large-v3-turbo", "large-v3"]
        if current_model == "large":
            current_model = "large-v3"
        if current_model in model_options:
            index = model_options.index(current_model)
            self.stt_whisper_model_combo.setCurrentIndex(index)

        # Set Whisper device combo
        current_device = self.settings.speech_to_text.whisper_device
        device_options = ["auto", "cuda", "cpu"]
        if current_device in device_options:
            index = device_options.index(current_device)
            self.stt_whisper_device_combo.setCurrentIndex(index)

        # Update UI visibility based on provider
        self._on_stt_provider_changed()

        # Set timeout and phrase limit
        self.stt_timeout_spin.setValue(self.settings.speech_to_text.timeout)
        self.stt_phrase_limit_spin.setValue(self.settings.speech_to_text.phrase_limit)

    def _populate_microphone_devices(self):
        """Populate the microphone device combo box with available devices."""
        try:
            import speech_recognition as sr

            self.stt_device_combo.clear()
            self.stt_device_combo.addItem("Default System Microphone", None)

            # Get list of available microphones
            try:
                devices = sr.Microphone.list_microphone_names()
                for i, device_name in enumerate(devices):
                    display_text = f"{i}: {device_name}"
                    self.stt_device_combo.addItem(display_text, i)

                # Set current selection based on saved setting
                current_device = self.settings.speech_to_text.device_index
                if current_device is None:
                    self.stt_device_combo.setCurrentIndex(0)  # Default
                else:
                    # Find the device index in the combo box
                    for idx in range(self.stt_device_combo.count()):
                        device_data = self.stt_device_combo.itemData(idx)
                        if device_data == current_device:
                            self.stt_device_combo.setCurrentIndex(idx)
                            break

            except Exception as e:
                self.logger.warning(f"Could not list microphone devices: {e}")
                # Keep only the default option

        except ImportError:
            self.stt_device_combo.addItem("Speech recognition not available", None)
            self.stt_device_combo.setEnabled(False)

    def _setup_speech_to_text_tab(self):
        """Setup the speech-to-text settings tab."""
        stt_tab = QWidget()
        layout = QVBoxLayout(stt_tab)

        # Speech-to-text settings
        stt_group = QGroupBox("Speech-to-Text Settings")
        stt_layout = QVBoxLayout(stt_group)

        # Provider selection
        provider_layout = QHBoxLayout()
        stt_provider_label = QLabel("Transcription Provider:")
        stt_provider_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        provider_layout.addWidget(stt_provider_label)
        self.stt_provider_combo = QComboBox()
        self.stt_provider_combo.addItems([
            "whisper - Local, offline (Whisper)",
            "google - Google cloud (sends audio to Google)"
        ])
        self.stt_provider_combo.currentTextChanged.connect(self._on_stt_provider_changed)
        provider_layout.addWidget(self.stt_provider_combo)
        stt_layout.addLayout(provider_layout)

        # Language selection
        language_layout = QHBoxLayout()
        stt_language_label = QLabel("Language:")
        stt_language_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        language_layout.addWidget(stt_language_label)
        self.stt_language_combo = QComboBox()
        self.stt_language_combo.addItems([
            "hu-HU - Hungarian",
            "en-US - English (US)",
            "en-GB - English (UK)",
            "de-DE - German",
            "fr-FR - French",
            "es-ES - Spanish",
            "it-IT - Italian",
            "pt-BR - Portuguese (Brazil)",
            "ru-RU - Russian",
            "ja-JP - Japanese",
            "ko-KR - Korean",
            "zh-CN - Chinese (Simplified)"
        ])
        language_layout.addWidget(self.stt_language_combo)
        stt_layout.addLayout(language_layout)

        # Whisper model selection (initially hidden)
        self.whisper_model_widget = QWidget()
        self.whisper_model_layout = QHBoxLayout(self.whisper_model_widget)
        self.whisper_model_layout.addWidget(QLabel("Whisper Model:"))
        whisper_model_label = QLabel("Whisper Model:")
        whisper_model_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.whisper_model_layout.addWidget(whisper_model_label)
        self.stt_whisper_model_combo = QComboBox()
        self.stt_whisper_model_combo.addItems([
            "auto - Best for this PC",
            "tiny - Fastest, poor with Hungarian",
            "base - Fast, weak with Hungarian",
            "small - Balanced, works on weak PCs",
            "medium - Good quality (4+ GB GPU)",
            "large-v3-turbo - Near-best, fast (5+ GB GPU)",
            "large-v3 - Best quality (6+ GB GPU)"
        ])
        self.whisper_model_layout.addWidget(self.stt_whisper_model_combo)
        self.whisper_model_widget.setVisible(False)
        stt_layout.addWidget(self.whisper_model_widget)

        # Whisper device selection (initially hidden)
        self.whisper_device_widget = QWidget()
        self.whisper_device_layout = QHBoxLayout(self.whisper_device_widget)
        self.whisper_device_layout.addWidget(QLabel("Compute Device:"))
        compute_device_label = QLabel("Compute Device:")
        compute_device_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.whisper_device_layout.addWidget(compute_device_label)
        self.stt_whisper_device_combo = QComboBox()
        self.stt_whisper_device_combo.addItems([
            "auto - GPU if usable, otherwise CPU",
            "cuda - NVIDIA GPU (faster)",
            "cpu - CPU (works everywhere, slower)"
        ])
        self.whisper_device_layout.addWidget(self.stt_whisper_device_combo)
        self.whisper_device_widget.setVisible(False)
        stt_layout.addWidget(self.whisper_device_widget)

        # Timeout settings
        timeout_layout = QHBoxLayout()
        listening_timeout_label = QLabel("Listening Timeout (seconds):")
        listening_timeout_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        timeout_layout.addWidget(listening_timeout_label)
        self.stt_timeout_spin = QSpinBox()
        self.stt_timeout_spin.setRange(1, 30)
        self.stt_timeout_spin.setValue(5)
        self.stt_timeout_spin.setToolTip("How long to wait for speech before timing out")
        timeout_layout.addWidget(self.stt_timeout_spin)
        stt_layout.addLayout(timeout_layout)

        # Phrase limit
        phrase_layout = QHBoxLayout()
        recording_duration_label = QLabel("Max Recording Duration (seconds):")
        recording_duration_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        phrase_layout.addWidget(recording_duration_label)
        self.stt_phrase_limit_spin = QSpinBox()
        self.stt_phrase_limit_spin.setRange(30, 480)
        self.stt_phrase_limit_spin.setValue(120)
        self.stt_phrase_limit_spin.setToolTip("Recording stops by itself (with a short sound) after this many seconds. The Google provider accepts at most 60 seconds, so it stops there even if this is higher.")
        phrase_layout.addWidget(self.stt_phrase_limit_spin)
        stt_layout.addLayout(phrase_layout)

        # Microphone device selection
        device_layout = QHBoxLayout()
        microphone_device_label = QLabel("Microphone Device:")
        microphone_device_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        device_layout.addWidget(microphone_device_label)
        self.stt_device_combo = QComboBox()
        self._populate_microphone_devices()
        self.stt_device_combo.setToolTip("Select which microphone to use for recording")
        device_layout.addWidget(self.stt_device_combo)
        stt_layout.addLayout(device_layout)

        layout.addWidget(stt_group)

        # Information
        info_group = QGroupBox("Information")
        info_layout = QVBoxLayout(info_group)

        self.stt_info_text = QLabel(
            "Speech-to-text uses Google Speech Recognition API.\n"
            "• Requires internet connection\n"
            "• Free service with usage limits\n"
            "• Supports multiple languages\n"
            "• Audio is processed securely by Google"
        )
        self.stt_info_text.setWordWrap(True)
        info_layout.addWidget(self.stt_info_text)

        layout.addWidget(info_group)
        layout.addStretch()

        self.tab_widget.addTab(stt_tab, "Speech-to-Text")

    def _load_current_settings(self):
        """Load current settings into the dialog."""
        # Load UI settings
        self.theme_combo.setCurrentText(self.settings.ui.theme.title())
        self.font_size_spin.setValue(self.settings.ui.font_size)

        # Load typography settings
        scale_map = {
            "small": "Small",
            "normal": "Normal",
            "large": "Large",
            "extra-large": "Extra Large",
            "custom": "Custom"
        }
        self.typography_scale_combo.setCurrentText(
            scale_map.get(self.settings.ui.typography_scale, "Normal")
        )
        self.custom_h1_spin.setValue(self.settings.ui.custom_h1_size)
        self.custom_h2_spin.setValue(self.settings.ui.custom_h2_size)
        self.custom_h3_spin.setValue(self.settings.ui.custom_h3_size)
        self.custom_body_spin.setValue(self.settings.ui.custom_body_size)
        self.custom_caption_spin.setValue(self.settings.ui.custom_caption_size)
        # Show/hide custom group based on scale
        self.custom_typography_group.setVisible(self.settings.ui.typography_scale == "custom")

        # Load speech-to-text settings
        self._load_speech_to_text_settings()
        self._populate_microphone_devices()



    def _on_apply(self, show_confirmation=True) -> bool:
        """Apply settings without closing dialog. Returns True when everything was applied."""
        try:
            if not self._apply_entity_types() or not self._apply_discord():
                return False
        except Exception as e:
            self.logger.exception("Applying settings failed")
            show_error(self, "Error", f"Failed to apply settings: {e}")
            return False
        try:
            # Apply theme
            theme = self.theme_combo.currentText()
            self.settings.ui.theme = theme.lower()

            # Apply font size
            font_size = self.font_size_spin.value()
            self.settings.ui.font_size = font_size

            # Apply typography settings
            scale_text = self.typography_scale_combo.currentText()
            scale_map_reverse = {
                "Small": "small",
                "Normal": "normal",
                "Large": "large",
                "Extra Large": "extra-large",
                "Custom": "custom"
            }
            self.settings.ui.typography_scale = scale_map_reverse.get(scale_text, "normal")
            self.settings.ui.custom_h1_size = self.custom_h1_spin.value()
            self.settings.ui.custom_h2_size = self.custom_h2_spin.value()
            self.settings.ui.custom_h3_size = self.custom_h3_spin.value()
            self.settings.ui.custom_body_size = self.custom_body_spin.value()
            self.settings.ui.custom_caption_size = self.custom_caption_spin.value()
    
            # Apply speech-to-text settings
            self.settings.speech_to_text.provider = self.stt_provider_combo.currentText().split(' - ')[0]
            self.settings.speech_to_text.language = self.stt_language_combo.currentText().split(' - ')[0]
            self.settings.speech_to_text.timeout = self.stt_timeout_spin.value()
            self.settings.speech_to_text.phrase_limit = self.stt_phrase_limit_spin.value()
            # Device index from combo box (None if "Default" is selected)
            device_text = self.stt_device_combo.currentText()
            if device_text.startswith("Default"):
                self.settings.speech_to_text.device_index = None
            else:
                # Extract device index from the text format "index: name"
                try:
                    device_index = int(device_text.split(':')[0].strip())
                    self.settings.speech_to_text.device_index = device_index
                except (ValueError, IndexError):
                    self.settings.speech_to_text.device_index = None

            # Apply Whisper settings
            self.settings.speech_to_text.whisper_model = self.stt_whisper_model_combo.currentText().split(' - ')[0]
            self.settings.speech_to_text.whisper_device = self.stt_whisper_device_combo.currentText().split(' - ')[0]

            # Save settings
            self.settings.save_settings()

            # Apply to parent window if it has _apply_settings
            if hasattr(self.parent(), '_apply_settings'):
                self.parent()._apply_settings()

            if show_confirmation:
                show_info(self, "Settings Applied", "Settings have been applied successfully.")
            return True

        except Exception as e:
            self.logger.exception("Applying settings failed")
            show_error(self, "Error", f"Failed to apply settings: {e}")
            return False

    def _on_typography_scale_changed(self, scale_text: str):
        """Handle typography scale combo box changes."""
        # Show/hide custom sizes group based on selection
        is_custom = (scale_text == "Custom")
        self.custom_typography_group.setVisible(is_custom)

    def _setup_entity_types_tab(self):
        """Entity type editor tab (needs the database)."""
        from gui.dialogs.entity_types_editor import EntityTypesEditor
        self.entity_types_editor = EntityTypesEditor(self.db_manager, self)
        self.tab_widget.addTab(self.entity_types_editor, "Entity Types")

    def _setup_discord_tab(self):
        """Discord bot settings tab (needs the database)."""
        from gui.dialogs.discord_settings_widget import DiscordSettingsWidget
        self.discord_settings_widget = DiscordSettingsWidget(self.db_manager, self)
        self.tab_widget.addTab(self.discord_settings_widget, "Discord")

    def _apply_discord(self) -> bool:
        widget = getattr(self, 'discord_settings_widget', None)
        if widget is None:
            return True
        if not widget.apply():
            self.tab_widget.setCurrentWidget(widget)
            return False
        return True

    def _apply_entity_types(self) -> bool:
        """Save entity type edits. Returns False (after telling the user) if they are invalid."""
        editor = getattr(self, 'entity_types_editor', None)
        if editor is None or not editor.is_dirty():
            return True
        try:
            if editor.apply():
                self.entity_types_modified = True
            return True
        except ValueError as e:
            show_error(self, "Entity Types", str(e))
            return False

    def _on_ok(self):
        """Apply settings and close dialog."""
        if self._on_apply(show_confirmation=False):
            self.accept()

    def _on_stt_provider_changed(self):
        """Handle speech-to-text provider selection change."""
        provider = self.stt_provider_combo.currentText().split(' - ')[0]

        if provider == "whisper":
            # Show Whisper-specific options
            self.whisper_model_widget.setVisible(True)
            self.whisper_device_widget.setVisible(True)

            # Update info text for Whisper
            self.stt_info_text.setText(
                "Speech-to-text uses OpenAI Whisper (local processing).\n"
                "• No internet connection required\n"
                "• Processes audio locally on your device\n"
                "• Higher accuracy for specialized content\n"
                "• Requires model download (first use only)\n"
                "• May be slower than Google service"
            )
        else:
            # Hide Whisper-specific options
            self.whisper_model_widget.setVisible(False)
            self.whisper_device_widget.setVisible(False)

            # Update info text for Google
            self.stt_info_text.setText(
                "Speech-to-text uses Google Speech Recognition API.\n"
                "• Requires internet connection\n"
                "• Free service with usage limits\n"
                "• Supports multiple languages\n"
                "• Audio is processed securely by Google"
            )
