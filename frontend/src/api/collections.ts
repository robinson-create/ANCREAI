import apiClient from "./client"
import type { Collection, CollectionCreate } from "@/types"

export const collectionsApi = {
  list: async (): Promise<Collection[]> => {
    const response = await apiClient.get<Collection[]>("/collections")
    return response.data
  },

  get: async (id: string): Promise<Collection> => {
    const response = await apiClient.get<Collection>(`/collections/${id}`)
    return response.data
  },

  create: async (data: CollectionCreate): Promise<Collection> => {
    const response = await apiClient.post<Collection>("/collections", data)
    return response.data
  },

  update: async (
    id: string,
    data: Partial<CollectionCreate>
  ): Promise<Collection> => {
    const response = await apiClient.patch<Collection>(`/collections/${id}`, data)
    return response.data
  },

  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/collections/${id}`)
  },
}
