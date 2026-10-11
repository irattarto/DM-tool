"""
Cryptographic utilities for secure storage of sensitive data.
"""

import threading
import os
import base64
from pathlib import Path
from typing import Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from config.paths import get_data_dir

from utils.logger import get_logger



def _write_private_file(path, data: bytes) -> None:
    """Atomically write a secret file that is owner-only (0600) from creation."""
    path = str(path)
    tmp = path + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise

# --- Windows DPAPI: ties the key file to the Windows user account -----------------------------
# Used only when no system keyring is available. The protected blob is useless on another
# account or PC, so a synced / backed-up data folder no longer reveals the key. DPAPI does not
# depend on the file's location, so the EXE and Microsoft Store Python (which see different
# AppData folders) still agree on one key.
_DPAPI_MAGIC = b"DPAPI1:"
_DPAPI_ENTROPY = b"RPG Database Manager key file"


def _dpapi_call(func_name: str, data: bytes) -> bytes:
    import ctypes
    from ctypes import wintypes

    class _Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    def blob(raw: bytes):
        buffer = ctypes.create_string_buffer(raw, len(raw))
        return _Blob(len(raw), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char))), buffer

    crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    source, keep_source = blob(data)
    entropy, keep_entropy = blob(_DPAPI_ENTROPY)
    result = _Blob()
    # CryptProtectData(in, description, entropy, reserved, prompt, flags, out) and
    # CryptUnprotectData(in, description_out, entropy, reserved, prompt, flags, out) share this shape
    function = getattr(crypt32, func_name)
    ok = function(ctypes.byref(source), None, ctypes.byref(entropy), None, None, 0, ctypes.byref(result))
    if not ok:
        raise OSError(f"{func_name} failed (error {ctypes.GetLastError()})")
    try:
        return ctypes.string_at(result.pbData, result.cbData)
    finally:
        kernel32.LocalFree(result.pbData)
        del keep_source, keep_entropy


def _dpapi_protect(data: bytes) -> bytes:
    return _dpapi_call("CryptProtectData", data)


def _dpapi_unprotect(data: bytes) -> bytes:
    return _dpapi_call("CryptUnprotectData", data)


def _dpapi_available() -> bool:
    return os.name == "nt"


def _write_key_file(path, key: bytes, logger=None) -> bool:
    """Write the key file, DPAPI-protected where possible. Returns True when it is protected.

    The protected form is verified (decrypts back to the same key) before it replaces anything;
    on any problem the plain owner-only file is written instead - the key is never lost.
    """
    if _dpapi_available():
        try:
            blob = _DPAPI_MAGIC + _dpapi_protect(key)
            if _dpapi_unprotect(blob[len(_DPAPI_MAGIC):]) != key:
                raise OSError("DPAPI round trip did not return the same key")
            _write_private_file(path, blob)
            return True
        except Exception as e:
            if logger:
                logger.warning(f"Could not protect the key file with Windows DPAPI ({e}); keeping an owner-only file")
    _write_private_file(path, key)
    return False


KEYRING_SERVICE = "RPG Database Manager"
KEYRING_USER = "ai-config-encryption-key"  # legacy name, kept so existing installs find their key


class _KeyringError(Exception):
    """The system keyring cannot be used (missing, locked, no backend, write failed)."""


class _KeyringStore:
    """Thin wrapper over the optional `keyring` package (Windows Credential Manager,
    macOS Keychain, Secret Service/KWallet on Linux). Any failure becomes _KeyringError
    so callers can fall back to the protected key file."""

    def __init__(self):
        self._module = None
        if os.environ.get("RPG_DB_NO_KEYRING"):
            return
        try:
            import keyring
            from keyring.backends import fail
            if isinstance(keyring.get_keyring(), fail.Keyring):
                return  # no usable backend on this system
            self._module = keyring
        except Exception:
            self._module = None

    @property
    def usable(self) -> bool:
        return self._module is not None

    def get(self) -> Optional[str]:
        try:
            return self._module.get_password(KEYRING_SERVICE, KEYRING_USER)
        except Exception as e:
            raise _KeyringError(str(e)) from e

    def set(self, value: str) -> None:
        try:
            self._module.set_password(KEYRING_SERVICE, KEYRING_USER, value)
        except Exception as e:
            raise _KeyringError(str(e)) from e


def _remove_secret_file(path: Path) -> None:
    """Best-effort overwrite and delete of a secret file."""
    try:
        if path.exists():
            size = path.stat().st_size
            with open(path, 'r+b') as f:
                f.write(b'\0' * size)
                f.flush()
                os.fsync(f.fileno())
            path.unlink()
    except OSError:
        try:
            path.unlink()
        except OSError:
            pass


