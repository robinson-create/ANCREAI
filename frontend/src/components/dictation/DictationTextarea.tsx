import * as React from "react"
import { Mic, MicOff, Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"
import { Textarea } from "@/components/ui/textarea"
import { useDictation } from "@/hooks/use-dictation"

interface DictationTextareaProps
  extends React.ComponentProps<"textarea"> {
  /** Called when a final transcript is received. */
  onTranscript?: (text: string) => void
  /** BCP-47 language code for dictation. */
  language?: string
}

/**
 * A Textarea with an integrated mic button for voice dictation.
 * For use outside of the chat composer (e.g. in forms).
 */
const DictationTextarea = React.forwardRef<
  HTMLTextAreaElement,
  DictationTextareaProps
>(({ className, onTranscript, language = "fr", ...props }, ref) => {
  const { isListening, isStarting, start, stop } = useDictation({
    language,
    onFinalTranscript: (text) => {
      onTranscript?.(text)
    },
  })

  return (
    <div className="relative">
      <Textarea
        ref={ref}
        className={cn("pr-12", className)}
        {...props}
      />
      <button
        type="button"
        className={cn(
          "absolute bottom-2 right-2 inline-flex h-8 w-8 items-center justify-center rounded-md transition-colors",
          isListening
            ? "bg-destructive text-destructive-foreground animate-pulse"
            : "text-muted-foreground hover:bg-muted hover:text-foreground",
          isStarting && "opacity-50 pointer-events-none"
        )}
        onClick={isListening ? stop : start}
        disabled={isStarting}
      >
        {isStarting ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : isListening ? (
          <MicOff className="h-4 w-4" />
        ) : (
          <Mic className="h-4 w-4" />
        )}
      </button>
    </div>
  )
})
DictationTextarea.displayName = "DictationTextarea"

export { DictationTextarea }
