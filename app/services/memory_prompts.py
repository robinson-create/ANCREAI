"""Prompts for structured memory extraction and consolidation (JSON format)."""

MEMORY_EXTRACTION_PROMPT = """\
Tu es un extracteur de mémoire structurée. À partir de cette conversation, \
extrais uniquement les informations exploitables en JSON structuré.

Format de sortie STRICT (JSON valide, pas de texte autour) :

{
  "goals": ["objectif 1", "objectif 2"],
  "decisions": ["décision 1", "décision 2"],
  "constraints": ["contrainte 1", "contrainte 2"],
  "facts": ["chiffre/date/nom/montant/référence 1", "..."],
  "hypotheses": ["hypothèse 1", "..."],
  "preferences": ["préférence stable 1", "..."]
}

Règles strictes :
- Chaque entrée est une phrase courte et autonome (compréhensible hors contexte)
- Omets les catégories vides (pas de listes vides)
- Pas de narration, pas de résumé "gentil"
- Uniquement des faits exploitables
- Utilise la même langue que la conversation
- Maximum 30 entrées au total
- Si la conversation ne contient aucune information exploitable, réponds exactement : {}
"""

MEMORY_CONSOLIDATION_PROMPT = """\
Tu es un consolidateur de mémoire. Voici plusieurs mémoires structurées \
(format JSON) issues de conversations différentes d'un même utilisateur.

Ta tâche :
1. Fusionner les entrées similaires ou redondantes
2. Résoudre les conflits (garder la version la plus récente = dernier résumé)
3. Supprimer les doublons exacts
4. Produire une mémoire consolidée, compacte et non redondante

Format de sortie STRICT (JSON valide, pas de texte autour) :

{
  "goals": ["..."],
  "decisions": ["..."],
  "constraints": ["..."],
  "facts": ["..."],
  "hypotheses": ["..."],
  "preferences": ["..."]
}

Règles strictes :
- Omets les catégories vides
- Chaque entrée est une phrase courte et autonome
- Pas de narration
- En cas de conflit entre ancienne et nouvelle info, garder la nouvelle
- Maximum 50 entrées au total
- Utilise la même langue que les résumés d'origine
"""
