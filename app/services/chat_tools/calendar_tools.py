"""
Calendar tools for LLM tool-calling in chat.

These tools allow the LLM to:
- Parse user calendar requests
- Execute calendar operations (create/update/delete)
- List events
- Find events

The tools return structured responses that can be rendered as UI blocks
in the chat interface.
"""

from typing import List


def get_calendar_tools() -> List[dict]:
    """
    Get calendar tool definitions for LLM function calling.

    Returns OpenAI-compatible function calling definitions.
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "calendar_parse_command",
                "description": (
                    "Parse une demande calendrier de l'utilisateur en commande structurée. "
                    "Utilise pour toute action calendrier (créer, modifier, supprimer événement). "
                    "Gère automatiquement les expressions temporelles relatives ('demain', 'lundi prochain', etc.)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": (
                                "La demande de l'utilisateur en langage naturel. "
                                "Ex: 'Ajoute une visio avec Marie demain à 14h'"
                            ),
                        },
                        "timezone": {
                            "type": "string",
                            "description": "Timezone de l'utilisateur (défaut: Europe/Paris)",
                            "default": "Europe/Paris",
                        },
                        "assistant_id": {
                            "type": "string",
                            "description": "ID de l'assistant (optionnel)",
                            "format": "uuid",
                        },
                        "provider_preference": {
                            "type": "string",
                            "enum": ["google", "microsoft"],
                            "description": (
                                "Provider préféré si l'utilisateur le spécifie "
                                "('dans mon calendrier Google', etc.)"
                            ),
                        },
                    },
                    "required": ["text"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "calendar_execute_command",
                "description": (
                    "Exécute une commande calendrier validée (après parsing). "
                    "Crée, modifie ou supprime l'événement dans Google Calendar ou Microsoft Outlook. "
                    "IMPORTANT: Demander confirmation avant delete sauf si explicitement autorisé."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "object",
                            "description": "Commande structurée issue de calendar_parse_command",
                        },
                        "skip_confirmation": {
                            "type": "boolean",
                            "description": (
                                "True si l'utilisateur a confirmé explicitement. "
                                "False (défaut) pour demander confirmation avant delete."
                            ),
                            "default": False,
                        },
                        "assistant_id": {
                            "type": "string",
                            "description": "ID de l'assistant (optionnel)",
                            "format": "uuid",
                        },
                    },
                    "required": ["command"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "calendar_list_events",
                "description": (
                    "Liste les événements calendrier sur une plage de dates. "
                    "Utile pour résoudre l'ambiguïté ('décale ma réunion de demain' → lister les réunions) "
                    "ou afficher le planning."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "range_start": {
                            "type": "string",
                            "description": "Date/heure début (ISO 8601). Ex: '2026-02-17T00:00:00+01:00'",
                            "format": "date-time",
                        },
                        "range_end": {
                            "type": "string",
                            "description": "Date/heure fin (ISO 8601). Ex: '2026-02-20T23:59:59+01:00'",
                            "format": "date-time",
                        },
                        "provider": {
                            "type": "string",
                            "enum": ["google", "microsoft"],
                            "description": "Filtrer par provider (optionnel)",
                        },
                        "query": {
                            "type": "string",
                            "description": "Recherche texte dans les titres (optionnel)",
                        },
                    },
                    "required": ["range_start", "range_end"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "calendar_find_events",
                "description": (
                    "Recherche fuzzy d'événements par titre ou critères. "
                    "Plus flexible que list_events. Utile pour 'trouve ma réunion avec Paul'."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title_query": {
                            "type": "string",
                            "description": "Recherche dans le titre (case-insensitive)",
                        },
                        "range_start": {
                            "type": "string",
                            "description": "Date début (optionnel, défaut: -7 jours)",
                            "format": "date-time",
                        },
                        "range_end": {
                            "type": "string",
                            "description": "Date fin (optionnel, défaut: +30 jours)",
                            "format": "date-time",
                        },
                        "provider": {
                            "type": "string",
                            "enum": ["google", "microsoft"],
                            "description": "Filtrer par provider (optionnel)",
                        },
                    },
                    "required": [],
                },
            },
        },
    ]


# System prompt addition for calendar context
CALENDAR_SYSTEM_PROMPT_ADDITION = """
## Calendar Tools

Tu as accès à des outils calendrier pour aider l'utilisateur à gérer ses événements Google Calendar et Microsoft Outlook.

### Workflow recommandé :

1. **Parse la demande** : Utilise `calendar_parse_command` pour comprendre l'intention
   - Si clarification nécessaire → Pose une question claire OU utilise `calendar_list_events`
   - Si commande claire → Passe à l'étape 2

2. **Exécute l'action** : Utilise `calendar_execute_command`
   - IMPORTANT : Demande confirmation avant delete (sauf si "supprime définitivement")
   - Affiche le résultat avec un bloc UI approprié

3. **Disambiguation** : Si plusieurs événements correspondent
   - Utilise `calendar_list_events` pour afficher les options
   - Attends que l'utilisateur précise
   - Ou propose d'ouvrir le calendrier visuel

### Règles importantes :

- ✅ Toujours normaliser timezone (défaut: Europe/Paris)
- ✅ Parser expressions temporelles ("demain", "lundi prochain", "dans 2h")
- ✅ Durée par défaut : 30 minutes
- ✅ Visio : "visio", "meet", "teams" → add_video_conference=true
- ⚠️ Delete : TOUJOURS demander confirmation
- ⚠️ NE JAMAIS inventer d'emails participants
- ⚠️ Si ambiguïté → Clarifier AVANT d'exécuter

### Exemples :

**Création simple :**
User: "Ajoute une visio avec Paul demain à 14h"
→ calendar_parse_command(text="...")
→ calendar_execute_command(command={...})
→ Afficher: "✅ Visio créée: Rendez-vous avec Paul, demain 14h00, lien Meet: https://..."

**Disambiguation :**
User: "Décale ma réunion de demain"
→ calendar_list_events(range_start="2026-02-17T00:00", range_end="2026-02-18T00:00")
→ 3 réunions trouvées
→ "J'ai trouvé 3 réunions demain. Laquelle veux-tu déplacer ?"
→ Afficher blocs de choix

**Delete avec confirmation :**
User: "Supprime mon call de lundi"
→ calendar_parse_command → requires_confirmation=true
→ "Je vais supprimer 'Appel client' lundi 18 février à 10h. Confirmes-tu ?"
→ User: "oui"
→ calendar_execute_command(skip_confirmation=true)
→ "✅ Événement supprimé"
"""
