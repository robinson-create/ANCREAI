import { CheckCircle2, AlertCircle, Loader2 } from "lucide-react"
import type { ToolCallPayload } from "@/schemas/blocks"

/** Human-readable labels for provider keys. */
const PROVIDER_LABELS: Record<string, string> = {
  hubspot: "HubSpot",
  pipedrive: "Pipedrive",
  gmail: "Gmail",
  "google-drive": "Google Drive",
  shopify: "Shopify",
  stripe: "Stripe",
  notion: "Notion",
  slack: "Slack",
  salesforce: "Salesforce",
  outlook: "Outlook",
  nocrm: "noCRM.io",
  lemlist: "Lemlist",
  fireflies: "Fireflies",
}

/** Color classes per provider. */
const PROVIDER_COLORS: Record<string, string> = {
  hubspot: "bg-orange-500",
  pipedrive: "bg-green-600",
  gmail: "bg-red-500",
  "google-drive": "bg-yellow-600",
  shopify: "bg-green-500",
  stripe: "bg-purple-500",
  notion: "bg-gray-800",
  slack: "bg-purple-600",
  salesforce: "bg-blue-500",
  outlook: "bg-blue-600",
  nocrm: "bg-teal-500",
  lemlist: "bg-indigo-500",
  fireflies: "bg-yellow-500",
}

/** Known provider prefixes used in tool names. */
const PROVIDER_PREFIXES = new Set([
  "hubspot", "pipedrive", "gmail", "google", "shopify",
  "stripe", "notion", "slack", "salesforce", "outlook",
  "nocrm", "lemlist", "fireflies",
])

/** Format a snake_case tool name as a readable label. */
function formatToolName(tool: string): string {
  // Remove provider prefix (e.g. "hubspot_search_contacts" → "search contacts")
  // Handles multi-word prefixes like "google_drive_list_files" → "list files"
  const parts = tool.split("_")
  while (parts.length > 1 && PROVIDER_PREFIXES.has(parts[0]!)) {
    parts.shift()
  }
  return parts.join(" ").replace(/^\w/, (c) => c.toUpperCase())
}

export function ToolCallBlock({ provider, tool, status, summary }: ToolCallPayload) {
  const label = PROVIDER_LABELS[provider] || provider
  const color = PROVIDER_COLORS[provider] || "bg-gray-500"
  const isError = status === "error"

  return (
    <div className="my-2 flex items-start gap-3 rounded-lg border bg-muted/40 px-4 py-3">
      {/* Provider avatar */}
      <div
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-md ${color} text-white text-xs font-bold`}
      >
        {label.slice(0, 2).toUpperCase()}
      </div>

      {/* Content */}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">{label}</span>
          <span className="text-xs text-muted-foreground">{formatToolName(tool)}</span>
        </div>
        {summary && (
          <p className={`mt-0.5 text-sm ${isError ? "text-destructive" : "text-muted-foreground"}`}>
            {summary}
          </p>
        )}
      </div>

      {/* Status icon */}
      <div className="shrink-0 pt-0.5">
        {status === "success" && <CheckCircle2 className="h-4 w-4 text-green-600" />}
        {status === "error" && <AlertCircle className="h-4 w-4 text-destructive" />}
        {!status && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />}
      </div>
    </div>
  )
}
