import { WebSpeechDictationAdapter } from "@assistant-ui/react"

/**
 * Creates a dictation adapter using the browser's Web Speech API.
 * Used by the chat runtime and useDictation hook.
 */
export function createDictationAdapter(options?: { language?: string }) {
  const lang = options?.language ?? "fr-FR"
  return new WebSpeechDictationAdapter({
    language: lang,
    continuous: true,
    interimResults: true,
  })
}
