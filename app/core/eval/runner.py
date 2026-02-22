"""Eval runner — runs eval datasets through a retrieval callable and collects metrics."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any

from app.core.eval.dataset import EvalDataset
from app.core.eval.metrics import RetrievalMetrics, compute_retrieval_metrics


@dataclass
class EvalResult:
    """Result for a single eval example."""

    query: str
    retrieved_ids: list[str]
    metrics: RetrievalMetrics | None = None
    error: str | None = None


@dataclass
class EvalReport:
    """Aggregated eval results."""

    dataset_name: str
    results: list[EvalResult] = field(default_factory=list)
    avg_precision: float = 0.0
    avg_recall: float = 0.0
    avg_mrr: float = 0.0

    def compute_aggregates(self) -> None:
        """Compute average metrics across all results with metrics."""
        with_metrics = [r for r in self.results if r.metrics]
        if not with_metrics:
            return
        n = len(with_metrics)
        self.avg_precision = sum(r.metrics.precision_at_k for r in with_metrics) / n
        self.avg_recall = sum(r.metrics.recall_at_k for r in with_metrics) / n
        self.avg_mrr = sum(r.metrics.mrr for r in with_metrics) / n


class EvalRunner:
    """Runs evaluation datasets through a retrieval callable.

    Args:
        retrieve_fn: async callable(query, collection_ids) -> list[str] of chunk_ids
        k: top-k for metrics computation
    """

    def __init__(
        self,
        retrieve_fn: Callable[..., Coroutine[Any, Any, list[str]]],
        k: int = 5,
    ) -> None:
        self.retrieve_fn = retrieve_fn
        self.k = k

    async def run(self, dataset: EvalDataset) -> EvalReport:
        """Run all examples and return an aggregated report."""
        results: list[EvalResult] = []

        for example in dataset.examples:
            try:
                retrieved_ids = await self.retrieve_fn(
                    example.query,
                    example.collection_ids,
                )
                metrics = None
                if example.expected_chunks:
                    metrics = compute_retrieval_metrics(
                        retrieved_ids, example.expected_chunks, self.k,
                    )
                results.append(EvalResult(
                    query=example.query,
                    retrieved_ids=retrieved_ids,
                    metrics=metrics,
                ))
            except Exception as e:
                results.append(EvalResult(
                    query=example.query,
                    retrieved_ids=[],
                    error=str(e),
                ))

        report = EvalReport(dataset_name=dataset.name, results=results)
        report.compute_aggregates()
        return report
