# Intégration Calendar Tools dans ChatService

## 📋 Vue d'ensemble

Ce guide explique comment intégrer les calendar tools dans le `ChatService` existant pour permettre au LLM de gérer les événements calendrier via conversation.

## 🎯 Objectif

Ajouter 4 nouveaux tools au ChatService :
- `calendar_parse_command` : Parse texte → commande structurée
- `calendar_execute_command` : Exécute commande (create/update/delete)
- `calendar_list_events` : Liste événements sur une plage
- `calendar_find_events` : Recherche fuzzy d'événements

## 📁 Fichiers créés

✅ `app/services/chat_tools/__init__.py`
✅ `app/services/chat_tools/calendar_tools.py` - Définitions des tools
✅ `app/services/chat_tools/calendar_handlers.py` - Handlers d'exécution

## 🔧 Modifications à apporter

### 1. Importer les calendar tools dans `app/services/chat.py`

**Ligne ~16** (après les autres imports) :

```python
from app.services.chat_tools.calendar_tools import get_calendar_tools, CALENDAR_SYSTEM_PROMPT_ADDITION
from app.services.chat_tools.calendar_handlers import (
    is_calendar_tool,
    execute_calendar_tool,
)
```

### 2. Ajouter les calendar block types

**Ligne ~149** (après `_TOOL_NAME_TO_BLOCK_TYPE`) :

```python
# Map calendar tool names → block types for the frontend
_CALENDAR_TOOL_TO_BLOCK_TYPE = {
    "calendar_parse_command": None,  # Returns command, not a block
    "calendar_execute_command": "calendar_event_card",  # Or other calendar blocks
    "calendar_list_events": "calendar_event_choices",
    "calendar_find_events": "calendar_event_choices",
}
```

### 3. Modifier `_build_tools_list` pour inclure calendar tools

**Ligne ~227** (méthode `_build_tools_list`) :

```python
def _build_tools_list(self, integrations: list[dict] | None = None) -> list[dict]:
    """Build the full tools list: block tools + calendar tools + integration tools."""
    tools = list(BLOCK_TOOLS)

    # Add calendar tools
    tools.extend(get_calendar_tools())

    # Add integration tools
    if integrations:
        for integration in integrations:
            provider = integration["provider"]
            tools.extend(get_tools_for_provider(provider))

    return tools
```

### 4. Modifier `_build_system_prompt` pour inclure calendar instructions

**Ligne ~197** (méthode `_build_system_prompt`) :

```python
def _build_system_prompt(
    self,
    custom_prompt: str | None,
    context: str,
    integrations: list[dict] | None = None,
) -> str:
    """Build system prompt with context, calendar, and integration instructions."""
    # ... existing code ...

    prompt += BLOCK_INSTRUCTIONS
    prompt += CALENDAR_SYSTEM_PROMPT_ADDITION  # ← ADD THIS
    prompt += _build_integration_instructions(integrations or [])

    return prompt
```

### 5. Modifier `_is_block_tool` pour inclure calendar tools

**Ligne ~236** (méthode `_is_block_tool`) :

```python
def _is_block_tool(self, tool_name: str) -> bool:
    """Check if a tool name is a block (UI) tool vs an integration/calendar tool."""
    return (
        tool_name in _TOOL_NAME_TO_BLOCK_TYPE
        or tool_name in _CALENDAR_TOOL_TO_BLOCK_TYPE
    )
```

### 6. Ajouter le handler calendar dans la boucle tool-calling (NON-STREAMING)

**Ligne ~380-410** (dans la méthode `chat`, boucle tool-calling) :

Après le bloc qui gère les integration tools, ajouter :

```python
# Handle calendar tools
elif is_calendar_tool(tc.function.name):
    logger.info("Calling calendar tool: %s", tc.function.name)

    try:
        args = json.loads(tc.function.arguments)
    except json.JSONDecodeError:
        args = {}

    result = await execute_calendar_tool(
        tool_name=tc.function.name,
        arguments=args,
        db=db,
        current_user={"tenant_id": tenant_id, "user_id": "CURRENT_USER_ID"},  # TODO: Get from context
    )

    # Emit calendar block
    result_data = json.loads(result)
    if result_data.get("type") in ["calendar_event_card", "calendar_event_choices", "calendar_connect_cta"]:
        all_blocks.append({
            "id": str(uuid4()),
            "type": result_data["type"],
            "payload": result_data,
        })

    messages.append({
        "role": "tool",
        "tool_call_id": tc.id,
        "content": result,
    })
```

### 7. Ajouter le handler calendar dans la boucle tool-calling (STREAMING)

**Ligne ~590-620** (dans la méthode `chat_stream`, boucle tool-calling) :

Après le bloc qui gère les integration tools, ajouter :

