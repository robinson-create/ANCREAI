import apiClient from "./client"

export interface OnboardingStatus {
  onboarding_completed: boolean
}

export interface OnboardingCompleteRequest {
  first_name: string
  last_name: string
  company_name: string
  memories: string
  website_urls: string[]
}

export interface OnboardingCompleteResponse {
  assistant_id: string
  collection_id: string
  checkout_url: string | null
}

export const onboardingApi = {
  getStatus: async (): Promise<OnboardingStatus> => {
    const response = await apiClient.get<OnboardingStatus>("/onboarding/status")
    return response.data
  },

  complete: async (
    data: OnboardingCompleteRequest
  ): Promise<OnboardingCompleteResponse> => {
    const response = await apiClient.post<OnboardingCompleteResponse>(
      "/onboarding/complete",
      data
    )
    return response.data
  },
}
