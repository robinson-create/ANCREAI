/**
 * Web Speech API - SpeechRecognition types for TypeScript.
 *
 * The DOM lib already declares SpeechRecognitionAlternative,
 * SpeechRecognitionResult, and SpeechRecognitionResultList.
 * We only add the recognizer instance, event types, and Window extensions.
 */

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
