import { useCallback, useEffect, useRef, useState } from "react"
import { getCurrentAuthToken } from "@/api/client"
import type { PresentationSSEEvent, PresentationSSEEventType } from "@/types"

interface UsePresentationSSEOptions {
  presentationId: string | undefined
  enabled: boolean
  onEvent: (event: PresentationSSEEvent) => void
  onError?: (message: string) => void
}

export function usePresentationSSE({
  presentationId,
  enabled,
  onEvent,
  onError,
}: UsePresentationSSEOptions) {
  const [isConnected, setIsConnected] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const onEventRef = useRef(onEvent)
  const onErrorRef = useRef(onError)
  onEventRef.current = onEvent
  onErrorRef.current = onError

  const connect = useCallback(async () => {
    if (!presentationId) return

    const token = await getCurrentAuthToken()
    if (!token) {
      onErrorRef.current?.("Token d'authentification indisponible")
      return
    }

    const base = import.meta.env.VITE_API_BASE_URL || window.location.origin
    const url = new URL(`/api/v1/presentations/${presentationId}/events`, base)

    const controller = new AbortController()
    abortRef.current = controller

    try {
      const response = await fetch(url, {
        method: "GET",
        headers: { Authorization: `Bearer ${token}` },
        signal: controller.signal,
      })

      if (!response.ok) {
        onErrorRef.current?.(`SSE: HTTP ${response.status}`)
        return
      }

      setIsConnected(true)
      const reader = response.body?.getReader()
      if (!reader) return

      const decoder = new TextDecoder()
      let buffer = ""

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const frames = buffer.split("\n\n")
        buffer = frames.pop() || ""

        for (const frame of frames) {
          if (!frame.trim() || frame.trim().startsWith(": heartbeat")) continue

          let eventType = "update"
          let eventData = ""

          for (const line of frame.split("\n")) {
            if (line.startsWith("event: ")) {
              eventType = line.slice(7).trim()
            } else if (line.startsWith("data: ")) {
              eventData = line.slice(6)
            }
          }

          if (eventData) {
            try {
              const payload = JSON.parse(eventData)
              onEventRef.current({
                type: eventType as PresentationSSEEventType,
                payload,
              })
            } catch {
              // ignore malformed JSON
            }
          }

          // Terminal events
          if (["outline_ready", "generation_complete", "export_ready", "error"].includes(eventType)) {
            setIsConnected(false)
            return
          }
        }
      }
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === "AbortError") return
      onErrorRef.current?.(`SSE: ${err instanceof Error ? err.message : "connexion perdue"}`)

      // Auto-reconnect after 3s
      if (!controller.signal.aborted) {
        setTimeout(() => {
          if (!abortRef.current?.signal.aborted) connect()
        }, 3000)
      }
    } finally {
      setIsConnected(false)
    }
  }, [presentationId])

  useEffect(() => {
    if (enabled && presentationId) {
      connect()
    }
    return () => {
      abortRef.current?.abort()
    }
  }, [enabled, presentationId, connect])

  return {
    isConnected,
    disconnect: () => abortRef.current?.abort(),
  }
}
