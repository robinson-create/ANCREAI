/**
 * CopilotKit Chat Popup.
 *
 * Renders the CopilotKit floating chat popup alongside our existing chat.
 * This is intentionally separate from our SSE-based RAG chat:
 *   - Our chat: RAG queries with document retrieval + citations
 *   - CopilotKit popup: Generative UI with tool calls (cards, widgets)
 *
 * Both coexist. The popup can be toggled by the user.
 */

import { CopilotPopup } from "@copilotkit/react-ui"
import "@copilotkit/react-ui/styles.css"

export function CopilotChatPopup() {
  return (
    <CopilotPopup
      instructions={
        "Tu es l'assistant IA d'Ancre. Tu peux afficher des KPI et statistiques " +
        "sous forme de cartes visuelles en utilisant l'action render_kpi_card. " +
        "Quand l'utilisateur demande des métriques, des stats ou un dashboard, " +
        "utilise render_kpi_card pour afficher les données de manière structurée. " +
        "Réponds en français."
      }
      labels={{
        title: "Ancre AI",
        initial: "Bonjour ! Je peux afficher des KPI et statistiques. Essayez : « Montre-moi les KPI du mois »",
      }}
      defaultOpen={false}
    />
  )
}
