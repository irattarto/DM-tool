"""Choose the Discord server and default channel of a campaign."""

from typing import Callable, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox, QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from gui.theme import set_props
from gui.workers.discord_worker import DiscordLookupWorker
from services.discord_service import DiscordClient
from services.discord_settings import DiscordSettings


class ModuleDiscordChannelDialog(QDialog):
    """Pick the server and channel that are preselected whenever something is sent from this campaign."""

    def __init__(self, db_manager, module: dict, parent=None,
                 client_factory: Optional[Callable[[], DiscordClient]] = None):
        super().__init__(parent)
        self.db = db_manager
        self.module = module
        self.settings = DiscordSettings(db_manager)
        self._client_factory = client_factory or self._default_client_factory
        self._worker = None
        self._pending_guild = None  # server whose channels are being loaded

        self.setWindowTitle(f"Discord server and channel for '{module.get('name', '')}'")
        self.setModal(True)
        self.resize(440, 260)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("The server and channel are preselected when you send images or text "
                                "from this campaign."))

        # Own link first, else the default server from Preferences
        self._guild_id, self._guild_name = self.settings.get_guild_for_module(module)

        layout.addWidget(QLabel("Server:"))
        self.guild_combo = QComboBox()
        self.guild_combo.addItem("(no server)", None)
        if self._guild_id:
            self.guild_combo.addItem(self._guild_name or str(self._guild_id), str(self._guild_id))
            self.guild_combo.setCurrentIndex(1)
        layout.addWidget(self.guild_combo)

        layout.addWidget(QLabel("Channel:"))
        self.combo = QComboBox()
        self.combo.addItem("(no channel)", None)
        current_id, current_name = module.get('discord_channel_id'), module.get('discord_channel_name')
        if current_id:
            self.combo.addItem(f"#{current_name or current_id}", str(current_id))
            self.combo.setCurrentIndex(1)
        layout.addWidget(self.combo)

        self.status_label = QLabel("")
        self.status_label.setTextFormat(Qt.TextFormat.PlainText)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        self.save_btn = QPushButton("Save")
        set_props(self.save_btn, variant="primary")
        self.save_btn.clicked.connect(self._on_save)
        buttons.addWidget(cancel)
        buttons.addWidget(self.save_btn)
        layout.addLayout(buttons)

        self._load_guilds()

    def _default_client_factory(self) -> DiscordClient:
        token = self.settings.get_token()
        if not token:
            raise ValueError("No Discord bot token is saved. Add it in Preferences > Discord.")
        return DiscordClient(token)

    # --- loading -----------------------------------------------------------
    def _start_worker(self, guild_id, on_result):
        worker = DiscordLookupWorker(self._client_factory, guild_id, self)
        worker.result_ready.connect(on_result)
        worker.error.connect(self._on_error)
        worker.finished.connect(lambda w=worker: self._on_finished(w))
        self._worker = worker
        worker.start()

    def _load_guilds(self):
        if not self.settings.has_token():
            self.status_label.setText("Discord is not set up yet (Preferences > Discord). "
                                      "You can still keep or clear the current link.")
            set_props(self.status_label, state="warning")
            return
        self.status_label.setText("Loading servers...")
        self._start_worker(None, self._on_guilds_loaded)

    def _on_guilds_loaded(self, result):
        wanted = self.guild_combo.currentData()
        self.guild_combo.blockSignals(True)
        self.guild_combo.clear()
        self.guild_combo.addItem("(no server)", None)
        for guild in result.get('guilds', []):
            self.guild_combo.addItem(guild['name'], str(guild['id']))
        index = self.guild_combo.findData(wanted) if wanted else 0
        if wanted and index < 0:  # linked server no longer listed: keep it visible
            self.guild_combo.addItem(self._guild_name or str(wanted), str(wanted))
            index = self.guild_combo.count() - 1
        self.guild_combo.setCurrentIndex(max(index, 0))
        self.guild_combo.blockSignals(False)
        self.guild_combo.currentIndexChanged.connect(self._on_guild_changed)
        self._load_channels()

    def _on_guild_changed(self, *_):
        # Channels belong to a server: the old choice is meaningless on another one
        self.combo.clear()
        self.combo.addItem("(no channel)", None)
        self._load_channels()

    def _load_channels(self):
        guild_id = self.guild_combo.currentData()
        if not guild_id:
            self.status_label.setText("")
            return
        self.status_label.setText("Loading channels...")
        set_props(self.status_label, state="")
        self._pending_guild = guild_id
        self._start_worker(guild_id, self._on_channels_loaded)

    def _on_channels_loaded(self, result):
        if self._pending_guild != self.guild_combo.currentData():
            return  # answer for a server that is no longer selected
        wanted = self.combo.currentData()
        self.combo.blockSignals(True)
        self.combo.clear()
        self.combo.addItem("(no channel)", None)
        for channel in result.get('channels', []):
            self.combo.addItem(f"#{channel['name']}", channel['id'])
        index = self.combo.findData(wanted) if wanted else 0
        if wanted and index < 0:
            # Keep the saved link visible only while its own server is selected
            if str(self.guild_combo.currentData()) == str(self._guild_id):
                self.combo.addItem(f"#{self.module.get('discord_channel_name') or wanted}", wanted)
                index = self.combo.count() - 1
            else:
                index = 0
        self.combo.setCurrentIndex(max(index, 0))
        self.combo.blockSignals(False)
        self.status_label.setText("")

    def _on_error(self, message: str):
        self.status_label.setText(message)
        set_props(self.status_label, state="error")

    def _on_finished(self, worker):
        if self._worker is worker:
            self._worker = None
        worker.deleteLater()

    def _on_save(self):
        channel_id = self.combo.currentData()
        guild_id = self.guild_combo.currentData()
        name = self.combo.currentText().lstrip('#') if channel_id else None
        guild_name = self.guild_combo.currentText() if guild_id else None
        if channel_id and not guild_id:
            self._on_error("Choose the server of this channel.")
            return
        self.db.set_module_discord_channel(self.module['id'], channel_id, name, guild_id, guild_name)
        self.accept()

    def reject(self):
        if self._worker is not None and self._worker.isRunning():
            self._worker.wait(3000)
        super().reject()
