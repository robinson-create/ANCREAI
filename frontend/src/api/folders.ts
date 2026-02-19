import apiClient from "./client"
import type { Folder, FolderCreate, FolderItem, FolderItemAdd, FolderUpdate } from "@/types"

export const foldersApi = {
  list: async (params?: { limit?: number; offset?: number }): Promise<Folder[]> => {
    const { data } = await apiClient.get<Folder[]>("/folders", { params })
    return data
  },

  get: async (id: string): Promise<Folder> => {
    const { data } = await apiClient.get<Folder>(`/folders/${id}`)
    return data
  },

  create: async (body: FolderCreate): Promise<Folder> => {
    const { data } = await apiClient.post<Folder>("/folders", body)
    return data
  },

  update: async (id: string, body: FolderUpdate): Promise<Folder> => {
    const { data } = await apiClient.patch<Folder>(`/folders/${id}`, body)
    return data
  },

  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/folders/${id}`)
  },

  listItems: async (
    folderId: string,
    params?: { item_type?: string }
  ): Promise<FolderItem[]> => {
    const { data } = await apiClient.get<FolderItem[]>(
      `/folders/${folderId}/items`,
      { params }
    )
    return data
  },

  addItem: async (folderId: string, body: FolderItemAdd): Promise<FolderItem> => {
    const { data } = await apiClient.post<FolderItem>(
      `/folders/${folderId}/items`,
      body
    )
    return data
  },

  removeItem: async (folderId: string, folderItemId: string): Promise<void> => {
    await apiClient.delete(`/folders/${folderId}/items/${folderItemId}`)
  },
}
