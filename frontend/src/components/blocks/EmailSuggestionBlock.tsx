import { Mail, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import type { EmailSuggestionPayload } from "@/schemas/blocks"

export function EmailSuggestionBlock({
  bundle_id,
  subject,
  reason,
  tone,
}: EmailSuggestionPayload) {
  const navigate = useNavigate()
  const [dismissed, setDismissed] = useState(false)

  useEffect(() => {
    console.log("[Analytics] email_suggestion_shown", { bundle_id, subject, tone })
  }, [bundle_id, subject, tone])

  if (dismissed) return null

  const handleCreate = () => {
    console.log("[Analytics] email_suggestion_clicked", { bundle_id })
    navigate(`/app/email?bundle=${bundle_id}`)
  }

  const handleDismiss = () => {
    console.log("[Analytics] email_suggestion_dismissed", { bundle_id })
    setDismissed(true)
  }

  return (
    <div className="my-2 rounded-lg border border-blue-500/30 bg-blue-50/50 dark:bg-blue-950/20 p-4">
      <div className="flex items-start gap-3">
        <Mail className="h-5 w-5 text-blue-600 dark:text-blue-400 mt-0.5 shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="font-medium text-sm">Transformer en email</p>
          <p className="text-sm text-muted-foreground mt-1">{reason}</p>
          {subject && (
            <p className="text-xs text-muted-foreground mt-1 truncate">
              Sujet : {subject}
            </p>
          )}
          <div className="flex gap-2 mt-3">
            <Button size="sm" onClick={handleCreate}>
              <Mail className="h-3.5 w-3.5 mr-1.5" />
              Créer l'email
            </Button>
            <Button size="sm" variant="ghost" onClick={handleDismiss}>
              <X className="h-3.5 w-3.5 mr-1.5" />
              Ignorer
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
