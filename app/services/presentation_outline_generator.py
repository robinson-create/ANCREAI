"""Outline generator — now a thin wrapper around the slide generator's generate_outline().

Kept for backward compatibility with presentation.py imports.
The actual outline generation logic is in presentation_slide_generator.py.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Awaitable

from app.services.presentation_slide_generator import (
    PresentationOutline,
    SlideOutline,
    generate_outline,
)

logger = logging.getLogger(__name__)

# Re-export for backward compatibility
__all__ = [
    "PresentationOutline",
    "SlideOutline",
    "generate_outline",
]
