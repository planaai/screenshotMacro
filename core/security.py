"""
core/security.py - Windows DPAPI encryption/decryption with cross-platform fallback.
"""

from __future__ import annotations

import base64
import os
import sys
from typing import Optional

# Custom Exception Hierarchy
class SecurityError(Exception):
    """Base exception for security operations."""
    pass


class EncryptionError(SecurityError, RuntimeError):
    """Raised when encryption fails."""
    pass


class DecryptionError(SecurityError, ValueError):
    """Raised when decryption fails due to invalid format, corruption, or DPAPI failure."""
    pass


# DPAPI / ctypes bindings
HAS_DPAPI: bool = False
CryptProtectData = None
CryptUnprotectData = None
LocalFree = None
DATA_BLOB = None

if sys.platform == "win32":
    try:
        import ctypes
        from ctypes import wintypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [
                ("cbData", wintypes.DWORD),
                ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
            ]

        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32

        # CryptProtectData definition
        _CryptProtectData = crypt32.CryptProtectData
        _CryptProtectData.argtypes = [
            ctypes.POINTER(DATA_BLOB),          # pDataIn
            wintypes.LPCWSTR,                  # szDataDescr
            ctypes.POINTER(DATA_BLOB),          # pOptionalEntropy
            ctypes.c_void_p,                   # pvReserved
            ctypes.c_void_p,                   # pPromptStruct
            wintypes.DWORD,                    # dwFlags
            ctypes.POINTER(DATA_BLOB)           # pDataOut
        ]
        _CryptProtectData.restype = wintypes.BOOL

        # CryptUnprotectData definition
        _CryptUnprotectData = crypt32.CryptUnprotectData
        _CryptUnprotectData.argtypes = [
            ctypes.POINTER(DATA_BLOB),          # pDataIn
            ctypes.POINTER(wintypes.LPWSTR),    # ppszDataDescr
            ctypes.POINTER(DATA_BLOB),          # pOptionalEntropy
            ctypes.c_void_p,                   # pvReserved
            ctypes.c_void_p,                   # pPromptStruct
            wintypes.DWORD,                    # dwFlags
            ctypes.POINTER(DATA_BLOB)           # pDataOut
        ]
        _CryptUnprotectData.restype = wintypes.BOOL

        # LocalFree definition
        _LocalFree = kernel32.LocalFree
        _LocalFree.argtypes = [ctypes.c_void_p]
        _LocalFree.restype = ctypes.c_void_p

        CryptProtectData = _CryptProtectData
        CryptUnprotectData = _CryptUnprotectData
        LocalFree = _LocalFree
        HAS_DPAPI = True
    except (AttributeError, OSError):
        HAS_DPAPI = False

# Win32 DPAPI constants
CRYPTPROTECT_UI_FORBIDDEN = 0x01

# Mock fallback configuration
_MOCK_PREFIX: bytes = b"MOCK_DPAPI_v1:"
_MOCK_KEY: bytes = b"Plana_SE_Mock_DPAPI_Key_2026"
_force_fallback: bool = os.environ.get("PLANA_FORCE_MOCK_DPAPI", "").lower() in ("1", "true", "yes")


def set_force_fallback(enabled: bool) -> None:
    """Enable or disable mock fallback explicitly (useful for testing)."""
    global _force_fallback
    _force_fallback = enabled


def is_fallback_active() -> bool:
    """Return whether fallback mode is active (non-Windows or forced)."""
    return _force_fallback or not HAS_DPAPI


def _mock_encrypt(data: bytes) -> bytes:
    """Deterministic reversible obfuscation for offline/mock fallback."""
    key_len = len(_MOCK_KEY)
    xored = bytes(b ^ _MOCK_KEY[i % key_len] for i, b in enumerate(data))
    return _MOCK_PREFIX + xored


def _mock_decrypt(cipher: bytes) -> bytes:
    """Reverses deterministic fallback obfuscation."""
    if not cipher.startswith(_MOCK_PREFIX):
        raise DecryptionError("Corrupted mock payload: missing expected mock prefix header")
    payload = cipher[len(_MOCK_PREFIX):]
    key_len = len(_MOCK_KEY)
    return bytes(b ^ _MOCK_KEY[i % key_len] for i, b in enumerate(payload))


def _dpapi_encrypt(data_bytes: bytes) -> bytes:
    """Encrypts bytes using Windows DPAPI CryptProtectData."""
    import ctypes
    in_buf = ctypes.create_string_buffer(data_bytes)
    in_blob = DATA_BLOB(len(data_bytes), ctypes.cast(in_buf, ctypes.POINTER(ctypes.c_ubyte)))
    out_blob = DATA_BLOB()

    res = CryptProtectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(out_blob),
    )
    if not res:
        err = ctypes.GetLastError() if hasattr(ctypes, "GetLastError") else 0
        raise EncryptionError(f"CryptProtectData failed with error code {err}")

    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        if out_blob.pbData and LocalFree is not None:
            LocalFree(out_blob.pbData)


def _dpapi_decrypt(cipher_bytes: bytes) -> bytes:
    """Decrypts bytes using Windows DPAPI CryptUnprotectData."""
    import ctypes
    in_buf = ctypes.create_string_buffer(cipher_bytes)
    in_blob = DATA_BLOB(len(cipher_bytes), ctypes.cast(in_buf, ctypes.POINTER(ctypes.c_ubyte)))
    out_blob = DATA_BLOB()

    res = CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(out_blob),
    )
    if not res:
        err = ctypes.GetLastError() if hasattr(ctypes, "GetLastError") else 0
        raise DecryptionError(f"CryptUnprotectData failed with error code {err}")

    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData) if out_blob.cbData else b""
    finally:
        if out_blob.pbData and LocalFree is not None:
            LocalFree(out_blob.pbData)


def encrypt_key(plain_key: str) -> str:
    """
    Encrypts plaintext string via Windows DPAPI (CryptProtectData) or mock fallback.
    Returns base64 encoded string.
    """
    if not isinstance(plain_key, str):
        raise TypeError(f"plain_key must be str, got {type(plain_key).__name__}")

    data_bytes = plain_key.encode("utf-8")

    if is_fallback_active():
        raw_cipher = _mock_encrypt(data_bytes)
    else:
        raw_cipher = _dpapi_encrypt(data_bytes)

    return base64.b64encode(raw_cipher).decode("ascii")


def decrypt_key(encrypted_b64: str) -> str:
    """
    Decrypts base64 DPAPI or mock fallback ciphertext.
    Returns plaintext string.
    """
    if encrypted_b64 is None or encrypted_b64 == "":
        return ""
    if not isinstance(encrypted_b64, str):
        raise TypeError(f"encrypted_b64 must be str, got {type(encrypted_b64).__name__}")

    try:
        raw_cipher = base64.b64decode(encrypted_b64, validate=True)
    except Exception as e:
        raise DecryptionError(f"Invalid base64 payload: {e}") from e

    if raw_cipher.startswith(_MOCK_PREFIX):
        plain_bytes = _mock_decrypt(raw_cipher)
    else:
        if is_fallback_active():
            raise DecryptionError(
                "Cannot decrypt Windows DPAPI payload: Windows DPAPI is not available on this platform"
            )
        plain_bytes = _dpapi_decrypt(raw_cipher)

    try:
        return plain_bytes.decode("utf-8")
    except UnicodeDecodeError as e:
        raise DecryptionError(f"Decrypted payload is not valid UTF-8: {e}") from e
