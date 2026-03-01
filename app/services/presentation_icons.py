"""Lucide icon registry — single source of truth for presentation icons.

The LLM generates semantic queries (e.g. "croissance", "rocket").
This module resolves them to exact Lucide icon names.
The frontend renders ONLY resolved icon_name values.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ── Icon sizing & role policy ──


ICON_SIZES: dict[str, dict[str, int | float]] = {
    "inline": {"size": 16, "stroke_width": 2.0},
    "card": {"size": 24, "stroke_width": 1.75},
    "section": {"size": 32, "stroke_width": 1.5},
    "hero": {"size": 48, "stroke_width": 1.25},
}

VALID_ICON_ROLES = {"inline", "card", "section", "hero"}


# ── Icon entry ──


@dataclass(frozen=True)
class IconEntry:
    name: str  # Exact Lucide component name: "Rocket", "Shield", "BarChart3"
    aliases: tuple[str, ...]  # Semantic search terms (lowercase, multi-language)
    category: str  # business | tech | process | people | data | nature | ui


# ── Registry — ~80 curated icons ──

_ENTRIES: list[IconEntry] = [
    # ── Business ──
    IconEntry("Target", ("target", "cible", "objectif", "goal", "ambition"), "business"),
    IconEntry("Briefcase", ("business", "briefcase", "entreprise", "travail", "work", "valise"), "business"),
    IconEntry("DollarSign", ("money", "dollar", "prix", "budget", "coût", "revenue", "chiffre d'affaires", "argent"), "business"),
    IconEntry("Euro", ("euro", "monnaie", "currency", "devise"), "business"),
    IconEntry("TrendingUp", ("growth", "croissance", "trending", "hausse", "progression", "augmentation"), "business"),
    IconEntry("TrendingDown", ("decline", "baisse", "déclin", "diminution", "chute"), "business"),
    IconEntry("Award", ("award", "prix", "récompense", "excellence", "qualité", "trophy", "trophée"), "business"),
    IconEntry("Globe", ("global", "world", "monde", "international", "worldwide", "planète"), "business"),
    IconEntry("Megaphone", ("marketing", "announce", "communication", "promotion", "campagne", "publicité"), "business"),
    IconEntry("Handshake", ("partnership", "partenariat", "accord", "deal", "collaboration"), "business"),
    IconEntry("Building2", ("company", "entreprise", "société", "siège", "bureau", "office"), "business"),
    IconEntry("Store", ("store", "magasin", "boutique", "commerce", "retail"), "business"),
    IconEntry("Receipt", ("invoice", "facture", "transaction", "paiement", "receipt"), "business"),
    IconEntry("PiggyBank", ("savings", "épargne", "économies", "investissement", "piggy"), "business"),
    IconEntry("Crown", ("premium", "leader", "roi", "top", "best", "first"), "business"),

    # ── Tech ──
    IconEntry("Rocket", ("rocket", "launch", "fusée", "innovation", "démarrage", "startup", "lancement"), "tech"),
    IconEntry("Zap", ("fast", "rapide", "performance", "speed", "éclair", "énergie", "puissance"), "tech"),
    IconEntry("Shield", ("shield", "security", "sécurité", "protection", "défense", "bouclier"), "tech"),
    IconEntry("Settings", ("settings", "config", "paramètres", "options", "réglages", "engrenage"), "tech"),
    IconEntry("Code", ("code", "développement", "programmation", "dev", "technique"), "tech"),
    IconEntry("Cpu", ("cpu", "processeur", "hardware", "machine", "serveur"), "tech"),
    IconEntry("Cloud", ("cloud", "nuage", "saas", "hébergement", "stockage"), "tech"),
    IconEntry("Wifi", ("wifi", "réseau", "connectivité", "internet", "connexion"), "tech"),
    IconEntry("Lock", ("lock", "sécurité", "verrouillage", "protection", "accès", "authentification"), "tech"),
    IconEntry("Sparkles", ("ai", "ia", "magic", "intelligence artificielle", "smart", "automatisation"), "tech"),
    IconEntry("Bot", ("bot", "robot", "automatisation", "chatbot", "assistant"), "tech"),
    IconEntry("Layers", ("layers", "stack", "architecture", "niveaux", "couches"), "tech"),
    IconEntry("Puzzle", ("puzzle", "intégration", "module", "composant", "plugin"), "tech"),
    IconEntry("Smartphone", ("mobile", "smartphone", "téléphone", "app", "application"), "tech"),
    IconEntry("Monitor", ("desktop", "écran", "ordinateur", "interface", "dashboard"), "tech"),

    # ── Process ──
    IconEntry("ArrowRight", ("arrow", "next", "suivant", "direction", "étape suivante"), "process"),
    IconEntry("ArrowUpRight", ("improve", "améliorer", "progression", "évolution"), "process"),
    IconEntry("RotateCcw", ("cycle", "itération", "boucle", "répéter", "récurrence"), "process"),
    IconEntry("GitBranch", ("branch", "branche", "parallèle", "workflow", "version"), "process"),
    IconEntry("Workflow", ("workflow", "processus", "flux", "pipeline", "automatisation"), "process"),
    IconEntry("ListChecks", ("checklist", "todo", "tâches", "étapes", "validation", "vérification"), "process"),
    IconEntry("Filter", ("filter", "filtre", "tri", "sélection", "entonnoir"), "process"),
    IconEntry("Repeat", ("repeat", "récurrence", "boucle", "automatique", "cycle"), "process"),

    # ── People ──
    IconEntry("Users", ("team", "équipe", "people", "utilisateurs", "groupe", "personnes"), "people"),
    IconEntry("User", ("user", "utilisateur", "profil", "personne", "individu"), "people"),
    IconEntry("UserCheck", ("verified", "vérifié", "approuvé", "validé", "certifié"), "people"),
    IconEntry("Heart", ("heart", "love", "satisfaction", "coeur", "engagement", "fidélité"), "people"),
    IconEntry("ThumbsUp", ("like", "approuver", "positif", "satisfaction", "feedback"), "people"),
    IconEntry("MessageCircle", ("chat", "message", "feedback", "commentaire", "conversation", "support"), "people"),
    IconEntry("GraduationCap", ("education", "formation", "learning", "école", "diplôme", "apprentissage"), "people"),
    IconEntry("HeartHandshake", ("care", "soin", "attention", "empathie", "service"), "people"),
    IconEntry("UserPlus", ("acquisition", "recrutement", "nouveau client", "inscription", "onboarding"), "people"),

    # ── Data ──
    IconEntry("BarChart3", ("chart", "graphique", "stats", "analytics", "données", "barchart"), "data"),
    IconEntry("LineChart", ("line", "courbe", "tendance", "trend", "évolution"), "data"),
    IconEntry("PieChart", ("pie", "camembert", "répartition", "distribution", "part"), "data"),
    IconEntry("Percent", ("percent", "pourcentage", "taux", "ratio", "proportion"), "data"),
    IconEntry("Hash", ("number", "nombre", "numéro", "chiffre", "quantité"), "data"),
    IconEntry("Database", ("database", "base de données", "data", "stockage", "bdd"), "data"),
    IconEntry("Activity", ("activity", "activité", "monitoring", "suivi", "pulse"), "data"),
    IconEntry("Gauge", ("gauge", "jauge", "mesure", "indicateur", "kpi", "score"), "data"),

    # ── UI / General ──
    IconEntry("CheckCircle", ("check", "done", "validé", "ok", "success", "terminé", "réussi"), "ui"),
    IconEntry("XCircle", ("error", "erreur", "échec", "non", "annuler", "refus"), "ui"),
    IconEntry("AlertTriangle", ("warning", "attention", "alerte", "risque", "danger"), "ui"),
    IconEntry("Info", ("info", "information", "détail", "aide", "note"), "ui"),
    IconEntry("Star", ("star", "rating", "étoile", "favori", "best", "note"), "ui"),
    IconEntry("Clock", ("time", "temps", "horloge", "durée", "délai", "clock"), "ui"),
    IconEntry("Calendar", ("calendar", "date", "planning", "calendrier", "agenda", "schedule"), "ui"),
    IconEntry("MapPin", ("location", "lieu", "place", "localisation", "adresse", "géo"), "ui"),
    IconEntry("Search", ("search", "recherche", "find", "explore", "loupe"), "ui"),
    IconEntry("Eye", ("visibility", "view", "visibilité", "vue", "aperçu", "transparence"), "ui"),
    IconEntry("EyeOff", ("hidden", "caché", "invisible", "masqué", "privé"), "ui"),
    IconEntry("Lightbulb", ("idea", "idée", "innovation", "insight", "ampoule", "suggestion"), "ui"),
    IconEntry("CircleDot", ("focus", "point", "center", "highlight", "cible"), "ui"),
    IconEntry("Flag", ("flag", "milestone", "jalon", "objectif", "drapeau"), "ui"),
    IconEntry("Bookmark", ("bookmark", "favori", "sauvegarde", "marque-page"), "ui"),
    IconEntry("Bell", ("notification", "alerte", "rappel", "cloche"), "ui"),
    IconEntry("Download", ("download", "téléchargement", "export"), "ui"),
    IconEntry("Upload", ("upload", "import", "envoi"), "ui"),
    IconEntry("Link", ("link", "lien", "connexion", "url"), "ui"),
    IconEntry("Mail", ("email", "mail", "courrier", "message", "newsletter"), "ui"),
    IconEntry("Phone", ("phone", "téléphone", "appel", "contact"), "ui"),

    # ── Nature / Misc ──
    IconEntry("Leaf", ("leaf", "feuille", "écologie", "vert", "durable", "nature", "bio"), "nature"),
    IconEntry("Sun", ("sun", "soleil", "lumière", "énergie", "optimisme"), "nature"),
    IconEntry("Droplets", ("water", "eau", "goutte", "liquide", "hydro"), "nature"),
    IconEntry("Mountain", ("mountain", "montagne", "sommet", "objectif", "défi", "challenge"), "nature"),
    IconEntry("TreePine", ("tree", "arbre", "forêt", "environnement", "croissance organique"), "nature"),
]

# Build lookup structures
ICON_REGISTRY: dict[str, IconEntry] = {e.name: e for e in _ENTRIES}
_ALIAS_INDEX: dict[str, str] = {}
for _entry in _ENTRIES:
    for _alias in _entry.aliases:
        _ALIAS_INDEX[_alias] = _entry.name

# Set of all valid icon names for fast validation
VALID_ICON_NAMES: frozenset[str] = frozenset(ICON_REGISTRY.keys())


# ── Resolution ──


def resolve_icon(query: str) -> str | None:
    """Resolve a semantic query to the best matching Lucide icon name.

    Returns None if no match found.
    """
    if not query:
        return None

    q = query.strip()

    # 1. Exact name match (case-insensitive)
    for name in ICON_REGISTRY:
        if name.lower() == q.lower():
            return name

    # 2. Exact alias match
    q_lower = q.lower()
    if q_lower in _ALIAS_INDEX:
        return _ALIAS_INDEX[q_lower]

    # 3. Substring match in aliases
    for alias, name in _ALIAS_INDEX.items():
        if q_lower in alias or alias in q_lower:
            return name

    # 4. Partial word match in aliases
    words = q_lower.split()
    for word in words:
        if len(word) < 3:
            continue
        if word in _ALIAS_INDEX:
            return _ALIAS_INDEX[word]
        for alias, name in _ALIAS_INDEX.items():
            if word in alias:
                return name

    logger.debug("No icon match for query: %s", query)
    return None


def is_valid_icon(name: str) -> bool:
    """Check if an icon name is in the Lucide registry."""
    return name in VALID_ICON_NAMES


def suggest_icons_for_content(text: str, max_results: int = 5) -> list[str]:
    """Suggest relevant Lucide icon names based on slide text content.

    Uses keyword overlap between text and icon aliases.
    Returns deduplicated list of icon names.
    """
    if not text:
        return []

    text_lower = text.lower()
    text_words = set(text_lower.split())

    scored: dict[str, int] = {}
    for entry in _ENTRIES:
        score = 0
        for alias in entry.aliases:
            if alias in text_lower:
                score += 2
            elif any(alias in w or w in alias for w in text_words if len(w) >= 3):
                score += 1
        if score > 0:
            scored[entry.name] = score

    sorted_icons = sorted(scored, key=lambda n: scored[n], reverse=True)
    return sorted_icons[:max_results]


def get_icon_names_for_prompt(max_icons: int = 40) -> str:
    """Return a compact list of available icon names for the LLM prompt."""
    names = sorted(ICON_REGISTRY.keys())[:max_icons]
    return ", ".join(names)


def get_icon_policy_for_prompt() -> str:
    """Return the icon policy text to inject into the system prompt."""
    icon_list = get_icon_names_for_prompt()
    return f"""\
POLITIQUE D'ICÔNES (OBLIGATOIRE) :
- Utilise UNIQUEMENT des icônes de la bibliothèque Lucide.
- Pour les éléments "icon" et "icon_list_item", le champ "query" est un terme sémantique libre.
  Exemple : "query": "croissance", "query": "sécurité", "query": "équipe"
- Le backend résoudra automatiquement vers le bon nom Lucide.
- Maximum 5 icônes par slide.
- Ne mélange pas les styles sur une même slide.
- Les icônes doivent renforcer la lisibilité et la hiérarchie, pas décorer gratuitement.
- Noms Lucide disponibles : {icon_list}
- Si tu connais le nom Lucide exact, tu peux l'utiliser directement dans "query"."""
