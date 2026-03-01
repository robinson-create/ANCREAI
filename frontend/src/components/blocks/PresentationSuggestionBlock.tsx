import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { Presentation, ArrowRight, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { presentationsApi } from "@/api/presentations"
import type { PresentationSuggestionPayload } from "@/schemas/blocks"

export function PresentationSuggestionBlock(props: PresentationSuggestionPayload) {
  const navigate = useNavigate()
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleCreate = async () => {
    setCreating(true)
    setError(null)
    try {
      const pres = await presentationsApi.create({
        title: props.title,
        prompt: props.prompt,
        settings: {
          language: "fr-FR",
          style: props.style,
          slide_count: props.slide_count,
        },
      })
      // Immediately trigger outline generation (same tunnel as documents page CTA)
      await presentationsApi.generateOutline(pres.id, {
        prompt: props.prompt,
        slide_count: props.slide_count,
        language: "fr-FR",
        style: props.style,
      })
      navigate(`/app/presentations/${pres.id}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erreur lors de la création")
      setCreating(false)
    }
  }

  return (
    <div className="rounded-lg border bg-card p-4 my-3 space-y-3">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
          <Presentation className="h-5 w-5 text-primary" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-medium text-sm">{props.title}</p>
          <p className="text-xs text-muted-foreground">
            {props.slide_count} slides &middot; {props.style}
          </p>
        </div>
      </div>

      {error && (
        <p className="text-xs text-destructive">{error}</p>
      )}

      <Button
        onClick={handleCreate}
        disabled={creating}
        className="w-full"
        size="sm"
      >
        {creating ? (
          <>
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            Création...
          </>
        ) : (
          <>
            Créer et ouvrir dans l'éditeur
            <ArrowRight className="h-4 w-4 ml-2" />
          </>
        )}
      </Button>
    </div>
  )
}
