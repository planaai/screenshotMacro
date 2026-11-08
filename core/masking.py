"""
core/masking.py - Secret Key Masking and Redaction Module.
"""

from __future__ import annotations

import logging
import re
import sys
import traceback
from typing import Any, Optional

_NVAPI_PATTERN = re.compile(r"nvapi-[A-Za-z0-9_\-]+")
_BEARER_PATTERN = re.compile(r"(?i)\b(Bearer\s+)(?!nvapi-\*{4})(?!\*{4})([A-Za-z0-9_\-\.\+/=]+)")
_GLOBAL_SECRET_KEY: str = ""


def set_global_secret_key(key: str) -> None:
    """Sets process-wide secret key for automatic redaction."""
    global _GLOBAL_SECRET_KEY
    _GLOBAL_SECRET_KEY = key or ""


def get_global_secret_key() -> str:
    """Gets currently registered process-wide secret key."""
    return _GLOBAL_SECRET_KEY


def mask_api_key(key: str) -> str:
    """Returns masked key representation (e.g. 'nvapi-****' or '****')."""
    if not key or not isinstance(key, str):
        return ""
    stripped = key.strip()
    if not stripped:
        return ""
    if stripped.startswith("nvapi-"):
        return "nvapi-****"
    return "****"


def _mask_exact_key(text: str, secret: str) -> str:
    """Replaces exact occurrences of secret and stripped secret in text."""
    if not secret or not isinstance(secret, str) or not secret.strip():
        return text
    masked = mask_api_key(secret)
    if not masked:
        return text
    text = text.replace(secret, masked)
    stripped = secret.strip()
    if stripped and stripped != secret:
        text = text.replace(stripped, masked)
    return text


def mask_text(text: str, secret_key: str = "") -> str:
    """Sanitizes text by redacting API keys, Bearer tokens, and secret_key."""
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    if not text:
        return ""

    if secret_key:
        text = _mask_exact_key(text, secret_key)
    if _GLOBAL_SECRET_KEY:
        text = _mask_exact_key(text, _GLOBAL_SECRET_KEY)

    text = _NVAPI_PATTERN.sub(lambda m: mask_api_key(m.group(0)), text)
    text = _BEARER_PATTERN.sub(lambda m: f"{m.group(1)}{mask_api_key(m.group(2))}", text)
    return text


class SensitiveMaskFilter(logging.Filter):
    """Logging filter that redacts API keys and secrets from log records."""

    def __init__(self, secret_key: str = "", name: str = "") -> None:
        super().__init__(name=name)
        self.secret_key = secret_key

    def set_secret_key(self, secret_key: str) -> None:
        """Updates instance-specific secret key to mask."""
        self.secret_key = secret_key

    def _effective_secret(self) -> str:
        return self.secret_key or _GLOBAL_SECRET_KEY

    def _mask_arg(self, arg: Any, secret: str) -> Any:
        if isinstance(arg, (int, float, bool)) or arg is None:
            return arg
        s = str(arg)
        masked = mask_text(s, secret)
        return masked if masked != s else arg

    def _mask_args(self, args: Any, secret: str) -> Any:
        if isinstance(args, tuple):
            return tuple(self._mask_arg(a, secret) for a in args)
        if isinstance(args, list):
            return [self._mask_arg(a, secret) for a in args]
        if isinstance(args, dict):
            return {k: self._mask_arg(v, secret) for k, v in args.items()}
        return args

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            secret = self._effective_secret()

            if isinstance(record.msg, str):
                record.msg = mask_text(record.msg, secret)
            elif record.msg is not None:
                record.msg = mask_text(str(record.msg), secret)

            if record.args:
                record.args = self._mask_args(record.args, secret)

            if record.exc_info and not getattr(record, "exc_text", None):
                try:
                    record.exc_text = logging.Formatter().formatException(record.exc_info)
                except Exception:
                    try:
                        if isinstance(record.exc_info, tuple):
                            record.exc_text = "".join(traceback.format_exception(*record.exc_info))
                        elif isinstance(record.exc_info, BaseException):
                            record.exc_text = "".join(traceback.format_exception(record.exc_info))
                        else:
                            record.exc_text = str(record.exc_info)
                    except Exception:
                        record.exc_text = None

            if getattr(record, "exc_text", None) and isinstance(record.exc_text, str):
                record.exc_text = mask_text(record.exc_text, secret)

            if getattr(record, "stack_info", None) and isinstance(record.stack_info, str):
                record.stack_info = mask_text(record.stack_info, secret)
        except Exception:
            pass
        return True


class MaskingEmittingStream:
    """EmittingStream wrapper ensuring GUI log window receives only masked text."""

    def __init__(self, signal: Any, secret_key: str = "") -> None:
        self.signal = signal
        self.secret_key = secret_key

    def write(self, text: Any) -> None:
        if not text:
            return
        s = str(text)
        if not s.strip():
            return
        masked = mask_text(s, self.secret_key)
        if masked.strip():
            self.signal.emit(masked)

    def flush(self) -> None:
        pass


class MaskingStreamWrapper:
    """Stream wrapper sanitizing text before writing to underlying stream."""

    def __init__(self, stream: Any, secret_key: str = "") -> None:
        self.stream = stream
        self.secret_key = secret_key

    def write(self, text: Any) -> int:
        if not text:
            return 0
        s = str(text)
        masked = mask_text(s, self.secret_key)
        return self.stream.write(masked)

    def flush(self) -> None:
        if hasattr(self.stream, "flush"):
            self.stream.flush()

    def isatty(self) -> bool:
        return getattr(self.stream, "isatty", lambda: False)()


def attach_masking_filter(logger: Optional[logging.Logger] = None, secret_key: str = "") -> SensitiveMaskFilter:
    """Attaches SensitiveMaskFilter to target logger and all its existing handlers."""
    target_logger = logger if logger is not None else logging.getLogger()
    filt = SensitiveMaskFilter(secret_key=secret_key)
    target_logger.addFilter(filt)
    for handler in target_logger.handlers:
        handler.addFilter(filt)
    return filt
