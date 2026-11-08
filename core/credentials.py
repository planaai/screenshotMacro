"""
core/credentials.py - Secure Credential & Model Configuration Storage.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import time
from typing import Optional, Tuple

from core.paths import get_user_data_dir
try:
    from core.security import encrypt_key, decrypt_key
except ImportError:
    def encrypt_key(plain_key: str) -> str:
        raise NotImplementedError("core.security.encrypt_key unavailable")

    def decrypt_key(encrypted_b64: str) -> str:
        raise NotImplementedError("core.security.decrypt_key unavailable")

logger = logging.getLogger("credentials")

DEFAULT_MODEL = "nvidia/nemotron-3.5-super-vl-120b-a12b"
ALT_MODEL = "mistralai/mistral-large-4-1t-a52b"
SUPPORTED_MODELS = (DEFAULT_MODEL, ALT_MODEL)
CREDENTIALS_FILE_NAME = "credentials.json"


def _extract_model_name(data: dict) -> str:
    """Extracts and validates model name from dictionary with fallback."""
    for key in ("selected_model", "model_name", "model"):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return DEFAULT_MODEL


def _extract_encrypted_key(data: dict) -> str:
    """Extracts encrypted key string from dictionary across known keys."""
    for key in ("api_key_encrypted", "api_key", "encrypted_key"):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


class CredentialManager:
    """Manages encrypted DPAPI credentials and selected NIM model persistence.

    Persists data to user_data/credentials.json, isolated from CoordinateService
    settings.json to prevent credential clobbering.
    """

    _global_lock = threading.RLock()

    def __init__(self, storage_path: Optional[str] = None) -> None:
        self._lock = threading.RLock()
        if storage_path is None:
            self.storage_path = os.path.join(get_user_data_dir(), CREDENTIALS_FILE_NAME)
        else:
            self.storage_path = os.path.abspath(storage_path)

        if os.path.basename(self.storage_path) == "settings.json":
            logger.warning(
                "CredentialManager configured with settings.json! "
                "CoordinateService.save_settings() overwrites this file. "
                "Use credentials.json to prevent clobbering."
            )

    def _read_file_content(self) -> Optional[dict]:
        """Reads and parses credentials JSON file."""
        if not os.path.exists(self.storage_path):
            return None
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return None
                data = json.loads(content)
                return data if isinstance(data, dict) else None
        except Exception as e:
            logger.warning(f"Failed to read credentials file: {e}")
            return None

    def _write_atomic(self, payload: dict) -> bool:
        """Atomically writes payload dict to storage_path using temp file and fsync."""
        temp_path = None
        try:
            target_dir = os.path.dirname(os.path.abspath(self.storage_path))
            if target_dir:
                os.makedirs(target_dir, exist_ok=True)

            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=target_dir,
                delete=False,
                prefix="cred_tmp_",
                suffix=".json",
            ) as tf:
                temp_path = tf.name
                json.dump(payload, tf, indent=2, ensure_ascii=False)
                tf.flush()
                os.fsync(tf.fileno())

            for attempt in range(3):
                try:
                    os.replace(temp_path, self.storage_path)
                    temp_path = None
                    break
                except PermissionError:
                    if attempt == 2:
                        raise
                    time.sleep(0.02)

            return True
        except Exception as e:
            logger.error(f"Failed to save credentials to {self.storage_path}: {e}")
            return False
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    def save_credentials(self, api_key: str, model_name: str = DEFAULT_MODEL) -> bool:
        """Encrypts API key and atomically saves credentials and model name."""
        with self._global_lock, self._lock:
            key_clean = str(api_key).strip() if api_key else ""
            model_clean = (str(model_name).strip() if model_name else "") or DEFAULT_MODEL

            encrypted_b64 = ""
            if key_clean:
                try:
                    encrypted_b64 = encrypt_key(key_clean)
                except Exception as e:
                    logger.error(f"Failed to encrypt API key: {e}")
                    return False

            payload = {
                "api_key_encrypted": encrypted_b64,
                "selected_model": model_clean,
            }
            return self._write_atomic(payload)

    def load_credentials(self) -> Tuple[str, str]:
        """Loads and decrypts credentials. Returns (plain_api_key, model_name)."""
        with self._global_lock, self._lock:
            data = self._read_file_content()
            if not data:
                return ("", DEFAULT_MODEL)

            model_name = _extract_model_name(data)
            encrypted_b64 = _extract_encrypted_key(data)
            if not encrypted_b64:
                return ("", model_name)

            try:
                plain_key = decrypt_key(encrypted_b64)
                return (plain_key, model_name)
            except Exception as e:
                logger.error(f"Failed to decrypt credentials: {e}")
                return ("", model_name)

    def has_key(self) -> bool:
        """Returns True if a valid non-empty decrypted API key is present."""
        with self._global_lock, self._lock:
            key, _ = self.load_credentials()
            return bool(key and key.strip())

    def clear_credentials(self) -> bool:
        """Atomically resets credentials file by removing it."""
        with self._global_lock, self._lock:
            if os.path.exists(self.storage_path):
                try:
                    os.remove(self.storage_path)
                    return True
                except OSError as e:
                    logger.error(f"Failed to remove credentials file: {e}")
                    return False
            return True
