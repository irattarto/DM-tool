"""
Discord integration through the bot REST API (no gateway connection).

Uses a bot token to list servers/channels and to post text and image files. The token
can belong to a bot shared with other tools or to a dedicated one; the app only makes
ordinary HTTPS requests and never logs in as the bot, so it does not interfere with a
running bot process.

Required bot permissions in the target channels: View Channel, Send Messages, Attach Files.
"""

import asyncio
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import aiohttp

from utils.logger import get_logger

API_BASE = "https://discord.com/api/v10"
USER_AGENT = "DiscordBot (https://github.com/irattarto/DM-tool, 1.0)"

MESSAGE_LIMIT = 2000                       # characters per message
EMBEDS_PER_MESSAGE = 10                    # Discord's limit of embeds (and attachments) per message
EMBED_TITLE_LIMIT = 256                    # characters in an embed title
DEFAULT_UPLOAD_LIMIT = 10 * 1024 * 1024    # bytes; the common limit for servers without boosts
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
CHANNEL_TYPE_TEXT = 0
CHANNEL_TYPE_ANNOUNCEMENT = 5
MAX_RATE_LIMIT_RETRIES = 3
MAX_RETRY_WAIT_SECONDS = 30.0


# --- errors ---------------------------------------------------------------
class DiscordError(Exception):
    """Base class; the message is written for the user."""


class DiscordAuthError(DiscordError):
    """The token is wrong or revoked (HTTP 401)."""


class DiscordPermissionError(DiscordError):
    """The bot may not do this in that server/channel (HTTP 403)."""


class DiscordNotFoundError(DiscordError):
    """Unknown channel or server (HTTP 404)."""


class DiscordFileTooLargeError(DiscordError):
    """The upload is bigger than Discord accepts (HTTP 413 or checked locally)."""


TRANSIENT_STATUSES = (500, 502, 503, 504)
MAX_TRANSIENT_RETRIES = 2


class DiscordRateLimitError(DiscordError):
    """Still rate limited after retrying."""


class DiscordNetworkError(DiscordError):
    """Could not reach Discord."""


@dataclass
class DiscordChannel:
    id: str
    name: str
    guild_id: str = ""


# --- pure helpers (unit tested) -------------------------------------------
_ID_RE = re.compile(r'^\d{15,25}$')
_TOKEN_RE = re.compile(r'^[A-Za-z0-9_\-.]{20,200}$')
_TAG_RE = re.compile(r'</?[A-Za-z][^<>]*>|<!--.*?-->', re.S)
_CONTROL_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')


def clean_text(text: str) -> str:
    """Plain text for Discord: HTML tags and control characters removed, Markdown kept."""
    text = _TAG_RE.sub('', text or '')
    text = _CONTROL_RE.sub('', text)
    return text.replace('\r\n', '\n').replace('\r', '\n').strip()


def split_message(text: str, limit: int = MESSAGE_LIMIT) -> List[str]:
    """Split text into chunks of at most ``limit`` characters.

    Prefers paragraph breaks, then line breaks, then spaces, and only cuts a word
    in half when a single word is longer than the limit.
    """
    text = clean_text(text)
    if not text:
        return []
    chunks: List[str] = []
    remaining = text
    while len(remaining) > limit:
        window = remaining[:limit]
        cut = max(window.rfind('\n\n'), -1)
        if cut < limit // 2:
            cut = max(cut, window.rfind('\n'))
        if cut < limit // 2:
            cut = max(cut, window.rfind(' '))
        if cut < 1:
            cut = limit
        chunk = remaining[:cut].rstrip()
        if chunk:
            chunks.append(chunk)
        remaining = remaining[cut:].lstrip('\n ')
    if remaining.strip():
        chunks.append(remaining.strip())
    return chunks


def _require_id(value: str, what: str) -> str:
    value = str(value or '').strip()
    if not _ID_RE.match(value):
        raise DiscordError(f"Invalid Discord {what} id.")
    return value


def build_caption(name: str) -> str:
    """The message text that accompanies an image: the entity name only."""
    return clean_text(name)[:MESSAGE_LIMIT]


