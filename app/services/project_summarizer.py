"""Project conversation summarizer service."""

import logging

from openai import AsyncOpenAI

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

SUMMARY_PROMPT = """Tu es un assistant de synthèse de projet. Résume cette conversation de projet en extrayant les informations clés de manière structurée.

Format de sortie (en utilisant la même langue que la conversation) :

## Objectifs
- Les objectifs identifiés dans la conversation

## Contraintes
- Les contraintes ou limitations mentionnées

## Décisions
- Les décisions prises pendant la conversation

## Données importantes
- Chiffres, dates, noms, références clés

## Hypothèses
- Les hypothèses ou suppositions formulées

Règles :
- Pas de blabla narratif, uniquement des bullet points factuels
- Utilise la même langue que la conversation
- Si une section est vide, l'omettre
- Maximum 500 mots"""


async def summarize_conversation(transcript: str) -> str:
    """Generate a structured summary of a conversation transcript.

    Args:
        transcript: The conversation transcript to summarize.

    Returns:
        A structured summary string.
    """
    client = AsyncOpenAI(
        api_key=settings.mistral_api_key,
        base_url="https://api.mistral.ai/v1",
    )

    response = await client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": SUMMARY_PROMPT},
            {"role": "user", "content": transcript},
        ],
        temperature=0.3,
        max_tokens=2000,
    )

    return response.choices[0].message.content or ""
