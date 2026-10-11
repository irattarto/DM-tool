"""Preview-and-confirm dialog for sending images or text to a Discord channel.

Nothing is posted without this dialog: it shows exactly what will be sent and where.
"""

from dataclasses import dataclass
from typing import Callable, List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QPlainTextEdit, QProgressBar, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

from gui.theme import set_props
from gui.workers.discord_worker import DiscordLookupWorker, DiscordSendWorker
from services.discord_service import EMBEDS_PER_MESSAGE, DiscordClient, build_caption, split_message
from services.discord_settings import DiscordSettings
from utils.logger import get_logger


@dataclass
class SendItem:
    kind: str                      # 'image', 'text' or 'embed' (a card with the name as title)
    text: str = ""
    path: str = ""
    caption: str = ""


class DiscordSendDialog(QDialog):
    """Choose the channel, check the preview, confirm. The campaign's channel is preselected."""

    def __init__(self, db_manager, module_id: Optional[int], items: List[SendItem], parent=None,
                 client_factory: Optional[Callable[[], DiscordClient]] = None):
        super().__init__(parent)
        self.db = db_manager
        self.module_id = module_id
        self.items = items
        self.logger = get_logger('discord_send_dialog')
        self.settings = DiscordSettings(db_manager)
        self._client_factory = client_factory or self._default_client_factory
        self._worker = None
        self._already_sent = 0  # items posted by a failed attempt; a retry skips them
        self._sending = False
        self._channels_loaded = False

        self.setWindowTitle("Send to Discord")
        self.setModal(True)
        self.resize(560, 560)
        self._setup_ui()
        self._start_channel_load()

    # --- setup ---------------------------------------------------------
    def _default_client_factory(self) -> DiscordClient:
        token = self.settings.get_token()
        if not token:
            raise ValueError("No Discord bot token is saved. Add it in Preferences > Discord.")
        return DiscordClient(token)

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        row = QHBoxLayout()
        row.addWidget(QLabel("Channel:"))
        self.channel_combo = QComboBox()
        self.channel_combo.setMinimumWidth(240)
        self.channel_combo.currentIndexChanged.connect(self._update_confirmation)
        row.addWidget(self.channel_combo, 1)
        layout.addLayout(row)

        self.status_label = QLabel("")
        self.status_label.setTextFormat(Qt.TextFormat.PlainText)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        layout.addWidget(self._build_preview(), 1)

        self.warning_label = QLabel("")
        self.warning_label.setTextFormat(Qt.TextFormat.PlainText)
        self.warning_label.setWordWrap(True)
        set_props(self.warning_label, role="badge-warning")
        layout.addWidget(self.warning_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(self.cancel_btn)
        self.send_btn = QPushButton("Send")
        set_props(self.send_btn, variant="primary")
        self.send_btn.setEnabled(False)
        self.send_btn.clicked.connect(self._on_send)
        buttons.addWidget(self.send_btn)
        layout.addLayout(buttons)

    def _build_preview(self) -> QWidget:
        """What will be posted, exactly."""
        if self.items and self.items[0].kind == 'text':
            text = "\n\n".join(item.text for item in self.items)
            chunks = split_message(text)
            box = QPlainTextEdit()
            box.setReadOnly(True)
            box.setPlainText("\n\n--- next message ---\n\n".join(chunks) if len(chunks) > 1 else (chunks[0] if chunks else ""))
            self._preview_info = f"{len(chunks)} message{'s' if len(chunks) != 1 else ''}"
            return box

        container = QWidget()
        column = QVBoxLayout(container)
        for item in self.items:
            row = QHBoxLayout()
            thumb = QLabel()
            pixmap = QPixmap(item.path)
            if not pixmap.isNull():
                thumb.setPixmap(pixmap.scaled(96, 96, Qt.AspectRatioMode.KeepAspectRatio,
                                              Qt.TransformationMode.SmoothTransformation))
            row.addWidget(thumb)
            name = QLabel(build_caption(item.caption) or "(no name)")
            name.setTextFormat(Qt.TextFormat.PlainText)
            set_props(name, role="strong")
            name.setWordWrap(True)
            row.addWidget(name, 1)
            column.addLayout(row)
        column.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)
        if self.items and self.items[0].kind == 'embed':
            messages = -(-len(self.items) // EMBEDS_PER_MESSAGE)
            self._preview_info = (f"{len(self.items)} card{'s' if len(self.items) != 1 else ''} "
                                  f"in about {messages} message{'s' if messages != 1 else ''}")
        else:
            self._preview_info = f"{len(self.items)} image{'s' if len(self.items) != 1 else ''}"
        return scroll

    # --- channel loading -------------------------------------------------
    def _start_channel_load(self):
        self._module = self.db.get_module(self.module_id) if self.module_id else None
        if not self.settings.is_configured_for(self._module):
            self.status_label.setText(
                "Discord is not set up yet. Open Preferences > Discord, paste the bot token and choose the server "
                "(or choose a server for this campaign in the campaign manager).")
            set_props(self.status_label, state="warning")
            return
        guild_id, _ = self.settings.get_guild_for_module(self._module)
        self.status_label.setText("Loading channels...")
        worker = DiscordLookupWorker(self._client_factory, guild_id, self)
        worker.result_ready.connect(self._on_channels_loaded)
        worker.error.connect(self._on_channels_error)
        worker.finished.connect(lambda w=worker: self._on_worker_finished(w))
        self._worker = worker
        worker.start()

    def _on_channels_loaded(self, result):
        channels = result.get('channels', [])
        self.channel_combo.blockSignals(True)
        self.channel_combo.clear()
        self.channel_combo.addItem("Choose a channel...", None)  # nothing is posted by default
        for channel in channels:
            self.channel_combo.addItem(f"#{channel['name']}", channel['id'])

        # Preselect the module's channel only if the chosen server really has it
        module = self.db.get_module(self.module_id) if self.module_id else None
        wanted = module.get('discord_channel_id') if module else None
        if wanted:
            index = self.channel_combo.findData(str(wanted))
            if index >= 0:
                self.channel_combo.setCurrentIndex(index)
            else:
                self.status_label.setText("The campaign's linked channel is not in the selected server; "
                                          "choose a channel.")
        self.channel_combo.blockSignals(False)

        self._channels_loaded = True
        if not channels:
            self.status_label.setText("The bot sees no text channels in that server.")
        elif not (wanted and self.channel_combo.currentData()):
            if not wanted:
                self.status_label.setText("")
        set_props(self.status_label, state="")
        self._update_confirmation()

    def _on_channels_error(self, message: str):
        self.status_label.setText(message)
        set_props(self.status_label, state="error")

    def _on_worker_finished(self, worker):
        """Per-worker cleanup: a late lookup must not drop a newer send worker."""
        if self._worker is worker:
            self._worker = None
        worker.deleteLater()

    # --- confirmation + sending -------------------------------------------
    def _selected_channel(self) -> tuple:
        return self.channel_combo.currentData(), self.channel_combo.currentText()

    def _update_confirmation(self):
        channel_id, name = self._selected_channel()
        _, guild_name = self.settings.get_guild_for_module(getattr(self, "_module", None))
        if channel_id:
            where = f"{name}" + (f" on {guild_name}" if guild_name else "")
            self.warning_label.setText(
                f"Check the preview. This posts {self._preview_info} publicly in {where}. "
                "Messages cannot be taken back from this app.")
            self.send_btn.setText(f"Send {self._preview_info} to {name}")
        else:
            self.warning_label.setText("Choose a channel to continue.")
            self.send_btn.setText("Send")
        self.send_btn.setEnabled(bool(channel_id) and self._channels_loaded and not self._sending)

    def _set_busy(self, busy: bool):
        self._sending = busy
        self.progress_bar.setVisible(busy)
        self.cancel_btn.setEnabled(not busy)
        self.channel_combo.setEnabled(not busy)
        self.send_btn.setEnabled(not busy and bool(self._selected_channel()[0]))

    def _on_send(self):
        channel_id, _ = self._selected_channel()
        if not channel_id:
            return
        worker = DiscordSendWorker(self._client_factory, channel_id, self.items, self, skip=self._already_sent)
        self._send_worker = worker
        worker.progress.connect(self.status_label.setText)
        worker.result_ready.connect(self._on_send_finished)
        worker.finished.connect(lambda w=worker: self._on_worker_finished(w))
        self._worker = worker
        self._set_busy(True)
        set_props(self.status_label, state="")
        worker.start()

    def _on_send_finished(self, success: bool, message: str):
        self._set_busy(False)
        worker = getattr(self, '_send_worker', None)
        if not success and worker is not None and worker.sent_count:
            self._already_sent = worker.sent_count
            message += (f"\n{self._already_sent} item(s) were already posted; sending again continues "
                        "with the remaining ones only.")
        self.status_label.setText(message)
        set_props(self.status_label, state="ok" if success else "error")
        if success:
            self.send_btn.setEnabled(False)
            self.cancel_btn.setText("Close")

    # --- closing ---------------------------------------------------------
    def is_busy(self) -> bool:
        return self._sending

    def reject(self):
        if self.is_busy():  # never abandon a send half-way
            return
        if self._worker is not None and self._worker.isRunning():
            self._worker.wait(5000)  # a channel lookup in flight must end before the dialog is destroyed
        super().reject()

    def closeEvent(self, event):
        if self.is_busy():
            event.ignore()
            return
        super().closeEvent(event)
