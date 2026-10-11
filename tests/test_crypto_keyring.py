"""Encryption key storage: system keyring first, protected file as fallback."""
import base64
import os

import pytest
from cryptography.fernet import Fernet

keyring = pytest.importorskip("keyring")
from keyring.backend import KeyringBackend

import utils.crypto_utils as crypto
from utils.crypto_utils import SecureStorage, KEYRING_SERVICE, KEYRING_USER


class MemoryKeyring(KeyringBackend):
    priority = 1

    def __init__(self):
        self.store = {}

    def get_password(self, service, username):
        return self.store.get((service, username))

    def set_password(self, service, username, password):
        self.store[(service, username)] = password

    def delete_password(self, service, username):
        self.store.pop((service, username), None)


class BrokenSetKeyring(MemoryKeyring):
    def set_password(self, service, username, password):
        raise RuntimeError("keyring is locked")


class LyingKeyring(MemoryKeyring):
    """Accepts writes but returns something else when read back."""

    def set_password(self, service, username, password):
        self.store[(service, username)] = "not-the-key"


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(crypto, "get_data_dir", lambda: tmp_path)
    monkeypatch.delenv("RPG_DB_NO_KEYRING", raising=False)
    return tmp_path


@pytest.fixture
def mem_keyring():
    previous = keyring.get_keyring()
    backend = MemoryKeyring()
    keyring.set_keyring(backend)
    yield backend
    keyring.set_keyring(previous)


def _legacy_install(data_dir, secret="sk-secret"):
    """Create what an older version left behind: key file + salt + a ciphertext."""
    old = SecureStorage.__new__(SecureStorage)
    import logging
    old.logger = logging.getLogger("legacy")
    old._cipher = None
    old.backend = "file"
    key = old._generate_key()
    crypto._write_private_file(data_dir / ".secure_key", key)
    token = base64.urlsafe_b64encode(Fernet(key).encrypt(secret.encode())).decode()
    return key, token


def test_fresh_install_uses_keyring_and_writes_no_key_file(data_dir, mem_keyring):
    storage = SecureStorage()
    assert storage.backend == "keyring"
    assert not (data_dir / ".secure_key").exists()
    assert (KEYRING_SERVICE, KEYRING_USER) in mem_keyring.store
    assert storage.decrypt(storage.encrypt("sk-abc")) == "sk-abc"
    # a second start reads the same key back
    assert SecureStorage().decrypt(storage.encrypt("sk-abc")) == "sk-abc"


def test_legacy_key_file_is_migrated_and_old_data_still_decrypts(data_dir, mem_keyring):
    key, token = _legacy_install(data_dir)
    assert (data_dir / ".secure_key").exists() and (data_dir / ".secure_salt").exists()

    storage = SecureStorage()
    assert storage.backend == "keyring"
    assert storage.decrypt(token) == "sk-secret"
    assert mem_keyring.store[(KEYRING_SERVICE, KEYRING_USER)] == key.decode()
    assert not (data_dir / ".secure_key").exists()
    assert not (data_dir / ".secure_salt").exists()


def test_lost_key_file_is_recovered_from_salt_into_keyring(data_dir, mem_keyring):
    key, token = _legacy_install(data_dir)
    (data_dir / ".secure_key").unlink()  # user deleted the key file; salt + machine id remain
    storage = SecureStorage()
    assert storage.backend == "keyring"
    assert storage.decrypt(token) == "sk-secret"


def test_no_keyring_backend_falls_back_to_protected_file(data_dir):
    from keyring.backends import fail
    previous = keyring.get_keyring()
    keyring.set_keyring(fail.Keyring())
    try:
        storage = SecureStorage()
        token = storage.encrypt("x")
        reopened = SecureStorage()  # still without a keyring: must find the same key file
    finally:
        keyring.set_keyring(previous)
    assert storage.backend == "file"
    key_file = data_dir / ".secure_key"
    assert key_file.exists()
    if os.name != "nt":  # Windows has no POSIX mode bits; the user profile ACL protects the file there
        assert (key_file.stat().st_mode & 0o077) == 0
    assert reopened.decrypt(token) == "x"


def test_env_override_forces_file_backend(data_dir, mem_keyring, monkeypatch):
    monkeypatch.setenv("RPG_DB_NO_KEYRING", "1")
    assert SecureStorage().backend == "file"
    assert mem_keyring.store == {}


def test_failed_keyring_write_keeps_legacy_file_and_still_works(data_dir):
    key, token = _legacy_install(data_dir)
    previous = keyring.get_keyring()
    keyring.set_keyring(BrokenSetKeyring())
    try:
        storage = SecureStorage()
    finally:
        keyring.set_keyring(previous)
    assert storage.backend == "file"
    assert (data_dir / ".secure_key").exists()
    assert storage.decrypt(token) == "sk-secret"


