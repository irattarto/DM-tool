"""Worker threads for Discord calls (list servers/channels, send messages) off the GUI thread."""

import asyncio
from typing import Callable, List, Optional

from PyQt6.QtCore import QThread, pyqtSignal

from services.discord_service import DiscordClient, DiscordError
from utils.logger import get_logger


class DiscordLookupWorker(QThread):
    """Test a token / list servers / list the text channels of a server."""

    result_ready = pyqtSignal(object)  # dict: {'bot', 'guilds'} or {'channels'}
    error = pyqtSignal(str)

    def __init__(self, client_factory: Callable[[], DiscordClient], guild_id: Optional[str] = None,
                 parent=None):
        super().__init__(parent)
        self.client_factory = client_factory
        self.guild_id = guild_id
        self.logger = get_logger('discord_lookup_worker')

    def run(self):
        async def work():
            client = self.client_factory()
            if self.guild_id:
                channels = await client.list_text_channels(self.guild_id)
                return {'channels': [{'id': c.id, 'name': c.name} for c in channels]}
            me = await client.get_me()
            guilds = await client.list_guilds()
            return {'bot': me.get('username', '?'), 'guilds': guilds}

        try:
            self.result_ready.emit(asyncio.run(work()))
        except (DiscordError, ValueError) as e:
            self.error.emit(str(e))
        except Exception as e:
            self.logger.error(f"Discord lookup failed: {e}", exc_info=True)
            self.error.emit(f"Unexpected error: {e}")


class DiscordSendWorker(QThread):
    """Send a list of items (text or image) to one channel, one after the other."""

    progress = pyqtSignal(str)
    result_ready = pyqtSignal(bool, str)  # success, message

    def __init__(self, client_factory: Callable[[], DiscordClient], channel_id: str, items: List,
                 parent=None, skip: int = 0):
        super().__init__(parent)
        self.skip = max(0, skip)  # items already posted by an earlier, partly failed attempt
        self.sent_count = self.skip
        self.client_factory = client_factory
        self.channel_id = channel_id
        self.items = items
        self.logger = get_logger('discord_send_worker')

    def run(self):
        sent = {'count': self.skip}

        async def work():
            client = self.client_factory()
            total = len(self.items)
            index = 0
            while index < total:
                index += 1
                item = self.items[index - 1]
                if index <= self.skip:
                    continue
                self.progress.emit(f"Sending {index} of {total}...")
                if item.kind == 'embed':
                    # consecutive cards travel together, up to ten per message
                    group = []
                    while index <= total and self.items[index - 1].kind == 'embed':
                        group.append((self.items[index - 1].caption, self.items[index - 1].path))
                        index += 1
                    index -= 1

                    def batch_sent(count):
                        sent['count'] += count
                        self.sent_count = sent['count']
                    await client.send_embeds(self.channel_id, group, on_batch_sent=batch_sent)
                    continue
                if item.kind == 'image':
                    await client.send_image(self.channel_id, item.path, item.caption)
                else:
                    await client.send_text(self.channel_id, item.text)
                sent['count'] += 1
                self.sent_count = sent['count']

        try:
            asyncio.run(work())
        except (DiscordError, ValueError) as e:
            total = len(self.items)
            prefix = f"Sent {sent['count']} of {total}, then it failed: " if sent['count'] else ""
            self.result_ready.emit(False, prefix + str(e))
            return
        except Exception as e:
            self.logger.error(f"Discord send failed: {e}", exc_info=True)
            self.result_ready.emit(False, f"Unexpected error: {e}")
            return
        count = sent['count']
        noun = 'card' if any(item.kind == 'embed' for item in self.items) else 'message'
        self.result_ready.emit(True, f"Sent {count} {noun}{'s' if count != 1 else ''} to Discord.")
