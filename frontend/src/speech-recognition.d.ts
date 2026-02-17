/**
 * Web Speech API - SpeechRecognition types for TypeScript.
 * Single source of truth to avoid conflicts between files.
 */
declare global {
  interface SpeechRecognitionResultItem {
    transcript: string
    confidence: number
  }

  interface SpeechRecognitionResult {
    readonly length: number
    readonly isFinal: boolean
    item(index: number): SpeechRecognitionResultItem
    [index: number]: SpeechRecognitionResultItem
  }

  interface SpeechRecognitionResultList {
    readonly length: number
    item(index: number): SpeechRecognitionResult
    [index: number]: SpeechRecognitionResult
  }

  interface SpeechRecognitionEvent extends Event {
    readonly resultIndex: number
    readonly results: SpeechRecognitionResultList
  }

  interface SpeechRecognitionErrorEvent extends Event {
    readonly error: string
    readonly message?: string
  }

  interface SpeechRecognitionInstance extends EventTarget {
    lang: string
    continuous: boolean
    interimResults: boolean
    start(): void
    stop(): void
    abort(): void
    onresult: ((ev: SpeechRecognitionEvent) => void) | null
    onerror: ((ev: SpeechRecognitionErrorEvent) => void) | null
    onend: (() => void) | null
  }

  interface Window {
    SpeechRecognition?: new () => SpeechRecognitionInstance
    webkitSpeechRecognition?: new () => SpeechRecognitionInstance
  }
}

export {}
