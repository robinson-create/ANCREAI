import { z } from "zod"

// ---------------------------------------------------------------------------
// KPI Cards
// ---------------------------------------------------------------------------
export const kpiCardsSchema = z.object({
  title: z.string().nullish(),
  items: z.array(
    z.object({
      label: z.string(),
      value: z.string(),
      delta: z.string().nullish(),
    })
  ),
})
export type KpiCardsPayload = z.infer<typeof kpiCardsSchema>

// ---------------------------------------------------------------------------
// Steps
// ---------------------------------------------------------------------------
export const stepsSchema = z.object({
  title: z.string().nullish(),
  steps: z.array(
    z.object({
      title: z.string(),
      description: z.string().nullish(),
      status: z.enum(["todo", "doing", "done"]).nullish(),
    })
  ),
})
export type StepsPayload = z.infer<typeof stepsSchema>

// ---------------------------------------------------------------------------
// Table
// ---------------------------------------------------------------------------
export const tableSchema = z.object({
  title: z.string().nullish(),
  columns: z.array(z.string()),
  rows: z.array(z.array(z.string())),
})
export type TablePayload = z.infer<typeof tableSchema>

// ---------------------------------------------------------------------------
// Callout
// ---------------------------------------------------------------------------
export const calloutSchema = z.object({
  tone: z.enum(["info", "warning", "success", "danger"]),
  title: z.string().nullish(),
  message: z.string(),
})
export type CalloutPayload = z.infer<typeof calloutSchema>

// ---------------------------------------------------------------------------
// Tool Call
// ---------------------------------------------------------------------------
export const toolCallSchema = z.object({
  provider: z.string(),
  tool: z.string(),
  arguments: z.record(z.unknown()).nullish(),
  status: z.enum(["success", "error"]).nullish(),
  summary: z.string().nullish(),
})
export type ToolCallPayload = z.infer<typeof toolCallSchema>

// ---------------------------------------------------------------------------
// Calendar Blocks
// ---------------------------------------------------------------------------
export const calendarEventCardSchema = z.object({
  event: z.object({
    id: z.string(),
    title: z.string(),
    starts_at: z.string(),
    ends_at: z.string(),
    timezone: z.string(),
    provider: z.enum(["google", "microsoft"]),
    calendar_id: z.string(),
    attendees: z.array(z.string()),
    video_conference_link: z.string().optional(),
    html_link: z.string().optional(),
    description: z.string().optional(),
  }),
  message: z.string().optional(),
  operation: z.enum(["create", "update", "delete", "list", "find"]).optional(),
})
export type CalendarEventCardPayload = z.infer<typeof calendarEventCardSchema>

export const calendarEventChoicesSchema = z.object({
  events: z.array(z.object({
    id: z.string(),
    title: z.string(),
    starts_at: z.string(),
    ends_at: z.string(),
    timezone: z.string(),
    provider: z.enum(["google", "microsoft"]),
    calendar_id: z.string(),
    attendees: z.array(z.string()),
    video_conference_link: z.string().optional(),
    html_link: z.string().optional(),
    description: z.string().optional(),
  })),
  message: z.string(),
})
export type CalendarEventChoicesPayload = z.infer<typeof calendarEventChoicesSchema>

export const calendarConnectCtaSchema = z.object({
  message: z.string().optional(),
})
export type CalendarConnectCtaPayload = z.infer<typeof calendarConnectCtaSchema>

// ---------------------------------------------------------------------------
// Email Suggestion
// ---------------------------------------------------------------------------
export const emailSuggestionSchema = z.object({
  bundle_id: z.string(),
  subject: z.string(),
  reason: z.string(),
  tone: z.enum(["formal", "friendly", "neutral"]),
})
export type EmailSuggestionPayload = z.infer<typeof emailSuggestionSchema>

// ---------------------------------------------------------------------------
// Registry
// ---------------------------------------------------------------------------
export const blockSchemas = {
  kpi_cards: kpiCardsSchema,
  steps: stepsSchema,
  table: tableSchema,
  callout: calloutSchema,
  tool_call: toolCallSchema,
  calendar_event_card: calendarEventCardSchema,
  calendar_event_choices: calendarEventChoicesSchema,
  calendar_connect_cta: calendarConnectCtaSchema,
  email_suggestion: emailSuggestionSchema,
} as const
