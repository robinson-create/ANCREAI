/**
 * Global CopilotKit actions registration.
 *
 * This component registers CopilotKit actions (tools) that the LLM
 * can invoke. Each action can render React components inline in the
 * CopilotKit chat, enabling "Generative UI".
 *
 * Place this component inside the CopilotKit provider tree AND BrowserRouter.
 */

import { useCopilotAction } from "@copilotkit/react-core"
import { useNavigate } from "react-router-dom"
import { Presentation, ArrowRight, Loader2 } from "lucide-react"
import { presentationsApi } from "@/api/presentations"
import { KpiCard } from "./KpiCard"
import type { KpiCardProps } from "./KpiCard"

export function CopilotActions() {
  const navigate = useNavigate()

  // Action: render_kpi_card
  useCopilotAction({
    name: "render_kpi_card",
    description:
      "Render a KPI (Key Performance Indicator) card with metrics. " +
      "Use this when the user asks for statistics, metrics, dashboards, " +
      "or performance data. Returns a visual card with values and trends.",
    parameters: [
      {
        name: "title",
        type: "string",
        description: "Title of the KPI card",
        required: true,
      },
      {
        name: "description",
        type: "string",
        description: "Short description below the title",
        required: false,
      },
      {
        name: "period",
        type: "string",
        description: "Time period label (e.g. 'Q1 2025', 'Last 30 days')",
        required: false,
      },
      {
        name: "kpis",
        type: "object[]",
        description: "Array of KPI items with label, value, and optional change percentage",
        required: true,
        attributes: [
          {
            name: "label",
            type: "string",
            description: "KPI metric name (e.g. 'Revenue', 'Users')",
            required: true,
          },
          {
            name: "value",
            type: "string",
            description: "KPI value (e.g. '€12,450', '1,234')",
            required: true,
          },
          {
            name: "change",
            type: "number",
            description: "Percentage change (positive = up, negative = down)",
            required: false,
          },
        ],
      },
    ],
    render: ({ args, status }) => {
      const props = args as unknown as KpiCardProps
      if (status === "executing" || status === "complete") {
        return (
          <KpiCard
            title={props.title || "KPI"}
            description={props.description}
            kpis={props.kpis || []}
            period={props.period}
          />
        )
      }
      return <></>
    },
    handler: async (args) => {
      return `KPI card "${args.title}" rendered with ${args.kpis?.length || 0} metrics.`
    },
  })

  // Action: create_presentation
  // Detects presentation requests and creates one, then offers navigation.
  useCopilotAction({
    name: "create_presentation",
    description:
      "Crée une nouvelle présentation professionnelle. " +
      "Utilise cette action quand l'utilisateur veut créer une présentation, " +
      "un diaporama, un pitch deck, un slideshow, des slides, ou décrit le contenu " +
      "de slides (titres, sections, design). " +
      "Extrais le sujet/prompt complet de la demande de l'utilisateur.",
    parameters: [
      {
        name: "title",
        type: "string",
        description: "Titre court de la présentation (ex: 'Pitch Dom Engineering')",
        required: true,
      },
      {
        name: "prompt",
        type: "string",
        description:
          "Le prompt COMPLET pour générer la présentation. " +
          "Reprends TOUT le contenu décrit par l'utilisateur : sujets, sections, " +
          "points clés, consignes de style, couleurs, etc. Ne résume pas.",
        required: true,
      },
      {
        name: "slide_count",
        type: "number",
        description: "Nombre de slides souhaité (par défaut 8)",
        required: false,
      },
      {
        name: "style",
        type: "string",
        description: "Style de la présentation : 'professional', 'creative', 'minimal', 'corporate'",
        required: false,
      },
    ],
    render: ({ args, status, result }) => {
      if (status === "executing") {
        return (
          <div className="flex items-center gap-3 rounded-lg border bg-card p-4 my-2">
            <Loader2 className="h-5 w-5 animate-spin text-primary" />
            <div>
              <p className="font-medium text-sm">Création de la présentation...</p>
              <p className="text-xs text-muted-foreground">{args.title}</p>
            </div>
          </div>
        )
      }
      // Extract presentation ID from handler result
      const presId = typeof result === "string"
        ? result.match(/ID: ([a-f0-9-]+)/)?.[1]
        : undefined
      if (status === "complete" && presId) {
        return (
          <div className="rounded-lg border bg-card p-4 my-2 space-y-3">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                <Presentation className="h-5 w-5 text-primary" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-medium text-sm">{args.title}</p>
                <p className="text-xs text-muted-foreground truncate">
                  {args.slide_count || 8} slides &middot; {args.style || "professional"}
                </p>
              </div>
            </div>
            <button
              onClick={() => navigate(`/app/presentations/${presId}`)}
              className="flex w-full items-center justify-center gap-2 rounded-md bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
            >
              Ouvrir dans l'éditeur
              <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        )
      }
      if (status === "complete") {
        // Error case — result is the error message
        return (
          <div className="rounded-lg border border-destructive/50 bg-destructive/5 p-4 my-2">
            <p className="text-sm text-destructive">{result}</p>
          </div>
        )
      }
      return <></>
    },
    handler: async (args) => {
      try {
        const slideCount = args.slide_count || 8
        const style = args.style || "professional"
        const pres = await presentationsApi.create({
          title: args.title,
          prompt: args.prompt,
          settings: {
            language: "fr-FR",
            style,
            slide_count: slideCount,
          },
        })
        // Immediately trigger outline generation (same tunnel as documents page CTA)
        await presentationsApi.generateOutline(pres.id, {
          prompt: args.prompt,
          slide_count: slideCount,
          language: "fr-FR",
          style,
        })
        return (
          `Présentation "${pres.title}" créée (ID: ${pres.id}). ` +
          `L'utilisateur peut cliquer sur le bouton pour ouvrir l'éditeur.`
        )
      } catch (error) {
        return `Erreur lors de la création : ${error instanceof Error ? error.message : "erreur inconnue"}`
      }
    },
  })

  return null
}
