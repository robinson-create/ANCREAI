"""Source coverage checker — ensures claims have citations.

Two levels:
1. Reactive heuristic: cheap regex check for numbers/dates/names without
   citations → appends disclaimer if detected.
2. Balanced/pro/exec: explicit `ensure_source_coverage` plan step that
   analyzes claims density vs citations count and flags unsupported claims.

No separate critic LLM — this is a lightweight post-processing step.
"""

from __future__ import annotations

import re

from app.core.logging import get_logger

logger = get_logger(__name__)


# ── Patterns that suggest factual claims ────────────────────────────

# Matches numbers with units, percentages, currency
_NUMBER_PATTERN = re.compile(
    r"\b\d[\d\s,.]*(?:%|€|EUR|USD|\$|M€|k€|millions?|milliards?|tonnes?|kg|km)\b",
    re.IGNORECASE,
)

# Matches dates (dd/mm/yyyy, yyyy-mm-dd, month year, etc.)
_DATE_PATTERN = re.compile(
    r"\b(?:\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}|"
    r"\d{4}[/\-.]\d{1,2}[/\-.]\d{1,2}|"
    r"(?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+\d{4})\b",
    re.IGNORECASE,
)

# Matches citation markers like [Source: ...] or [1], [2]
_CITATION_PATTERN = re.compile(
    r"\[(?:Source|Réf|source|ref).*?\]|\[\d+\]",
    re.IGNORECASE,
)

# Common disclaimer patterns already present
_DISCLAIMER_PATTERN = re.compile(
    r"(?:à confirmer|à vérifier|sous réserve|non vérifié|sans source)",
    re.IGNORECASE,
)


# ── Reactive heuristic ─────────────────────────────────────────────


def check_source_coverage_heuristic(
    response_text: str,
    citations_count: int,
) -> SourceCoverageResult:
    """Cheap heuristic check for the reactive profile.

    Counts factual-looking patterns (numbers, dates) and compares
    against citation count. Returns a result with optional disclaimer.
    """
    claims = _count_claims(response_text)
    has_disclaimer = bool(_DISCLAIMER_PATTERN.search(response_text))

    if claims == 0 or citations_count > 0 or has_disclaimer:
        return SourceCoverageResult(
            claims_count=claims,
            citations_count=citations_count,
            coverage_adequate=True,
        )

    # Claims detected but no citations and no disclaimer
    return SourceCoverageResult(
        claims_count=claims,
        citations_count=citations_count,
        coverage_adequate=False,
        disclaimer=(
            "\n\n---\n*Les données factuelles mentionnées ci-dessus "
            "sont issues du contexte disponible. Veuillez vérifier "
            "les chiffres et dates auprès de vos sources officielles.*"
        ),
    )


# ── Balanced/pro/exec coverage analysis ────────────────────────────


def analyze_source_coverage(
    response_text: str,
    citations: list[dict],
) -> SourceCoverageResult:
    """Detailed coverage analysis for balanced/pro/exec profiles.

    Used as the `ensure_source_coverage` plan step. Checks:
    - Claims density (factual patterns per paragraph)
    - Citation coverage ratio
    - Uncited paragraphs with factual content
    """
    claims = _count_claims(response_text)
    citations_count = len(citations)

    # Split into paragraphs for granular analysis
    paragraphs = [p.strip() for p in response_text.split("\n") if p.strip()]
    uncited_claims = []

    for para in paragraphs:
        para_claims = _count_claims(para)
        if para_claims > 0:
            has_citation = bool(_CITATION_PATTERN.search(para))
            has_disclaimer = bool(_DISCLAIMER_PATTERN.search(para))
            if not has_citation and not has_disclaimer:
                uncited_claims.append(para[:100])

    if not uncited_claims:
        return SourceCoverageResult(
            claims_count=claims,
            citations_count=citations_count,
            coverage_adequate=True,
        )

    # Coverage inadequate — provide details
    return SourceCoverageResult(
        claims_count=claims,
        citations_count=citations_count,
        coverage_adequate=False,
        uncited_paragraphs=uncited_claims,
        disclaimer=(
            "\n\n---\n*Certaines informations factuelles dans cette réponse "
            "n'ont pas pu être associées à une source documentaire. "
            "Les passages concernés sont à vérifier.*"
        ),
    )


# ── Result model ───────────────────────────────────────────────────


class SourceCoverageResult:
    """Result of a source coverage check."""

    __slots__ = (
        "claims_count",
        "citations_count",
        "coverage_adequate",
        "disclaimer",
        "uncited_paragraphs",
    )

    def __init__(
        self,
        claims_count: int = 0,
        citations_count: int = 0,
        coverage_adequate: bool = True,
        disclaimer: str | None = None,
        uncited_paragraphs: list[str] | None = None,
    ) -> None:
        self.claims_count = claims_count
        self.citations_count = citations_count
        self.coverage_adequate = coverage_adequate
        self.disclaimer = disclaimer
        self.uncited_paragraphs = uncited_paragraphs or []

    @property
    def needs_disclaimer(self) -> bool:
        return not self.coverage_adequate and self.disclaimer is not None


# ── Helpers ─────────────────────────────────────────────────────────


def _count_claims(text: str) -> int:
    """Count factual-looking patterns in text."""
    numbers = len(_NUMBER_PATTERN.findall(text))
    dates = len(_DATE_PATTERN.findall(text))
    return numbers + dates
