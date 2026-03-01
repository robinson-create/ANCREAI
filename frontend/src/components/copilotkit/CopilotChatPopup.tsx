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
        "Tu es l'assistant IA d'Ancre. Tu peux :\n" +
        "1. Créer des présentations professionnelles avec l'action create_presentation. " +
        "Quand l'utilisateur décrit un diaporama, un pitch, des slides ou une présentation, " +
        "utilise create_presentation en extrayant TOUT le contenu décrit (sujets, sections, consignes de design, couleurs). " +
        "Ne te contente PAS de répondre en texte — crée la présentation.\n" +
        "2. Afficher des KPI et statistiques avec render_kpi_card.\n" +
        "Réponds en français. Sois concis."
      }
      labels={{
        title: "Ancre AI",
        initial: "Bonjour ! Je peux creer des presentations et afficher des KPI. Decrivez votre presentation et je la cree pour vous.",
      }}
      defaultOpen={false}
    />
  )
}
