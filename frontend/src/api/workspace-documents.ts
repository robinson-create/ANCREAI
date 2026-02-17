import apiClient from "./client"
import type {
  AiActionResponse,
  DocModel,
  WorkspaceDocument,
  WorkspaceDocumentCreate,
  WorkspaceDocumentListItem,
  WorkspaceDocumentUpdate,
} from "@/types"

export const workspaceDocumentsApi = {
  list: async (status?: string): Promise<WorkspaceDocumentListItem[]> => {
    const params: Record<string, string> = {}
    if (status) params.status_filter = status
    const { data } = await apiClient.get<WorkspaceDocumentListItem[]>(
      "/workspace-documents",
      { params }
    )
    return data
  },

  get: async (id: string): Promise<WorkspaceDocument> => {
    const { data } = await apiClient.get<WorkspaceDocument>(
      `/workspace-documents/${id}`
    )
    return data
  },

  create: async (
    body: WorkspaceDocumentCreate
  ): Promise<WorkspaceDocument> => {
    const { data } = await apiClient.post<WorkspaceDocument>(
      "/workspace-documents",
      body
    )
    return data
  },

  update: async (
    id: string,
    body: WorkspaceDocumentUpdate
  ): Promise<WorkspaceDocument> => {
    const { data } = await apiClient.patch<WorkspaceDocument>(
      `/workspace-documents/${id}`,
      body
    )
    return data
  },

  patchContent: async (
    id: string,
    content_json: DocModel
  ): Promise<WorkspaceDocument> => {
    const { data } = await apiClient.patch<WorkspaceDocument>(
      `/workspace-documents/${id}/content`,
      { content_json }
    )
    return data
  },

  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/workspace-documents/${id}`)
  },

  duplicate: async (id: string): Promise<WorkspaceDocument> => {
    const { data } = await apiClient.post<WorkspaceDocument>(
      `/workspace-documents/${id}/duplicate`
    )
    return data
  },

  // AI actions

  generate: async (
    id: string,
    body: { prompt: string; collection_ids?: string[]; doc_type?: string }
  ): Promise<AiActionResponse> => {
    const { data } = await apiClient.post<AiActionResponse>(
      `/workspace-documents/${id}/ai/generate`,
      body
    )
    return data
  },

  rewriteBlock: async (
    id: string,
    body: {
      block_id: string
      instruction: string
      collection_ids?: string[]
    }
  ): Promise<AiActionResponse> => {
    const { data } = await apiClient.post<AiActionResponse>(
      `/workspace-documents/${id}/ai/rewrite`,
      body
    )
    return data
  },

  checkDocument: async (
    id: string,
    body: { collection_ids?: string[]; check_type?: string }
  ): Promise<AiActionResponse> => {
    const { data } = await apiClient.post<AiActionResponse>(
      `/workspace-documents/${id}/ai/check`,
      body
    )
    return data
  },

  addLineItem: async (
    id: string,
    body: {
      block_id: string
      description: string
      collection_ids?: string[]
    }
  ): Promise<AiActionResponse> => {
    const { data } = await apiClient.post<AiActionResponse>(
      `/workspace-documents/${id}/ai/add-line-item`,
      body
    )
    return data
  },

  exportPdf: async (id: string): Promise<{ url: string }> => {
    const { data } = await apiClient.post<{ url: string }>(
      `/workspace-documents/${id}/export/pdf`
    )
    return data
  },
}
