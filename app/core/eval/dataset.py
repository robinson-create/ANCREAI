"""Eval dataset — load JSONL eval datasets."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class EvalExample:
    """Single evaluation example."""

    query: str
    expected_chunks: list[str] | None = None
    expected_answer: str | None = None
    collection_ids: list[str] | None = None
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class EvalDataset:
    """Collection of evaluation examples."""

    name: str
    examples: list[EvalExample]

    @classmethod
    def from_jsonl(cls, path: str | Path, name: str | None = None) -> EvalDataset:
        """Load dataset from JSONL file."""
        path = Path(path)
        examples: list[EvalExample] = []
        with path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                examples.append(EvalExample(
                    query=data["query"],
                    expected_chunks=data.get("expected_chunks"),
                    expected_answer=data.get("expected_answer"),
                    collection_ids=data.get("collection_ids"),
                    tags=data.get("tags", []),
                    metadata=data.get("metadata", {}),
                ))
        return cls(name=name or path.stem, examples=examples)

    def filter_by_tag(self, tag: str) -> EvalDataset:
        """Return a new dataset containing only examples with the given tag."""
        return EvalDataset(
            name=f"{self.name}[{tag}]",
            examples=[e for e in self.examples if tag in e.tags],
        )

    def __len__(self) -> int:
        return len(self.examples)