class SecureStorage:
    """
    Secure storage for sensitive data like API keys.

    Uses Fernet (symmetric encryption). The key lives in the operating system's secure
    store (keyring) when one is available; otherwise it is kept in an owner-only file in
    the application data folder, which is less safe if that folder is synced or shared.
    """

    BACKEND_KEYRING = 'keyring'
    BACKEND_FILE = 'file'

    def __init__(self):
        """Initialize secure storage."""
        self.logger = get_logger('secure_storage')
        self._cipher = None
        self.backend = self.BACKEND_FILE
        self._key_file_protected = False
        self._initialize_cipher()

    def _get_machine_id(self) -> bytes:
        """
        Get a machine-specific identifier for key derivation.

        Returns:
            Bytes representing machine identity
        """
        try:
            # Try to get machine ID from various sources
            if os.name == 'nt':  # Windows
                import winreg
                try:
                    # Try to get machine GUID from registry
                    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                       r"SOFTWARE\Microsoft\Cryptography")
                    machine_guid, _ = winreg.QueryValueEx(key, "MachineGuid")
                    winreg.CloseKey(key)
                    return machine_guid.encode()
                except Exception:
                    pass

            # Fallback: use username + computer name
            import getpass
            import socket
            machine_str = f"{getpass.getuser()}@{socket.gethostname()}"
            return machine_str.encode()

        except Exception as e:
            self.logger.warning(f"Could not get machine ID: {e}, using fallback")
            return b"rpg-db-manager-default-key"

    def _get_key_file_path(self) -> Path:
        """Get path to the encryption key file."""
        return get_data_dir() / ".secure_key"

    def _get_or_create_salt(self) -> bytes:
        """
        Get or create a unique salt for this installation.

        Returns:
            Salt bytes
        """
        salt_file = self._get_key_file_path().parent / ".secure_salt"

        try:
            if salt_file.exists():
                with open(salt_file, 'rb') as f:
                    salt = f.read()
                if len(salt) == 32:  # Validate salt length
                    return salt
                self.logger.warning("Invalid salt file, generating new salt")

            # Generate new random salt
            import secrets
            salt = secrets.token_bytes(32)

            # Save salt for future use
            _write_private_file(salt_file, salt)

            self.logger.info("Generated new unique salt for encryption")
            return salt

        except Exception as e:
            self.logger.error(f"Failed to manage salt file: {e}")
            raise RuntimeError(f"Cannot initialize encryption without salt: {e}")

    def _generate_key(self) -> bytes:
        """
        Generate encryption key from machine-specific data.

        Returns:
            Encryption key
        """
        machine_id = self._get_machine_id()

        # Get unique salt for this installation
        salt = self._get_or_create_salt()

        # Use PBKDF2HMAC to derive a key from machine ID
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,  # Unique salt per installation
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(machine_id))
        return key

    def _read_legacy_key(self, key_file: Path) -> Optional[bytes]:
        """Return the key stored in the key file, None if there is no file.

        Raises RuntimeError if the file exists but is not a valid key (never silently replaced).
        """
        if not key_file.exists():
            return None
        try:
            with open(key_file, 'rb') as f:
                key = f.read()
            self._key_file_protected = key.startswith(_DPAPI_MAGIC)
            if self._key_file_protected:
                if not _dpapi_available():
                    raise ValueError("the key file is protected for a Windows account and cannot be read on this system")
                key = _dpapi_unprotect(key[len(_DPAPI_MAGIC):])
            if len(key) != 44:  # Fernet keys are 44 bytes when base64 encoded
                raise ValueError(f"Invalid key length: {len(key)}")
            Fernet(key)
            return key
        except Exception as e:
            self.logger.error(f"Could not load existing key: {e}")
            raise RuntimeError(
                f"Failed to load encryption key from {key_file}. "
                "Cannot proceed without valid encryption. "
                "Delete the key file to generate a new one (WARNING: existing encrypted data will be lost)."
            ) from e

    @property
    def key_file_protected(self) -> bool:
        """True when the fallback key file is protected for the Windows account (DPAPI)."""
        return self.backend == self.BACKEND_FILE and self._key_file_protected

    def _use_key(self, key: bytes, backend: str) -> None:
        self._cipher = Fernet(key)
        self.backend = backend

    def _initialize_cipher(self):
        """Load or create the encryption key: keyring first, protected file as fallback."""
        key_file = self._get_key_file_path()
        salt_file = key_file.parent / ".secure_salt"
        store = _KeyringStore()
        legacy_error = None
        try:
            legacy_key = self._read_legacy_key(key_file)
        except RuntimeError as e:
            # A corrupt key file must not block a working keyring key; it is left untouched
            legacy_key, legacy_error = None, e

        if store.usable:
            try:
                stored = store.get()
                if stored:
                    key = stored.encode()
                    self._use_key(key, self.BACKEND_KEYRING)
                    self.logger.info("Loaded encryption key from the system keyring")
                    if legacy_key is not None:
                        if legacy_key == key:
                            _remove_secret_file(key_file)
                            _remove_secret_file(salt_file)
                        else:
                            self.logger.warning(
                                "A key file and a different keyring key both exist; keeping the key file untouched"
                            )
                    return

                # No key in the keyring yet: migrate the legacy key, or create a new one
                if legacy_error is not None:
                    raise legacy_error  # the old key is unreadable; do not create a different one
                if legacy_key is not None:
                    key = legacy_key
                elif salt_file.exists():
                    key = self._generate_key()  # recover the machine-derived key of an older install
                else:
                    key = Fernet.generate_key()

                store.set(key.decode())
                if store.get() != key.decode():
                    raise _KeyringError("keyring read-back did not match the stored key")

                self._use_key(key, self.BACKEND_KEYRING)
                if legacy_key is not None or salt_file.exists():
                    # Only now that the keyring round trip is verified
                    _remove_secret_file(key_file)
                    _remove_secret_file(salt_file)
                    self.logger.info("Moved the encryption key from a file into the system keyring")
                else:
                    self.logger.info("Stored a new encryption key in the system keyring")
                return
            except _KeyringError as e:
                self.logger.warning(f"System keyring unavailable ({e}); using a protected key file instead")
        else:
            self.logger.warning("No system keyring available; the encryption key is kept in a protected file")

        # File fallback
        if legacy_error is not None:
            raise legacy_error  # never replace a key file we could not read
        if legacy_key is not None:
            self._use_key(legacy_key, self.BACKEND_FILE)
            self.logger.info("Loaded existing encryption key from file")
            if not self._key_file_protected and _dpapi_available():
                try:        # upgrade an older plain key file in place (verified before it is replaced)
                    self._key_file_protected = _write_key_file(key_file, legacy_key, self.logger)
                except Exception as e:
                    self.logger.warning(f"Could not upgrade the key file protection: {e}")
            return

        try:
            key = self._generate_key()
        except Exception as e:
            self.logger.error(f"Failed to generate encryption key: {e}")
            raise RuntimeError(
                "Failed to generate encryption key. "
                "Check file permissions and system configuration."
            ) from e

        try:
            self._key_file_protected = _write_key_file(key_file, key, self.logger)
            self.logger.info("Generated and saved new encryption key")
        except Exception as e:
            self.logger.error(f"Could not save encryption key: {e}")
            raise RuntimeError(
                f"Failed to save encryption key to {key_file}. "
                "Check file permissions."
            ) from e

        self._use_key(key, self.BACKEND_FILE)

    def encrypt(self, data: str) -> str:
        """
        Encrypt a string.

        Args:
            data: Plain text string to encrypt

        Returns:
            Encrypted string (base64 encoded)

        Raises:
            RuntimeError: If encryption fails
        """
        if not data:
            return ""

        if self._cipher is None:
            raise RuntimeError("Encryption cipher not initialized")

        try:
            encrypted_bytes = self._cipher.encrypt(data.encode('utf-8'))
            return base64.urlsafe_b64encode(encrypted_bytes).decode('utf-8')
        except Exception as e:
            self.logger.error(f"Encryption failed: {e}")
            raise RuntimeError(f"Failed to encrypt data: {e}") from e

    def decrypt(self, encrypted_data: str) -> str:
        """
        Decrypt an encrypted string.

        Args:
            encrypted_data: Encrypted string (base64 encoded)

        Returns:
            Decrypted plain text string

        Raises:
            RuntimeError: If decryption fails
        """
        if not encrypted_data:
            return ""

        if self._cipher is None:
            raise RuntimeError("Encryption cipher not initialized")

        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode('utf-8'))
            decrypted_bytes = self._cipher.decrypt(encrypted_bytes)
            return decrypted_bytes.decode('utf-8')
        except Exception as e:
            self.logger.error(f"Decryption failed: {e}")
            raise RuntimeError(
                f"Failed to decrypt data. This may indicate corrupted data or wrong encryption key. "
                f"Error: {e}"
            ) from e


# Global instance
_secure_storage = None
_secure_storage_lock = threading.Lock()


def get_secure_storage() -> SecureStorage:
    """Get the global secure storage instance (created once, even from several threads)."""
    global _secure_storage
    with _secure_storage_lock:
        if _secure_storage is None:
            _secure_storage = SecureStorage()
        return _secure_storage
