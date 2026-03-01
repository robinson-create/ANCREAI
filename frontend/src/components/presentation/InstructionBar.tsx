import { useState, useCallback, useRef } from "react"
import { Sparkles, Loader2, Send } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"

interface InstructionBarProps {
  onSubmit: (instruction: string) => void
  isProcessing: boolean
  disabled?: boolean
}

const SUGGESTION_CHIPS = [
  "Transforme en graphique",
  "Mets en avant les chiffres",
  "Transforme en timeline",
  "Ajoute des icônes",
  "Transforme en comparaison",
  "Plus premium",
]

export function InstructionBar({ onSubmit, isProcessing, disabled }: InstructionBarProps) {
  const [instruction, setInstruction] = useState("")
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const handleSubmit = useCallback(
    (e?: React.FormEvent) => {
      e?.preventDefault()
      const trimmed = instruction.trim()
      if (!trimmed || isProcessing) return
      onSubmit(trimmed)
      setInstruction("")
    },
    [instruction, isProcessing, onSubmit],
  )

  const handleChipClick = useCallback(
    (chip: string) => {
      if (isProcessing) return
      onSubmit(chip)
    },
    [isProcessing, onSubmit],
  )

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault()
        handleSubmit()
      }
    },
    [handleSubmit],
  )

  return (
    <div className="w-72 border-l bg-card flex flex-col h-full shrink-0">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2.5 border-b">
        <Sparkles className="h-4 w-4 text-primary" />
        <span className="text-sm font-medium">Assistant IA</span>
      </div>

      {/* Suggestion chips */}
      <div className="px-3 py-2.5 border-b">
        <p className="text-[11px] text-muted-foreground mb-2">Suggestions rapides</p>
        <div className="flex flex-wrap gap-1.5">
          {SUGGESTION_CHIPS.map((chip) => (
            <button
              key={chip}
              onClick={() => handleChipClick(chip)}
              disabled={isProcessing || disabled}
              className="text-xs px-2.5 py-1 rounded-full border
                text-muted-foreground hover:text-foreground hover:border-primary/40
                transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {chip}
            </button>
          ))}
        </div>
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Input area */}
      <form onSubmit={handleSubmit} className="px-3 py-3 border-t">
        <Textarea
          ref={textareaRef}
          value={instruction}
          onChange={(e) => setInstruction(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Donne une consigne... ex: rends plus visuel, transforme en timeline"
          className="resize-none text-sm min-h-[72px]"
          disabled={isProcessing || disabled}
        />
        <div className="flex items-center justify-between mt-2">
          <p className="text-[10px] text-muted-foreground">
            ⌘+Entrée
          </p>
          <Button
            type="submit"
            size="sm"
            disabled={!instruction.trim() || isProcessing || disabled}
            className="gap-1.5 h-8"
          >
            {isProcessing ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Send className="h-3.5 w-3.5" />
            )}
            {isProcessing ? "En cours..." : "Appliquer"}
          </Button>
        </div>
      </form>
    </div>
  )
}
