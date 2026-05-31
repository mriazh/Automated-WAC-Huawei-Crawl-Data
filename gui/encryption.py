"""Fernet encryption service using Windows MachineGuid as key source.

Provides machine-bound symmetric encryption for storing sensitive data
(e.g., passwords) in the config store. The encryption key is derived from
the Windows registry MachineGuid, making encrypted data non-portable
between machines.
"""

import base64
import hashlib
import winreg

from cryptography.fernet import Fernet, InvalidToken


class DecryptionError(Exception):
    """Raised when decryption fails due to key mismatch or data corruption."""


class EncryptionService:
    """Fernet encryption using Windows MachineGuid as key source."""

    def __init__(self) -> None:
        """Derive Fernet key from HKLM\\SOFTWARE\\Microsoft\\Cryptography\\MachineGuid."""
        machine_guid = self._read_machine_guid()
        key = self._derive_key(machine_guid)
        self._fernet = Fernet(key)

    def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext string, return base64-encoded ciphertext."""
        token = self._fernet.encrypt(plaintext.encode("utf-8"))
        return base64.urlsafe_b64encode(token).decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt base64-encoded ciphertext, return plaintext.

        Raises DecryptionError on failure (key mismatch or corruption).
        """
        try:
            token = base64.urlsafe_b64decode(ciphertext.encode("ascii"))
            plaintext_bytes = self._fernet.decrypt(token)
            return plaintext_bytes.decode("utf-8")
        except (InvalidToken, Exception) as e:
            raise DecryptionError(f"Decryption failed: {e}") from e

    @staticmethod
    def _read_machine_guid() -> str:
        """Read MachineGuid from Windows registry."""
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
            0,
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
        )
        try:
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
            return value
        finally:
            winreg.CloseKey(key)

    @staticmethod
    def _derive_key(machine_guid: str) -> bytes:
        """Derive a Fernet-compatible key from the MachineGuid string.

        Takes the SHA256 hash of the MachineGuid and base64url-encodes
        the first 32 bytes to produce a valid 32-byte Fernet key.
        """
        digest = hashlib.sha256(machine_guid.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest[:32])