def build_embed_title(name: str) -> str:
    """The title of an embed card: the entity name, cut to Discord's title limit."""
    return clean_text(name)[:EMBED_TITLE_LIMIT]


def build_embed_text(names: List[str]) -> str:
    """Plain message text listing the names, so notifications and clients without embeds still show them."""
    text = ", ".join(n for n in (clean_text(name) for name in names) if n)
    if len(text) > MESSAGE_LIMIT:
        text = text[:MESSAGE_LIMIT - 1].rstrip() + "…"
    return text


def batch_embeds(prepared: List[tuple], max_bytes: int = DEFAULT_UPLOAD_LIMIT,
                 per_message: int = EMBEDS_PER_MESSAGE) -> List[List[tuple]]:
    """Group prepared (name, filename, data, content_type) tuples into messages.

    A message holds at most ``per_message`` cards and at most ``max_bytes`` of image data in total.
    """
    batches: List[List[tuple]] = []
    current: List[tuple] = []
    size = 0
    for entry in prepared:
        entry_size = len(entry[2])
        if current and (len(current) >= per_message or size + entry_size > max_bytes):
            batches.append(current)
            current, size = [], 0
        current.append(entry)
        size += entry_size
    if current:
        batches.append(current)
    return batches


def validate_token(token: str) -> str:
    """Return the token stripped of surrounding whitespace, or raise ValueError."""
    token = (token or '').strip()
    if token.lower().startswith('bot '):
        token = token[4:].strip()
    if not _TOKEN_RE.match(token):
        raise ValueError("That does not look like a bot token. Copy it from the Discord Developer Portal "
                         "(Bot > Reset Token) without spaces.")
    return token


def _strip_metadata(data: bytes, suffix: str) -> bytes:
    """Remove EXIF/GPS data from JPEG, PNG and WebP uploads; other formats and failures pass through."""
    if suffix not in ('.jpg', '.jpeg', '.png', '.webp'):
        return data
    try:
        import io
        from PIL import Image
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            clean = image  # Pillow writes no EXIF/GPS unless asked to, so a plain re-save drops it
            buffer = io.BytesIO()
            fmt = {'.jpg': 'JPEG', '.jpeg': 'JPEG', '.png': 'PNG', '.webp': 'WEBP'}[suffix]
            options = {'quality': 95} if fmt in ('JPEG', 'WEBP') else {}
            clean.save(buffer, format=fmt, **options)
        return buffer.getvalue()
    except Exception as e:
        from utils.logger import get_logger
        get_logger('discord').warning(f"Could not strip image metadata, sending the original: {e}")
        return data


def prepare_image(path: str, max_bytes: int = DEFAULT_UPLOAD_LIMIT) -> tuple:
    """Return (filename, bytes, content_type) ready to upload, downscaling if the file is too large.

    Raises DiscordError for files that are missing or not images.
    """
    source = Path(path)
    if source.suffix.lower() not in IMAGE_EXTENSIONS or not source.is_file():
        raise DiscordError(f"Not a sendable image: {source.name}")
    data = source.read_bytes()
    content_type = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                    '.gif': 'image/gif', '.webp': 'image/webp'}[source.suffix.lower()]
    data = _strip_metadata(data, source.suffix.lower())
    if len(data) <= max_bytes:
        return source.name, data, content_type

    # Too large: re-encode as JPEG at decreasing size/quality until it fits
    try:
        import io
        from PIL import Image
        image = Image.open(source).convert('RGB')
        scale, quality = 1.0, 90
        for _ in range(8):
            candidate = image if scale == 1.0 else image.resize(
                (max(1, int(image.width * scale)), max(1, int(image.height * scale))))
            buffer = io.BytesIO()
            candidate.save(buffer, format='JPEG', quality=quality, optimize=True)
            if buffer.tell() <= max_bytes:
                return source.stem + '.jpg', buffer.getvalue(), 'image/jpeg'
            scale *= 0.75
            quality = max(60, quality - 5)
    except DiscordError:
        raise
    except Exception as e:
        raise DiscordFileTooLargeError(f"{source.name} is too large and could not be shrunk: {e}") from e
    raise DiscordFileTooLargeError(f"{source.name} is too large for Discord even after shrinking it.")


