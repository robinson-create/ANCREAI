# Plan : Corriger la génération de slides et améliorer le rendu

## Contexte

La migration vers le pipeline JSON template (3 étapes LLM) est fonctionnelle pour la slide d'intro, mais 3 bugs critiques empêchent les autres slides de se rendre correctement :

1. **Bug critique : session DB partagée en parallèle** — `asyncio.gather()` exécute 4 LLM calls concurrents via `_tracked_llm_call()` qui font tous `db.add()` + `db.flush()` sur la MÊME session SQLAlchemy. Résultat : seule la slide 0 (intro) réussit, les 3 autres restent "running" avec 0 tokens et le fallback silencieux produit `{"title": "Title", "bulletPoints": []}`.

2. **Bug CSS** — `--card-color` mappé sur `accent` (#EFEBEA beige) au lieu d'un gris clair, ce qui rend les cartes quasi invisibles sur fond blanc.

3. **Pas de styling visuel** — Les templates React ont les bonnes structures mais aucune variation visuelle (pas d'images, icônes sans couleur, pas de bordures visibles).

## Problèmes identifiés (preuves DB)

```
Run 0: outline      → SUCCESS (tokens=2216→932, 16s)
Run 1: layouts       → SUCCESS (tokens=1450→21,  0.7s)
Run 2: slide 0 intro → SUCCESS (tokens=1192→274, 5.5s)
Run 3: slide 1       → STUCK "running" (tokens=0→0)  ← DB session crash
Run 4: slide 2       → STUCK "running" (tokens=0→0)  ← DB session crash
Run 5: slide 3       → STUCK "running" (tokens=0→0)  ← DB session crash

Slide 1 content_json: {"title": "Title", "bulletPoints": []}  ← FALLBACK
```

## Plan d'implémentation

### Étape 1 : Corriger la génération parallèle (bug critique)

**Fichier : `app/services/presentation.py`**

Le problème est dans `generate_slides()` ligne ~447 : le `llm_call` closure capture `db` (session partagée). Quand `generate_full_deck()` lance `asyncio.gather()` pour les slides, chaque coroutine fait `db.flush()` en parallèle → corruption.

**Solution** : Séparer le tracking DB de l'appel LLM. Dans le `llm_call` closure, ne PAS utiliser `_tracked_llm_call()`. À la place, faire l'appel API directement et tracker après coup.

```python
# Dans generate_slides(), remplacer le llm_call closure :
async def llm_call(sys_prompt: str, usr_prompt: str) -> str:
    """LLM call without DB tracking — safe for parallel use."""
    response = await self.client.chat.completions.create(
        model=self.slide_model,
        max_tokens=4096,
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": usr_prompt},
        ],
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content or ""
    logger.info(
        "LLM call: tokens=%d→%d",
        response.usage.prompt_tokens if response.usage else 0,
        response.usage.completion_tokens if response.usage else 0,
    )
    return content
```

On garde `_tracked_llm_call()` uniquement pour les appels séquentiels (outline, layouts) qui n'ont pas ce problème de concurrence. Pour la step 3 (content per slide), on utilise le `llm_call` léger ci-dessus.

### Étape 2 : Corriger le mapping CSS variables

**Fichier : `frontend/src/components/presentation/SlideRenderer.tsx`**

Dans `buildThemeCSSVars()`, corriger :
- `--card-color` : `theme.colors.accent` → calcul dynamique d'un gris très clair basé sur le background
- Ajouter `--accent-color` : pour les éléments décoratifs (actuellement manquant)

```typescript
// Calculer une couleur de carte légèrement différente du fond
"--card-color": `color-mix(in srgb, ${theme.colors.background} 92%, ${theme.colors.text})`,
"--accent-color": theme.colors.accent,
```

### Étape 3 : Améliorer la qualité de rendu des templates

**Fichiers : `frontend/src/components/presentation/templates/*.tsx`**

Corrections mineures sur les templates existants pour améliorer le rendu :
- **Tous les templates** : S'assurer que les fallbacks CSS sont cohérents
- **BulletWithIconsSlideLayout** : Vérifier que les icônes utilisent `--primary-color` pour la couleur
- **MetricsSlideLayout** : Vérifier le contraste des cartes métriques
- **ChartWithBulletsSlideLayout** : S'assurer que le chart est visible même sans données

### Étape 4 : Résolution des icônes (fix backend)

**Fichier : `app/services/presentation.py` (`_resolve_icons`)**

Actuellement, `_resolve_icons` cherche `__icon_query__` dans le content_json et ajoute `icon_name`. Mais les templates frontend attendent le champ `icon` (pas `icon_name`).

Vérifier et aligner :
- Backend : `sub_value["icon_name"] = icons[0]` → `sub_value["icon"] = icons[0]` si c'est ce que les templates attendent
- OU templates : accéder `bullet.icon_name` au lieu de `bullet.icon`

### Étape 5 : Nettoyage du purpose dans _tracked_llm_call

**Fichier : `app/services/presentation.py`**

Le `llm_call` closure utilise `purpose=RunPurpose.OUTLINE.value` pour TOUS les appels (outline, layout, content). C'est trompeur dans les logs. Comme on sépare les appels (étape 1), on peut donner un purpose correct pour outline et layout.

## Fichiers à modifier

| Fichier | Modification |
|---------|-------------|
| `app/services/presentation.py` | Séparer llm_call du tracking DB pour la génération parallèle |
| `frontend/src/components/presentation/SlideRenderer.tsx` | Fix `--card-color` CSS variable |
| `app/services/presentation.py` (_resolve_icons) | Aligner nom de champ icône (icon vs icon_name) |

## Vérification

1. Relancer serveur + worker
2. Créer une nouvelle présentation (4+ slides)
3. Vérifier dans les logs :
   - `LLM call: tokens=X→Y` pour CHAQUE slide (pas juste la première)
   - `Full deck: complete, 4 slides, layouts=[...]`
   - Pas de `FALLBACK` dans les logs
4. Vérifier en DB : `content_json` a du vrai contenu (pas `"title": "Title"`)
5. Vérifier dans le frontend :
   - Toutes les slides ont du contenu (pas juste "Slide")
   - Les cartes sont visibles (pas invisibles sur fond blanc)
   - Console : pas de `[SlideTemplate] Unknown layout`
