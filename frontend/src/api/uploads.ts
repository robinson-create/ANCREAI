import apiClient from "./client"
import type {
  UploadDocument,
  UploadDocumentDetail,
  UploadDownloadUrl,
  UploadPage,
} from "@/types"

export const uploadsApi = {
  list: async (status?: string): Promise<UploadDocument[]> => {
    const params = status ? { status_filter: status } : {}
    const response = await apiClient.get<UploadDocument[]>("/uploads", {
      params,
    })
    return response.data
  },

  get: async (id: string): Promise<UploadDocumentDetail> => {
    const response = await apiClient.get<UploadDocumentDetail>(
      `/uploads/${id}`
    )
    return response.data
  },

  getPages: async (id: string): Promise<UploadPage[]> => {
    const response = await apiClient.get<UploadPage[]>(
      `/uploads/${id}/pages`
    )
    return response.data
  },

  getDownloadUrl: async (id: string): Promise<UploadDownloadUrl> => {
    const response = await apiClient.get<UploadDownloadUrl>(
      `/uploads/${id}/download-url`
    )
    return response.data
  },

  upload: async (files: File[]): Promise<UploadDocument[]> => {
    const formData = new FormData()
    for (const file of files) {
      formData.append("files", file)
    }
    const response = await apiClient.post<UploadDocument[]>(
      "/uploads",
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
    await apiClient.delete(`/uploads/${id}`)
  },

  reprocess: async (id: string): Promise<UploadDocument> => {
    const response = await apiClient.post<UploadDocument>(
      `/uploads/${id}/reprocess`
    )
    return response.data
  },
}
