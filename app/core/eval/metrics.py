"""Retrieval and answer quality metrics."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RetrievalMetrics:
    """Aggregated retrieval metrics for a single example."""

    precision_at_k: float
    recall_at_k: float
    mrr: float
    k: int


def precision_at_k(retrieved: list[str], relevant: list[str], k: int) -> float:
    """Precision@K: fraction of top-k retrieved that are relevant."""
    top_k = retrieved[:k]
    if not top_k:
        return 0.0
    relevant_set = set(relevant)
    hits = sum(1 for r in top_k if r in relevant_set)
    return hits / len(top_k)


def recall_at_k(retrieved: list[str], relevant: list[str], k: int) -> float:
    """Recall@K: fraction of relevant items found in top-k."""
    if not relevant:
        return 1.0
    top_k = set(retrieved[:k])
    hits = sum(1 for r in relevant if r in top_k)
    return hits / len(relevant)


def mean_reciprocal_rank(retrieved: list[str], relevant: list[str]) -> float:
    """MRR: 1/rank of first relevant result."""
    relevant_set = set(relevant)
    for i, r in enumerate(retrieved, 1):
        if r in relevant_set:
            return 1.0 / i
    return 0.0


def compute_retrieval_metrics(
    retrieved: list[str],
    relevant: list[str],
    k: int = 5,
) -> RetrievalMetrics:
    """Compute all retrieval metrics for a single example."""
    return RetrievalMetrics(
        precision_at_k=precision_at_k(retrieved, relevant, k),
        recall_at_k=recall_at_k(retrieved, relevant, k),
        mrr=mean_reciprocal_rank(retrieved, relevant),
        k=k,
    )


# ── Answer metrics ────────────────────────────────────────────────


def exact_match(predicted: str, expected: str) -> bool:
    """Case-insensitive exact match after stripping whitespace."""
    return predicted.strip().lower() == expected.strip().lower()


def fuzzy_match(predicted: str, expected: str, threshold: float = 0.8) -> bool:
    """Token overlap ratio against expected."""
    pred_tokens = set(predicted.strip().lower().split())
    exp_tokens = set(expected.strip().lower().split())
    if not exp_tokens:
        return True
    overlap = len(pred_tokens & exp_tokens)
    return (overlap / len(exp_tokens)) >= threshold