```python
# Handle calendar tools
elif is_calendar_tool(tc_data["name"]):
    logger.info("Calling calendar tool (streaming): %s", tc_data["name"])

    # Emit tool_call block (in progress)
    yield ChatStreamEvent(event="block", data={
        "id": str(uuid4()),
        "type": "tool_call",
        "payload": {
            "provider": "calendar",
            "tool": tc_data["name"],
            "status": "calling",
        },
    })

    try:
        args = json.loads(tc_data["arguments"])
    except json.JSONDecodeError:
        args = {}

    result = await execute_calendar_tool(
        tool_name=tc_data["name"],
        arguments=args,
        db=db,
        current_user={"tenant_id": tenant_id, "user_id": "CURRENT_USER_ID"},  # TODO: Get from context
    )

    # Parse result and emit appropriate block
    result_data = json.loads(result)
    if result_data.get("type") in ["calendar_event_card", "calendar_event_choices", "calendar_connect_cta", "calendar_clarification"]:
        yield ChatStreamEvent(event="block", data={
            "id": str(uuid4()),
            "type": result_data["type"],
            "payload": result_data,
        })

    messages.append({
        "role": "tool",
        "tool_call_id": tc_data["id"],
        "content": result,
    })
```

## 🎨 Blocs UI Frontend

Les calendar tools retournent les types de blocs suivants :

| Type de bloc | Composant React | Description |
|--------------|-----------------|-------------|
| `calendar_event_card` | `CalendarEventCard.tsx` | Affiche un événement créé/modifié |
| `calendar_event_choices` | `CalendarEventChoices.tsx` | Liste d'événements pour disambiguation |
| `calendar_connect_cta` | `CalendarConnectProviderCTA.tsx` | CTA pour connecter calendrier |
| `calendar_clarification` | (texte simple) | Question de clarification |
| `calendar_confirmation` | (texte simple + boutons) | Demande confirmation avant delete |

### Enregistrement des composants dans le chat

**Fichier frontend à modifier** : `frontend/src/components/chat/MessageBlocks.tsx` (ou équivalent)

```tsx
import { CalendarEventCard } from '@/components/blocks/calendar/CalendarEventCard';
import { CalendarEventChoices } from '@/components/blocks/calendar/CalendarEventChoices';
import { CalendarConnectProviderCTA } from '@/components/blocks/calendar/CalendarConnectProviderCTA';

// Dans le switch/case des block types :
case 'calendar_event_card':
  return <CalendarEventCard event={block.payload.event} message={block.payload.message} />;

case 'calendar_event_choices':
  return (
    <CalendarEventChoices
      events={block.payload.events}
      message={block.payload.message}
      onSelect={(eventId) => {
        // TODO: Re-submit with selected event ID
      }}
      onOpenCalendar={() => {
        // TODO: Open calendar modal
      }}
    />
  );

case 'calendar_connect_cta':
  return <CalendarConnectProviderCTA />;
```

## 🧪 Test manuel

Une fois intégré, tester avec ces messages :

1. **Création simple** :
   ```
   Ajoute une visio avec Paul demain à 14h
   ```
   → Devrait créer l'événement et afficher `CalendarEventCard`

2. **Disambiguation** :
   ```
   Décale ma réunion de demain
   ```
   → Devrait lister les réunions et afficher `CalendarEventChoices`

3. **Suppression avec confirmation** :
   ```
   Supprime mon call de lundi
   ```
   → Devrait demander confirmation avant delete

4. **Pas de provider connecté** :
   ```
   Ajoute un événement
   ```
   → Devrait afficher `CalendarConnectProviderCTA`

## ⚠️ Points d'attention

1. **User ID context** : Remplacer `"CURRENT_USER_ID"` par le vrai user ID depuis le contexte auth
2. **DB session** : S'assurer que `db` est passé correctement dans les méthodes streaming
3. **Error handling** : Gérer gracefully les erreurs Nango (token expiré, etc.)
4. **Rate limiting** : Considérer rate limiting pour éviter spam d'API calls

## 📚 Ressources

- Définitions tools : `app/services/chat_tools/calendar_tools.py`
- Handlers : `app/services/chat_tools/calendar_handlers.py`
- Composants UI : `frontend/src/components/blocks/calendar/`
- Services calendar : `app/services/calendar/`

## ✅ Checklist d'intégration

- [ ] Imports ajoutés dans `chat.py`
- [ ] `_build_tools_list` modifié
- [ ] `_build_system_prompt` modifié
- [ ] `_is_block_tool` modifié
- [ ] Handler calendar ajouté dans `chat()` (non-streaming)
- [ ] Handler calendar ajouté dans `chat_stream()` (streaming)
- [ ] Composants UI enregistrés dans MessageBlocks
- [ ] Tests manuels effectués
- [ ] User context correctement passé

---

**Une fois ces modifications appliquées, les calendar tools seront pleinement intégrés dans le chat ! 🎉**
