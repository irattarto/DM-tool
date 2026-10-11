"""Preferences tab for the Discord bot: token, connection test and server choice."""

from typing import Callable, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

from gui.theme import set_props
from gui.workers.discord_worker import DiscordLookupWorker
from services.discord_service import DiscordClient, validate_token
from services.discord_settings import DiscordSettings


class DiscordSettingsWidget(QWidget):
    """Token and server for the Discord bot. Changes are saved by apply() (Apply/OK)."""

    def __init__(self, db_manager, parent=None,
                 client_builder: Optional[Callable[[str], DiscordClient]] = None):
        super().__init__(parent)
        self.db = db_manager
        self._client_builder = client_builder or (lambda token: DiscordClient(token))
        self.settings = DiscordSettings(db_manager)
        self._worker = None
        self._dirty = False
        self._setup_ui()
        self._load()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        info = QLabel(
            "Send images and text from your campaign to Discord with a bot. You can use the bot you already "
            "have (shared with other tools) or a dedicated one. The app only makes web requests with the "
            "token; it does not log in as the bot, so a bot that is already running is not disturbed.\n\n"
            "The bot needs View Channel, Send Messages and Attach Files in the channels you post to. "
            "Create or copy the token in the Discord Developer Portal (Bot > Reset Token)."
        )
        info.setWordWrap(True)
        set_props(info, role="muted")
        layout.addWidget(info)

        form = QFormLayout()
        self.token_edit = QLineEdit()
        self.token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_edit.textEdited.connect(self._mark_dirty)
        form.addRow("Bot token:", self.token_edit)

        buttons = QHBoxLayout()
        self.connect_btn = QPushButton("Connect and load servers")
        self.connect_btn.clicked.connect(self._on_connect)
        self.remove_btn = QPushButton("Remove saved token")
        self.remove_btn.clicked.connect(self._on_remove)
        buttons.addWidget(self.connect_btn)
        buttons.addWidget(self.remove_btn)
        buttons.addStretch()
        form.addRow("", buttons)

        self.guild_combo = QComboBox()
        self.guild_combo.currentIndexChanged.connect(self._mark_dirty)
        form.addRow("Default server:", self.guild_combo)
        layout.addLayout(form)

        self.status_label = QLabel("")
        self.status_label.setTextFormat(Qt.TextFormat.PlainText)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        layout.addStretch()

    # --- state ------------------------------------------------------------
    def _load(self):
        guild_id, guild_name = self.settings.get_guild()
        self.guild_combo.blockSignals(True)
        self.guild_combo.clear()
        if guild_id:
            self.guild_combo.addItem(guild_name or guild_id, guild_id)
        self.guild_combo.blockSignals(False)
        if self.settings.has_token():
            self.token_edit.setPlaceholderText("A token is saved (type a new one to replace it)")
            self._set_status("A bot token is saved." + ("" if guild_id else " Choose a server below."), "ok")
        else:
            self.token_edit.setPlaceholderText("Paste the bot token here")
            self._set_status("Not set up yet.", "")
        self._dirty = False

    def _set_status(self, text: str, state: str = ""):
        self.status_label.setText(text)
        set_props(self.status_label, state=state)

    def _mark_dirty(self, *_):
        self._dirty = True

    def is_dirty(self) -> bool:
        return self._dirty

    # --- actions -------------------------------------------------------------
    def _current_token(self) -> Optional[str]:
        typed = self.token_edit.text().strip()
        return typed or self.settings.get_token()

    def _on_connect(self):
        try:
            token = validate_token(self._current_token() or "")
        except ValueError as e:
            self._set_status(str(e), "error")
            return
        self.connect_btn.setEnabled(False)
        self._set_status("Connecting...", "")
        worker = DiscordLookupWorker(lambda: self._client_builder(token), None, self)
        worker.result_ready.connect(self._on_connected)
        worker.error.connect(self._on_connect_error)
        worker.finished.connect(self._on_worker_finished)
        self._worker = worker
        worker.start()

    def _on_connected(self, result):
        previous = self.guild_combo.currentData()
        self.guild_combo.blockSignals(True)
        self.guild_combo.clear()
        for guild in result.get('guilds', []):
            self.guild_combo.addItem(guild['name'], guild['id'])
        index = self.guild_combo.findData(previous) if previous else 0
        self.guild_combo.setCurrentIndex(max(index, 0))
        self.guild_combo.blockSignals(False)
        count = self.guild_combo.count()
        self._dirty = True
        if count:
            self._set_status(f"Connected as {result.get('bot')}. Choose the server and press Apply or OK.", "ok")
        else:
            self._set_status(f"Connected as {result.get('bot')}, but the bot is not in any server yet. "
                             "Invite it to your server first.", "warning")

    def _on_connect_error(self, message: str):
        self._set_status(message, "error")

    def _on_worker_finished(self):
        self.connect_btn.setEnabled(True)
        worker, self._worker = self._worker, None
        if worker is not None:
            worker.deleteLater()

    def _on_remove(self):
        self.settings.clear_token()
        self.settings.set_guild(None)
        self.token_edit.clear()
        self._load()
        self._set_status("The saved token was removed.", "")

    # --- saving ----------------------------------------------------------------
    def apply(self) -> bool:
        """Save the token and server. Returns False (after showing why) if the token is invalid."""
        if not self._dirty:
            return True
        typed = self.token_edit.text().strip()
        try:
            if typed:
                self.settings.set_token(typed)
                self.token_edit.clear()
                self.token_edit.setPlaceholderText("A token is saved (type a new one to replace it)")
            guild_id = self.guild_combo.currentData()
            self.settings.set_guild(guild_id, self.guild_combo.currentText() if guild_id else None)
        except ValueError as e:
            self._set_status(str(e), "error")
            return False
        self._dirty = False
        self._set_status("Saved." if self.settings.has_token() else "Not set up yet.",
                         "ok" if self.settings.has_token() else "")
        return True
