"""Shared enums used across multiple models."""

from enum import Enum


class ContentScope(str, Enum):
    """Explicit scope for content: org-level, personal, or project."""

    ORG = "org"
    PERSONAL = "personal"
    PROJECT = "project"


class OrgRole(str, Enum):
    """Role of a member within an organization."""

    ADMIN = "admin"
    MEMBER = "member"


class MemberStatus(str, Enum):
    """Status of an org membership."""

    INVITED = "invited"
    ACTIVE = "active"
    INACTIVE = "inactive"
