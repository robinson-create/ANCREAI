import type { Block } from "@/types"
import { blockSchemas } from "@/schemas/blocks"
import { KpiCards } from "./KpiCards"
import { Steps } from "./Steps"
import { DataTable } from "./DataTable"
import { Callout } from "./Callout"
import { ToolCallBlock } from "./ToolCallBlock"
import { ErrorBlock } from "./ErrorBlock"
import { CalendarEventCard } from "./calendar/CalendarEventCard"
import { CalendarEventChoices } from "./calendar/CalendarEventChoices"
import { CalendarConnectProviderCTA } from "./calendar/CalendarConnectProviderCTA"
import { EmailSuggestionBlock } from "./EmailSuggestionBlock"
import { ContactSuggestionBlock } from "./ContactSuggestionBlock"
import { PresentationSuggestionBlock } from "./PresentationSuggestionBlock"

const blockComponents = {
  kpi_cards: KpiCards,
  steps: Steps,
  table: DataTable,
  callout: Callout,
  tool_call: ToolCallBlock,
  calendar_event_card: CalendarEventCard,
  calendar_event_choices: CalendarEventChoices,
  calendar_connect_cta: CalendarConnectProviderCTA,
  email_suggestion: EmailSuggestionBlock,
  contact_suggestion: ContactSuggestionBlock,
  presentation_suggestion: PresentationSuggestionBlock,
} as const

type RenderableBlockType = keyof typeof blockComponents

export function BlockRenderer({ block }: { block: Block }) {
  console.debug("[BlockRenderer]", block.type, block.payload)

  // Handle error blocks from the backend
  if (block.type === "error") {
    const payload = block.payload as { message?: string; raw?: string }
    return (
      <ErrorBlock
        message={payload?.message || "Unknown error"}
        raw={payload?.raw}
      />
    )
  }

  // Unknown block type
  if (!(block.type in blockComponents)) {
    return (
      <ErrorBlock
        message={`Unknown block type: "${block.type}"`}
        raw={JSON.stringify(block.payload, null, 2)}
      />
    )
  }

  const blockType = block.type as RenderableBlockType
  const schema = blockSchemas[blockType]
  const Component = blockComponents[blockType]

  // Validate payload with Zod
  const result = schema.safeParse(block.payload)

  if (!result.success) {
    const errors = result.error.issues
      .map((i) => `${i.path.join(".")}: ${i.message}`)
      .join("; ")
    return (
      <ErrorBlock
        message={`Validation failed: ${errors}`}
        raw={JSON.stringify(block.payload, null, 2)}
      />
    )
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return <Component {...(result.data as any)} />
}
