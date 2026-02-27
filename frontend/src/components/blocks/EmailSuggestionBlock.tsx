import { Mail, Check, X } from "lucide-react"
import { useState } from "react"
import type { EmailSuggestionPayload } from "@/schemas/blocks"

export function EmailSuggestionBlock({
  subject,
}: EmailSuggestionPayload) {
  const [dismissed, setDismissed] = useState(false)

  if (dismissed) return null

  return (
    <div className="my-2 rounded-lg border border-green-500/30 bg-green-50/50 dark:bg-green-950/20 p-2.5 overflow-hidden">
      <div className="flex items-center gap-2 min-w-0">
        <div className="flex h-5 w-5 items-center justify-center rounded-full bg-green-500/20 shrink-0">
          <Check className="h-3 w-3 text-green-600 dark:text-green-400" />
        </div>
        <Mail className="h-4 w-4 text-green-600 dark:text-green-400 shrink-0" />
        <p className="text-sm font-medium truncate flex-1 min-w-0">
          {subject ? `Email rédigé : ${subject}` : "Email rédigé"}
        </p>
        <button
          onClick={() => setDismissed(true)}
          className="shrink-0 inline-flex items-center justify-center h-5 w-5 rounded text-muted-foreground hover:bg-muted"
        >
          <X className="h-3 w-3" />
        </button>
      </div>
    </div>
  )
}
