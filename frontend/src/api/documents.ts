import apiClient from "./client"
import type { Document, DocumentUploadResponse } from "@/types"

export const documentsApi = {
  list: async (collectionId?: string): Promise<Document[]> => {
    const params = collectionId ? { collection_id: collectionId } : {}
    const response = await apiClient.get<Document[]>("/documents", { params })
    return response.data
  },

  get: async (id: string): Promise<Document> => {
    const response = await apiClient.get<Document>(`/documents/${id}`)
    return response.data
  },

  upload: async (
    collectionId: string,
    file: File
  ): Promise<DocumentUploadResponse> => {
    const formData = new FormData()
    formData.append("file", file)

    const response = await apiClient.post<DocumentUploadResponse>(
      `/documents/upload/${collectionId}`,
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      }
    )
    return response.data
  },

  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/documents/${id}`)
  },

  reprocess: async (id: string): Promise<DocumentUploadResponse> => {
    const response = await apiClient.post<DocumentUploadResponse>(
      `/documents/${id}/reprocess`
    )
    return response.data
  },
}
