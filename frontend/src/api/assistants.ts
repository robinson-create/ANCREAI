import apiClient from "./client"
import type { Assistant, AssistantCreate, AssistantUpdate } from "@/types"

export const assistantsApi = {
  list: async (): Promise<Assistant[]> => {
    const response = await apiClient.get<Assistant[]>("/assistants")
    return response.data
  },

  get: async (id: string): Promise<Assistant> => {
    const response = await apiClient.get<Assistant>(`/assistants/${id}`)
    return response.data
  },

  create: async (data: AssistantCreate): Promise<Assistant> => {
    const response = await apiClient.post<Assistant>("/assistants", data)
    return response.data
  },

  update: async (id: string, data: AssistantUpdate): Promise<Assistant> => {
    const response = await apiClient.patch<Assistant>(`/assistants/${id}`, data)
    return response.data
  },

  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/assistants/${id}`)
  },
}
