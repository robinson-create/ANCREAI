import apiClient, { getCurrentAuthToken } from "./client"
import type { Block, ChatRequest, ChatResponse, Message } from "@/types"

export const chatApi = {
  send: async (
    assistantId: string,
    data: ChatRequest
  ): Promise<ChatResponse> => {
    const response = await apiClient.post<ChatResponse>(
      `/chat/${assistantId}`,
      data
    )
    return response.data
  },

  stream: (
    assistantId: string,
    data: ChatRequest,
    onToken: (token: string) => void,
    onComplete: (response: {
      conversationId: string
      citations: ChatResponse["citations"]
      tokensInput: number
      tokensOutput: number
    }) => void,
    onError: (error: string) => void,
    onConversationId?: (conversationId: string) => void,
    onBlock?: (block: Block) => void,
    onDraftUpdate?: (data: { subject: string; body_draft: string; tone: string; reason: string }) => void,
    onDocumentUpdate?: (data: { markdown_content: string; summary: string }) => void
  ): (() => void) => {
    const base = import.meta.env.VITE_API_BASE_URL || window.location.origin
    const url = new URL(`/api/v1/chat/${assistantId}/stream`, base)

    // Create AbortController for cancellation
    const controller = new AbortController()

    // Start the fetch with auth token from Clerk
    ;(async () => {
      const token = await getCurrentAuthToken()

      if (!token) {
        onError("Authentication token not available")
        return
      }

      fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(data),
        signal: controller.signal,
      })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`)
        }

        const reader = response.body?.getReader()
        const decoder = new TextDecoder()

        let conversationId = ""
        let citations: ChatResponse["citations"] = []
        let tokensInput = 0
        let tokensOutput = 0
        let completed = false

        const handleEvent = (eventType: string, eventData: string) => {
          switch (eventType) {
            case "conversation_id":
              conversationId = eventData
              if (onConversationId) {
                onConversationId(conversationId)
              }
              break
            case "token":
              onToken(eventData)
              break
            case "block":
              if (onBlock) {
                try {
                  const block: Block = JSON.parse(eventData)
                  onBlock(block)
                } catch {
                  // Ignore parse errors
                }
              }
              break
            case "citations":
              try {
                citations = JSON.parse(eventData)
              } catch {
                // Ignore parse errors
              }
              break
            case "done":
              try {
                const doneData = JSON.parse(eventData)
                tokensInput = doneData.tokens_input || 0
                tokensOutput = doneData.tokens_output || 0
              } catch {
                // Ignore parse errors
              }
              completed = true
              onComplete({
                conversationId,
                citations,
                tokensInput,
                tokensOutput,
              })
              break
            case "draft_update":
              if (onDraftUpdate) {
                try {
                  const draftData = JSON.parse(eventData)
                  onDraftUpdate(draftData)
                } catch {
                  // Ignore parse errors
                }
              }
              break
            case "document_update":
              if (onDocumentUpdate) {
                try {
                  const docData = JSON.parse(eventData)
                  onDocumentUpdate(docData)
                } catch {
                  // Ignore parse errors
                }
              }
              break
            case "error":
              completed = true
              onError(eventData)
              break
          }
        }

        const parseSSEFrame = (frame: string) => {
          if (!frame.trim()) return
          const lines = frame.split("\n")
          let eventType = ""
          const dataLines: string[] = []
          for (const line of lines) {
            if (line.startsWith("event:")) {
              eventType = line.slice(6).trim()
            } else if (line.startsWith("data:")) {
              const raw = line.slice(5)
              dataLines.push(raw.startsWith(" ") ? raw.slice(1) : raw)
            }
          }
          const eventData = dataLines.join("\n")
          if (eventType) handleEvent(eventType, eventData)
        }

        const processStream = async () => {
          if (!reader) return

          let buffer = ""

          while (true) {
            const { done, value } = await reader.read()
            if (done) break

            buffer += decoder.decode(value, { stream: true })

            // Process complete SSE messages (separated by double newlines)
            const messages = buffer.split("\n\n")
            // Keep the last incomplete message in the buffer
            buffer = messages.pop() || ""

            for (const message of messages) {
              parseSSEFrame(message)
            }
          }

          // Flush remaining decoder buffer and process any trailing data
          const remaining = decoder.decode()
          if (remaining) buffer += remaining
          if (buffer.trim()) {
            for (const frame of buffer.split("\n\n")) {
              parseSSEFrame(frame)
            }
          }
        }

        processStream()
          .catch((err) => {
            if (err.name !== "AbortError" && !completed) {
              onError(err.message)
            }
          })
          .finally(() => {
            // Safety: if stream ended without done/error event, force complete
            if (!completed) {
              onComplete({
                conversationId,
                citations,
                tokensInput,
                tokensOutput,
              })
            }
          })
      })
      .catch((err) => {
        if (err.name !== "AbortError") {
          onError(err.message)
        }
      })
    })() // End of async IIFE

    // Return abort function
    return () => controller.abort()
  },

  getConversation: async (
    assistantId: string,
    conversationId: string
  ): Promise<Message[]> => {
    const response = await apiClient.get<Message[]>(
      `/chat/${assistantId}/conversations/${conversationId}`
    )
    return response.data
  },

  listConversations: async (
    assistantId: string
  ): Promise<Array<{
    id: string
    title: string
    started_at: string
    last_message_at: string
    message_count: number
  }>> => {
    const response = await apiClient.get(
      `/chat/${assistantId}/conversations`
    )
    return response.data
  },
}
