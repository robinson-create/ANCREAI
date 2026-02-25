import apiClient from "./client"
import type {
  PresentationListItem,
  PresentationCreate,
  PresentationFull,
  PresentationUpdate,
  Slide,
  SlideUpdate,
  GenerateOutlineRequest,
  GenerateSlidesRequest,
  RegenerateSlideRequest,
  OutlineItem,
  ExportRequest,
  ExportRead,
} from "@/types"

export const presentationsApi = {
  // ── CRUD ──

  list: async (status?: string): Promise<PresentationListItem[]> => {
    const params: Record<string, string> = {}
    if (status) params.status_filter = status
    const { data } = await apiClient.get<PresentationListItem[]>("/presentations", { params })
    return data
  },

  get: async (id: string): Promise<PresentationFull> => {
    const { data } = await apiClient.get<PresentationFull>(`/presentations/${id}`)
    return data
  },

  create: async (body: PresentationCreate): Promise<PresentationFull> => {
    const { data } = await apiClient.post<PresentationFull>("/presentations", body)
    return data
  },

  update: async (id: string, body: PresentationUpdate): Promise<PresentationFull> => {
    const { data } = await apiClient.patch<PresentationFull>(`/presentations/${id}`, body)
    return data
  },

  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/presentations/${id}`)
  },

  duplicate: async (id: string): Promise<PresentationFull> => {
    const { data } = await apiClient.post<PresentationFull>(`/presentations/${id}/duplicate`)
    return data
  },

  // ── Outline ──

  generateOutline: async (
    id: string,
    body: GenerateOutlineRequest,
  ): Promise<{ job_id: string; status: string }> => {
    const { data } = await apiClient.post<{ job_id: string; status: string }>(
      `/presentations/${id}/outline/generate`,
      body,
    )
    return data
  },

  updateOutline: async (id: string, outline: OutlineItem[]): Promise<PresentationFull> => {
    const { data } = await apiClient.patch<PresentationFull>(
      `/presentations/${id}/outline`,
      { outline },
    )
    return data
  },

  // ── Slides ──

  generateSlides: async (
    id: string,
    body: GenerateSlidesRequest,
  ): Promise<{ job_id: string; status: string }> => {
    const { data } = await apiClient.post<{ job_id: string; status: string }>(
      `/presentations/${id}/slides/generate`,
      body,
    )
    return data
  },

  updateSlide: async (presId: string, slideId: string, body: SlideUpdate): Promise<Slide> => {
    const { data } = await apiClient.patch<Slide>(
      `/presentations/${presId}/slides/${slideId}`,
      body,
    )
    return data
  },

  regenerateSlide: async (
    presId: string,
    slideId: string,
    body: RegenerateSlideRequest,
  ): Promise<Slide> => {
    const { data } = await apiClient.post<Slide>(
      `/presentations/${presId}/slides/${slideId}/regenerate`,
      body,
    )
    return data
  },

  addSlide: async (presId: string): Promise<Slide> => {
    const { data } = await apiClient.post<Slide>(`/presentations/${presId}/slides`)
    return data
  },

  deleteSlide: async (presId: string, slideId: string): Promise<void> => {
    await apiClient.delete(`/presentations/${presId}/slides/${slideId}`)
  },

  reorderSlides: async (presId: string, slideIds: string[]): Promise<PresentationFull> => {
    const { data } = await apiClient.post<PresentationFull>(
      `/presentations/${presId}/slides/reorder`,
      { slide_ids: slideIds },
    )
    return data
  },

  // ── Export ──

  exportPresentation: async (
    presId: string,
    body: ExportRequest,
  ): Promise<{ export_id: string; job_id: string; status: string }> => {
    const { data } = await apiClient.post<{ export_id: string; job_id: string; status: string }>(
      `/presentations/${presId}/export`,
      body,
    )
    return data
  },

  listExports: async (presId: string): Promise<ExportRead[]> => {
    const { data } = await apiClient.get<ExportRead[]>(`/presentations/${presId}/exports`)
    return data
  },
}