# --- client ---------------------------------------------------------------
class DiscordClient:
    """Small async client for the parts of the Discord REST API this app needs."""

    def __init__(self, token: str, base_url: str = API_BASE, upload_limit: int = DEFAULT_UPLOAD_LIMIT,
                 sleep: Optional[Callable[[float], Any]] = None):
        self._token = validate_token(token)
        self.base_url = base_url.rstrip('/')
        self.upload_limit = upload_limit
        self._sleep = sleep or asyncio.sleep
        self.logger = get_logger('discord')

    # -- plumbing --
    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bot {self._token}", "User-Agent": USER_AGENT}

    async def _request(self, method: str, path: str, *, json_body: Any = None,
                       form: Optional[aiohttp.FormData] = None) -> Any:
        """One API call with 429 handling. The token is never logged."""
        url = f"{self.base_url}{path}"
        timeout = aiohttp.ClientTimeout(total=60)
        for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
            try:
                async with aiohttp.ClientSession(timeout=timeout, headers=self._headers()) as session:
                    # A FormData can only be sent once; rebuild it per attempt via the factory
                    body = form() if callable(form) else form
                    async with session.request(method, url, json=json_body, data=body) as response:
                        if response.status == 429:
                            retry_after = await self._retry_after(response)
                            if attempt >= MAX_RATE_LIMIT_RETRIES:
                                raise DiscordRateLimitError(
                                    "Discord is rate limiting the bot. Wait a moment and try again.")
                            self.logger.warning(f"Discord rate limit, waiting {retry_after:.1f}s")
                            await self._sleep(retry_after)
                            continue
                        if response.status in TRANSIENT_STATUSES and attempt < MAX_TRANSIENT_RETRIES:
                            delay = 2 ** attempt
                            self.logger.warning(f"Discord answered {response.status}, retrying in {delay}s")
                            await self._sleep(delay)
                            continue
                        return await self._handle(response)
            except aiohttp.ClientConnectorError as e:
                # the connection was never established, so nothing was sent: safe to retry
                if attempt < MAX_TRANSIENT_RETRIES:
                    await self._sleep(2 ** attempt)
                    continue
                raise DiscordNetworkError(f"Could not reach Discord: {e}") from e
            except aiohttp.ClientError as e:
                raise DiscordNetworkError(f"Could not reach Discord: {e}") from e
            except asyncio.TimeoutError as e:
                raise DiscordNetworkError("Discord did not answer in time.") from e
        raise DiscordRateLimitError("Discord is rate limiting the bot. Wait a moment and try again.")

    @staticmethod
    async def _retry_after(response) -> float:
        try:
            data = await response.json(content_type=None)
            wait = float(data.get('retry_after', 1.0))
        except Exception:
            try:
                wait = float(response.headers.get('Retry-After', 1.0) or 1.0)
            except (TypeError, ValueError):
                wait = 1.0
        return min(max(wait, 0.1), MAX_RETRY_WAIT_SECONDS)

    async def _handle(self, response) -> Any:
        status = response.status
        if 200 <= status < 300:
            if status == 204:
                return None
            return await response.json(content_type=None)
        detail = ''
        try:
            data = await response.json(content_type=None)
            detail = str(data.get('message', ''))[:200]
        except Exception:
            pass
        if status == 401:
            raise DiscordAuthError("Discord rejected the bot token. Check it in Preferences > Discord.")
        if status == 403:
            raise DiscordPermissionError(
                "The bot is not allowed to do that. Give it View Channel, Send Messages and Attach Files "
                "in that channel.")
        if status == 404:
            raise DiscordNotFoundError("Discord could not find that channel or server. "
                                       "Is the bot in the server, and does the channel still exist?")
        if status == 413:
            raise DiscordFileTooLargeError("The file is too large for this Discord server.")
        raise DiscordError(f"Discord error {status}" + (f": {detail}" if detail else ""))

    # -- queries --
    async def get_me(self) -> Dict[str, Any]:
        """The bot's own user (also the cheapest way to test a token)."""
        return await self._request('GET', '/users/@me')

    async def list_guilds(self) -> List[Dict[str, Any]]:
        result: List[Dict[str, Any]] = []
        after = None
        for _ in range(20):  # at most 20 pages of 200 servers
            path = '/users/@me/guilds?limit=200' + (f'&after={after}' if after else '')
            page = await self._request('GET', path) or []
            result += [{'id': str(g['id']), 'name': g.get('name', '?')} for g in page]
            if len(page) < 200:
                break
            after = str(page[-1]['id'])
        return result

    async def list_text_channels(self, guild_id: str) -> List[DiscordChannel]:
        guild_id = _require_id(guild_id, 'server')
        channels = await self._request('GET', f'/guilds/{guild_id}/channels')
        result = [
            DiscordChannel(id=str(c['id']), name=c.get('name', '?'), guild_id=str(guild_id))
            for c in sorted(channels or [], key=lambda c: (c.get('position', 0), c.get('name', '')))
            if c.get('type') in (CHANNEL_TYPE_TEXT, CHANNEL_TYPE_ANNOUNCEMENT)
        ]
        return result

    # -- sending --
    async def send_text(self, channel_id: str, text: str) -> int:
        """Send text (split into several messages if needed). Returns the number of messages."""
        channel_id = _require_id(channel_id, 'channel')
        chunks = split_message(text)
        if not chunks:
            raise DiscordError("There is no text to send.")
        for chunk in chunks:
            await self._request('POST', f'/channels/{channel_id}/messages', json_body={
                'content': chunk,
                'allowed_mentions': {'parse': []},  # pasted @everyone / @here / role mentions never ping
            })
        return len(chunks)

    async def send_image(self, channel_id: str, image_path: str, caption: str) -> None:
        """Send one image file with the entity name as the message text."""
        channel_id = _require_id(channel_id, 'channel')
        filename, data, content_type = prepare_image(image_path, self.upload_limit)
        payload = json.dumps({
            'content': build_caption(caption),
            'allowed_mentions': {'parse': []},
            'attachments': [{'id': 0, 'filename': filename}],
        })

        def make_form() -> aiohttp.FormData:
            form = aiohttp.FormData()
            form.add_field('payload_json', payload, content_type='application/json')
            form.add_field('files[0]', data, filename=filename, content_type=content_type)
            return form

        await self._request('POST', f'/channels/{channel_id}/messages', form=make_form)

    async def send_embeds(self, channel_id: str, entries: List[tuple],
                          on_batch_sent: Optional[Callable[[int], Any]] = None) -> int:
        """Send (name, image_path) pairs as embed cards, up to 10 per message. Returns the message count.

        ``on_batch_sent(n)`` is called after each message with the number of cards it carried.
        """
        channel_id = _require_id(channel_id, 'channel')
        prepared = []
        for name, path in entries:
            filename, data, content_type = prepare_image(path, self.upload_limit)
            prepared.append((name, filename, data, content_type))
        if not prepared:
            raise DiscordError("There is nothing to send.")
        batches = batch_embeds(prepared, self.upload_limit)
        for batch in batches:
            files = []
            embeds = []
            for index, (name, filename, data, content_type) in enumerate(batch):
                suffix = Path(filename).suffix.lower()
                safe_name = f"npc{index}{suffix}"   # plain ASCII so attachment:// always resolves
                files.append((index, safe_name, data, content_type))
                embeds.append({'title': build_embed_title(name), 'image': {'url': f'attachment://{safe_name}'}})
            payload = json.dumps({
                'content': build_embed_text([entry[0] for entry in batch]),
                'embeds': embeds,
                'allowed_mentions': {'parse': []},
                'attachments': [{'id': index, 'filename': safe_name} for index, safe_name, _, _ in files],
            })

            def make_form(payload=payload, files=files) -> aiohttp.FormData:
                form = aiohttp.FormData()
                form.add_field('payload_json', payload, content_type='application/json')
                for index, safe_name, data, content_type in files:
                    form.add_field(f'files[{index}]', data, filename=safe_name, content_type=content_type)
                return form

            await self._request('POST', f'/channels/{channel_id}/messages', form=make_form)
            if on_batch_sent:
                on_batch_sent(len(batch))
        return len(batches)