def test_read_back_mismatch_never_deletes_the_key_file(data_dir):
    key, token = _legacy_install(data_dir)
    previous = keyring.get_keyring()
    keyring.set_keyring(LyingKeyring())
    try:
        storage = SecureStorage()
    finally:
        keyring.set_keyring(previous)
    assert storage.backend == "file"
    assert (data_dir / ".secure_key").exists() and (data_dir / ".secure_salt").exists()
    assert storage.decrypt(token) == "sk-secret"


def test_conflicting_keys_keep_the_file(data_dir, mem_keyring):
    key, token = _legacy_install(data_dir)
    other = Fernet.generate_key().decode()
    mem_keyring.set_password(KEYRING_SERVICE, KEYRING_USER, other)
    storage = SecureStorage()
    assert storage.backend == "keyring"
    assert (data_dir / ".secure_key").exists()  # never delete a key that differs from the keyring's


def test_invalid_key_file_is_not_silently_replaced(data_dir, mem_keyring):
    (data_dir / ".secure_key").write_bytes(b"garbage")
    with pytest.raises(RuntimeError):
        SecureStorage()
    assert (data_dir / ".secure_key").read_bytes() == b"garbage"


# ---- Windows DPAPI protection of the fallback key file (fake reversible transform; real DPAPI is Windows-only)

@pytest.fixture
def fake_dpapi(monkeypatch):
    monkeypatch.setattr(crypto, "_dpapi_available", lambda: True)
    monkeypatch.setattr(crypto, "_dpapi_protect", lambda data: b"P" + data[::-1])
    monkeypatch.setattr(crypto, "_dpapi_unprotect", lambda blob: blob[1:][::-1])


@pytest.fixture
def no_keyring(monkeypatch):
    monkeypatch.setenv("RPG_DB_NO_KEYRING", "1")


def test_new_key_file_is_protected_for_the_windows_account(data_dir, fake_dpapi, no_keyring):
    storage = SecureStorage()
    raw = (data_dir / ".secure_key").read_bytes()
    assert raw.startswith(crypto._DPAPI_MAGIC) and storage.key_file_protected
    again = SecureStorage()                                   # reads the protected form back
    assert again.key_file_protected and again.decrypt(storage.encrypt("sk-1")) == "sk-1"


def test_plain_key_file_is_upgraded_and_old_data_still_decrypts(data_dir, fake_dpapi, no_keyring):
    key, token = _legacy_install(data_dir)
    storage = SecureStorage()
    assert (data_dir / ".secure_key").read_bytes().startswith(crypto._DPAPI_MAGIC)
    assert key not in (data_dir / ".secure_key").read_bytes()
    assert storage.decrypt(token) == "sk-secret"


def test_failed_protection_keeps_the_plain_key_file(data_dir, monkeypatch, no_keyring):
    monkeypatch.setattr(crypto, "_dpapi_available", lambda: True)

    def boom(_):
        raise OSError("no DPAPI")
    monkeypatch.setattr(crypto, "_dpapi_protect", boom)
    key, token = _legacy_install(data_dir)
    storage = SecureStorage()
    assert (data_dir / ".secure_key").read_bytes() == key and not storage.key_file_protected
    assert storage.decrypt(token) == "sk-secret"


def test_wrong_roundtrip_never_replaces_the_key_file(data_dir, monkeypatch, no_keyring):
    monkeypatch.setattr(crypto, "_dpapi_available", lambda: True)
    monkeypatch.setattr(crypto, "_dpapi_protect", lambda d: b"P" + d)
    monkeypatch.setattr(crypto, "_dpapi_unprotect", lambda b: b"something else")
    key, _ = _legacy_install(data_dir)
    SecureStorage()
    assert (data_dir / ".secure_key").read_bytes() == key


def test_corrupt_protected_file_is_not_replaced(data_dir, fake_dpapi, no_keyring):
    (data_dir / ".secure_key").write_bytes(crypto._DPAPI_MAGIC + b"garbage")
    with pytest.raises(RuntimeError):
        SecureStorage()
    assert (data_dir / ".secure_key").read_bytes() == crypto._DPAPI_MAGIC + b"garbage"


def test_protected_key_file_cannot_be_read_on_other_systems(data_dir, monkeypatch, no_keyring):
    monkeypatch.setattr(crypto, "_dpapi_available", lambda: False)
    (data_dir / ".secure_key").write_bytes(crypto._DPAPI_MAGIC + b"blob")
    with pytest.raises(RuntimeError):
        SecureStorage()
