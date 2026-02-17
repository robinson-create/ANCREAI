import type { DictationAdapter } from "@assistant-ui/react"

/**
 * Stub adapter for future Capacitor / React Native bridge.
 *
 * Will delegate to native speech recognition APIs once the
 * mobile app is built. For now, always reports as unsupported.
 */
export class NativeDictationAdapter implements DictationAdapter {
  static isSupported(): boolean {
    // Check for Capacitor bridge or React Native bridge
    return typeof window !== "undefined" && "NativeDictation" in window
  }

  listen(): DictationAdapter.Session {
    throw new Error("NativeDictationAdapter is not implemented yet")
  }
}
