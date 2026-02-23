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
    onBlock?: (block: Block) => void
  ): (() => void) => {
    const url = new URL(`/api/v1/chat/${assistantId}/stream`, window.location.origin)

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
              if (!message.trim()) continue

              const lines = message.split("\n")
              let eventType = ""
              const dataLines: string[] = []

              for (const line of lines) {
                if (line.startsWith("event:")) {
                  eventType = line.slice(6).trim()
                } else if (line.startsWith("data:")) {
                  // SSE spec: remove "data:" prefix, then strip exactly one
                  // leading space (the SSE separator). Preserve any additional
                  // whitespace that is part of the actual token data.
                  const raw = line.slice(5)
                  dataLines.push(raw.startsWith(" ") ? raw.slice(1) : raw)
                }
              }

              // SSE spec: multiple data: lines are joined with newlines
              const eventData = dataLines.join("\n")

              if (!eventType) continue

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
                  onComplete({
                    conversationId,
                    citations,
                    tokensInput,
                    tokensOutput,
                  })
                  break
                case "error":
                  onError(eventData)
                  break
              }
            }
          }
        }

        processStream().catch((err) => {
          if (err.name !== "AbortError") {
            onError(err.message)
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
