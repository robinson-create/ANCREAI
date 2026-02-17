import { useState, useCallback, useRef, useMemo } from "react"
import { createDictationAdapter } from "@/lib/dictation"
import type { DictationAdapter } from "@assistant-ui/react"

interface UseDictationOptions {
  language?: string
  onFinalTranscript?: (text: string) => void
  onInterimTranscript?: (text: string) => void
}

interface UseDictationReturn {
  isListening: boolean
  isStarting: boolean
  transcript: string
  start: () => void
  stop: () => void
}

/**
 * Standalone dictation hook for use outside of assistant-ui's runtime context.
 * For the chat composer, use the DictationAdapter via useExternalStoreRuntime instead.
 */
export function useDictation(options?: UseDictationOptions): UseDictationReturn {
  const [isListening, setIsListening] = useState(false)
  const [isStarting, setIsStarting] = useState(false)
  const [transcript, setTranscript] = useState("")
  const sessionRef = useRef<DictationAdapter.Session | null>(null)
  const optionsRef = useRef(options)
  optionsRef.current = options

  const adapter = useMemo(
    () => createDictationAdapter({ language: options?.language }),
    [options?.language]
  )

  const start = useCallback(() => {
    if (sessionRef.current) return

    setIsStarting(true)
    setTranscript("")
    const session = adapter.listen()
    sessionRef.current = session

    session.onSpeechStart(() => {
      setIsStarting(false)
      setIsListening(true)
    })

    session.onSpeech((result) => {
      setTranscript(result.transcript)
      if (result.isFinal === false) {
        optionsRef.current?.onInterimTranscript?.(result.transcript)
      }
    })

    session.onSpeechEnd((result) => {
      if (result.transcript) {
        optionsRef.current?.onFinalTranscript?.(result.transcript)
      }
      setIsListening(false)
      setIsStarting(false)
      sessionRef.current = null
    })
  }, [adapter])

  const stop = useCallback(async () => {
    if (sessionRef.current) {
      await sessionRef.current.stop()
      sessionRef.current = null
    }
    setIsListening(false)
    setIsStarting(false)
  }, [])

  return { isListening, isStarting, transcript, start, stop }
}
