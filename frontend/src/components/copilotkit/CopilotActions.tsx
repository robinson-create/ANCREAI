/**
 * Global CopilotKit actions registration.
 *
 * This component registers CopilotKit actions (tools) that the LLM
 * can invoke. Each action can render React components inline in the
 * CopilotKit chat, enabling "Generative UI".
 *
 * Place this component inside the CopilotKit provider tree.
 */

import { useCopilotAction } from "@copilotkit/react-core"
import { KpiCard } from "./KpiCard"
import type { KpiCardProps } from "./KpiCard"

export function CopilotActions() {
  // Action: render_kpi_card
  // The LLM can call this to display a KPI dashboard card in the chat.
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
      // The handler runs after render. We just acknowledge.
      // In a real scenario, this could call our FastAPI backend
      // to fetch real data before rendering.
      return `KPI card "${args.title}" rendered with ${args.kpis?.length || 0} metrics.`
    },
  })

  // This component renders nothing visible - it just registers actions
  return null
}
