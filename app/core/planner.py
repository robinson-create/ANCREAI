"""Planner — generates a structured plan for balanced/pro/exec profiles.

The planner asks the LLM to produce a lightweight JSON plan before executing
the tool loop. This gives the agent structure and ensures steps like
`ensure_source_coverage` are included.

Reactive profile skips planning entirely (straight-through).
"""

from __future__ import annotations

import json
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


# ── Plan models ─────────────────────────────────────────────────────


class PlanStepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


class PlanStep(BaseModel):
    """A single step in the agent plan."""

    id: str = Field(default_factory=lambda: str(uuid4())[:8])
    action: str  # e.g. "search_documents", "synthesize", "ensure_source_coverage"
    description: str
    tool: str | None = None  # Tool to call, if any
    status: PlanStepStatus = PlanStepStatus.PENDING
    result_summary: str | None = None


class AgentPlan(BaseModel):
    """Structured plan for a single agent run."""

    steps: list[PlanStep] = Field(default_factory=list)
    reasoning: str = ""
    profile: str = "balanced"

    def pending_steps(self) -> list[PlanStep]:
        return [s for s in self.steps if s.status == PlanStepStatus.PENDING]

    def current_step(self) -> PlanStep | None:
        pending = self.pending_steps()
        return pending[0] if pending else None

    def mark_step(self, step_id: str, status: PlanStepStatus, summary: str | None = None) -> None:
        for step in self.steps:
            if step.id == step_id:
                step.status = status
                if summary:
                    step.result_summary = summary
                return

    def is_complete(self) -> bool:
        return all(
            s.status in (PlanStepStatus.COMPLETED, PlanStepStatus.SKIPPED)
            for s in self.steps
        )

    def to_prompt_summary(self) -> str:
        """Format plan as a concise prompt section for the LLM."""
        lines = ["PLAN:"]
        for s in self.steps:
            marker = "✓" if s.status == PlanStepStatus.COMPLETED else "○"
            lines.append(f"  {marker} {s.action}: {s.description}")
            if s.result_summary:
                lines.append(f"    → {s.result_summary}")
        return "\n".join(lines)


# ── Plan generation ─────────────────────────────────────────────────

PLAN_SYSTEM_PROMPT = """\
Tu es un planificateur d'agent IA. Analyse la requête utilisateur et génère \
un plan d'exécution structuré en JSON.

Étapes disponibles :
- search_documents : Rechercher dans la base documentaire (outil: search_documents)
- synthesize : Synthétiser les résultats en réponse structurée (pas d'outil)
- ensure_source_coverage : Vérifier que chaque affirmation a une citation (pas d'outil)

Règles :
- Commence toujours par search_documents si la question nécessite des informations
- Termine toujours par ensure_source_coverage
- Pour les questions simples (salutations, questions sur toi), renvoie un plan minimal avec juste synthesize
- Maximum 5 étapes

Réponds UNIQUEMENT avec un JSON valide au format :
{
  "reasoning": "Explication courte du plan",
  "steps": [
    {"action": "search_documents", "description": "...", "tool": "search_documents"},
    {"action": "synthesize", "description": "...", "tool": null},
    {"action": "ensure_source_coverage", "description": "Vérifier les citations", "tool": null}
  ]
}"""


async def generate_plan(
    *,
    message: str,
    profile: str,
    available_tools: list[str] | None = None,
    conversation_summary: str | None = None,
) -> AgentPlan:
    """Generate a plan using the LLM.

    For balanced profile, generates a lightweight 2-3 step plan.
    For pro/exec, generates a more detailed plan.

    Falls back to a default plan on LLM failure.
    """
    from openai import AsyncOpenAI

    client = AsyncOpenAI(
        api_key=settings.mistral_api_key,
        base_url="https://api.mistral.ai/v1",
    )

    user_prompt = f"Requête utilisateur : {message}"
    if conversation_summary:
        user_prompt += f"\n\nContexte conversation : {conversation_summary}"
    if available_tools:
        user_prompt += f"\n\nOutils disponibles : {', '.join(available_tools)}"

    try:
        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": PLAN_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=500,
            temperature=0.1,
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content or "{}"
        data = json.loads(raw)

        steps = [
            PlanStep(
                action=s.get("action", "synthesize"),
                description=s.get("description", ""),
                tool=s.get("tool"),
            )
            for s in data.get("steps", [])
        ]

        plan = AgentPlan(
            steps=steps,
            reasoning=data.get("reasoning", ""),
            profile=profile,
        )

        logger.info(
            "plan_generated",
            profile=profile,
            step_count=len(steps),
            reasoning=plan.reasoning[:100],
        )

        return plan

    except Exception as e:
        logger.warning("plan_generation_failed", error=str(e))
        return _default_plan(profile)


def _default_plan(profile: str) -> AgentPlan:
    """Fallback plan when LLM planning fails."""
    steps = [
        PlanStep(
            action="search_documents",
            description="Rechercher dans la base documentaire",
            tool="search_documents",
        ),
        PlanStep(
            action="synthesize",
            description="Synthétiser les résultats",
        ),
        PlanStep(
            action="ensure_source_coverage",
            description="Vérifier que chaque affirmation a une citation",
        ),
    ]
    return AgentPlan(steps=steps, reasoning="Plan par défaut", profile=profile)


# ── Profile config ──────────────────────────────────────────────────

_PROFILE_MAX_ROUNDS: dict[str, int] = {
    "reactive": 1,
    "balanced": 3,
    "pro": 5,
    "exec": 5,
}


def max_tool_rounds(profile: str) -> int:
    """Return the maximum tool loop rounds for a profile."""
    return _PROFILE_MAX_ROUNDS.get(profile, 1)


def needs_planning(profile: str) -> bool:
    """Return True if the profile requires LLM planning."""
    return profile in ("balanced", "pro", "exec")
