"""Stored Discord settings: the bot token (encrypted) and the default server.

The token is encrypted with the same key protection as other stored secrets (OS keyring when
available) and kept in the application database. It is never written to logs, and module
backups do not contain it (they only carry module data).
"""

from typing import Optional

from utils.logger import get_logger

META_TOKEN = 'discord_bot_token'
META_GUILD = 'discord_guild_id'
META_GUILD_NAME = 'discord_guild_name'


class DiscordSettings:
    def __init__(self, db_manager, secure_storage=None):
        self.db = db_manager
        self._secure = secure_storage
        self.logger = get_logger('discord_settings')

    @property
    def secure(self):
        if self._secure is None:
            from utils.crypto_utils import get_secure_storage
            self._secure = get_secure_storage()
        return self._secure

    # token
    def set_token(self, token: str) -> None:
        from services.discord_service import validate_token
        token = validate_token(token)
        self.db.set_app_meta(META_TOKEN, self.secure.encrypt(token))

    def get_token(self) -> Optional[str]:
        encrypted = self.db.get_app_meta(META_TOKEN)
        if not encrypted:
            return None
        try:
            return self.secure.decrypt(encrypted)
        except Exception as e:  # key lost or data corrupted: behave as "not configured"
            self.logger.warning(f"Stored Discord token could not be decrypted: {e}")
            return None

    def clear_token(self) -> None:
        self.db.set_app_meta(META_TOKEN, None)

    def has_token(self) -> bool:
        return bool(self.db.get_app_meta(META_TOKEN))

    # server
    def set_guild(self, guild_id: Optional[str], name: Optional[str] = None) -> None:
        """Set the default server (used by campaigns that have no server of their own)."""
        self.db.set_app_meta(META_GUILD, str(guild_id) if guild_id else None)
        self.db.set_app_meta(META_GUILD_NAME, name if guild_id else None)

    def get_guild(self) -> tuple:
        return self.db.get_app_meta(META_GUILD), self.db.get_app_meta(META_GUILD_NAME)

    def is_configured(self) -> bool:
        return self.has_token() and bool(self.db.get_app_meta(META_GUILD))

    def get_guild_for_module(self, module: Optional[dict]) -> tuple:
        """The server of a campaign: its own link, else the default server."""
        if module and module.get('discord_guild_id'):
            return module['discord_guild_id'], module.get('discord_guild_name')
        return self.get_guild()

    def is_configured_for(self, module: Optional[dict]) -> bool:
        return self.has_token() and bool(self.get_guild_for_module(module)[0])
