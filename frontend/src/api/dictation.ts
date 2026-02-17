import apiClient from "./client"

export interface TranscriptionResponse {
  text: string
  duration_seconds: number
  remaining_seconds: number
}

export const dictationApi = {
  transcribe: async (
    audioBlob: Blob,
    language: string = "fr"
  ): Promise<TranscriptionResponse> => {
    const formData = new FormData()
    formData.append("file", audioBlob, "recording.webm")

    const response = await apiClient.post<TranscriptionResponse>(
      `/dictation/transcribe?language=${encodeURIComponent(language)}`,
      formData,
      {
        headers: { "Content-Type": "multipart/form-data" },
      }
    )
    return response.data
  },
}
