"""Mail integration services."""

from app.services.mail.factory import get_mail_provider

__all__ = ["get_mail_provider"]
