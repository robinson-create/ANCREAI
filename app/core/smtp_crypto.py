"""Encryption for SMTP passwords stored in mail_accounts.smtp_config."""

from __future__ import annotations

import logging

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)


def _get_fernet() -> Fernet | None:
    """Create Fernet instance from settings. Returns None if key not configured."""
    from app.config import get_settings

    key = get_settings().smtp_encryption_key
    if not key or len(key) < 32:
        logger.warning("SMTP_ENCRYPTION_KEY not configured or too short")
        return None

    try:
        return Fernet(key.encode("ascii"))
    except Exception as e:
        logger.warning("Invalid SMTP_ENCRYPTION_KEY: %s", e)
        return None


def encrypt_smtp_password(plain: str) -> str | None:
    """Encrypt a plain SMTP password. Returns None if encryption not available."""
    f = _get_fernet()
    if not f:
        return None
    return f.encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt_smtp_password(encrypted: str) -> str | None:
    """Decrypt an encrypted SMTP password. Returns None on failure."""
    f = _get_fernet()
    if not f:
        return None
    try:
        return f.decrypt(encrypted.encode("ascii")).decode("utf-8")
    except InvalidToken:
        logger.warning("Failed to decrypt SMTP password (invalid token)")
        return None


def generate_smtp_encryption_key() -> str:
    """Generate a new Fernet key for SMTP password encryption (for .env)."""
    return Fernet.generate_key().decode("ascii")
