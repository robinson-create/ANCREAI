import {
  WebSpeechDictationAdapter,
  type DictationAdapter,
} from "@assistant-ui/react"
import { NativeDictationAdapter } from "./native-adapter"
import { CloudFallbackDictationAdapter } from "./cloud-fallback-adapter"

export type DictationProviderType = "web-speech" | "native" | "cloud"

/**
 * Create the best available DictationAdapter.
 *
 * Priority: WebSpeech (Chrome/Edge) → Native (Capacitor/RN) → Cloud (backend Whisper).
 * Use `forceProvider` to override for debugging.
 */
export function createDictationAdapter(options?: {
  language?: string
  forceProvider?: DictationProviderType
}): DictationAdapter {
  const language = options?.language ?? "fr"
  const forced = options?.forceProvider

  if (
    forced === "web-speech" ||
    (!forced && WebSpeechDictationAdapter.isSupported())
  ) {
    return new WebSpeechDictationAdapter({
      language,
      continuous: true,
      interimResults: false,
    })
  }

  if (
    forced === "native" ||
    (!forced && NativeDictationAdapter.isSupported())
  ) {
    return new NativeDictationAdapter()
  }

  return new CloudFallbackDictationAdapter({ language })
}

/**
 * Detect which provider would be selected automatically.
 */
export function detectDictationProvider(): DictationProviderType {
  if (NativeDictationAdapter.isSupported()) return "native"
  if (WebSpeechDictationAdapter.isSupported()) return "web-speech"
  return "cloud"
}
