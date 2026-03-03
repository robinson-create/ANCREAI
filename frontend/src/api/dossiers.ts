import apiClient, { getCurrentAuthToken } from "./client"
import type {
  Block,
  Dossier,
  DossierWithStats,
  DossierDocument,
  DossierDocumentUploadResponse,
  DossierConversation,
  DossierItem,
  DossierItemAdd,
  Message,
  ChatResponse,
} from "@/types"

export interface DossierChatRequest {
  message: string
  conversation_id?: string
  include_history?: boolean
  max_history_messages?: number
}

export interface DossierCreateRequest {
  name: string
  description?: string
  color?: string
}

export interface DossierUpdateRequest {
  name?: string
  description?: string
  color?: string
}

export const dossiersApi = {
  get: async (id: string): Promise<DossierWithStats> => {
    const response = await apiClient.get<DossierWithStats>(`/dossiers/${id}`)
    return response.data
  },

  list: async (): Promise<DossierWithStats[]> => {
    const response = await apiClient.get<DossierWithStats[]>("/dossiers")
    return response.data
  },

  create: async (data: DossierCreateRequest): Promise<Dossier> => {
    const response = await apiClient.post<Dossier>("/dossiers", data)
    return response.data
  },

  update: async (id: string, data: DossierUpdateRequest): Promise<Dossier> => {
    const response = await apiClient.patch<Dossier>(`/dossiers/${id}`, data)
    return response.data
  },

  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/dossiers/${id}`)
  },

  importDocument: async (
    dossierId: string,
    sourceDocumentId: string
  ): Promise<DossierDocumentUploadResponse> => {
    const response = await apiClient.post<DossierDocumentUploadResponse>(
      `/dossiers/${dossierId}/documents/import`,
      { source_document_id: sourceDocumentId }
    )
    return response.data
  },

  listDocuments: async (dossierId: string): Promise<DossierDocument[]> => {
    const response = await apiClient.get<DossierDocument[]>(
      `/dossiers/${dossierId}/documents`
    )
    return response.data
  },

  uploadDocument: async (
    dossierId: string,
    file: File
  ): Promise<DossierDocumentUploadResponse> => {
    const formData = new FormData()
    formData.append("file", file)
    const response = await apiClient.post<DossierDocumentUploadResponse>(
      `/dossiers/${dossierId}/documents`,
      formData,
      { headers: { "Content-Type": "multipart/form-data" } }
    )
    return response.data
  },

  deleteDocument: async (dossierId: string, documentId: string): Promise<void> => {
    await apiClient.delete(`/dossiers/${dossierId}/documents/${documentId}`)
  },

  // ── Generic items (presentations, workspace docs, emails) ──

  listItems: async (dossierId: string, itemType?: string): Promise<DossierItem[]> => {
    const params = itemType ? { item_type: itemType } : undefined
    const response = await apiClient.get<DossierItem[]>(
      `/dossiers/${dossierId}/items`,
      { params }
    )
    return response.data
  },

  addItem: async (dossierId: string, data: DossierItemAdd): Promise<DossierItem> => {
    const response = await apiClient.post<DossierItem>(
      `/dossiers/${dossierId}/items`,
      data
    )
    return response.data
  },

  removeItem: async (dossierId: string, itemId: string): Promise<void> => {
    await apiClient.delete(`/dossiers/${dossierId}/items/${itemId}`)
  },

  listConversations: async (
    dossierId: string
  ): Promise<DossierConversation[]> => {
    const response = await apiClient.get<DossierConversation[]>(
      `/dossiers/${dossierId}/conversations`
    )
    return response.data
  },

  getConversation: async (
    dossierId: string,
    conversationId: string
  ): Promise<Message[]> => {
    const response = await apiClient.get<Message[]>(
      `/dossiers/${dossierId}/conversations/${conversationId}`
    )
    return response.data
  },

  stream: (
    dossierId: string,
    data: DossierChatRequest,
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
    const base = import.meta.env.VITE_API_BASE_URL || window.location.origin
    const url = new URL(`/api/v1/dossiers/${dossierId}/chat/stream`, base)

    const controller = new AbortController()

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

              const messages = buffer.split("\n\n")
              buffer = messages.pop() || ""

              for (const message of messages) {
                parseSSEFrame(message)
              }
            }

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
    })()

    return () => controller.abort()
  },
}
