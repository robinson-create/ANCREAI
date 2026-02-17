import apiClient from "./client"

export interface TenantSettings {
  mail_signature: string
}

export const settingsApi = {
  get: async (): Promise<TenantSettings> => {
    const response = await apiClient.get<TenantSettings>("/settings")
    return response.data
  },

  update: async (data: Partial<{ mail_signature: string }>): Promise<TenantSettings> => {
    const response = await apiClient.patch<TenantSettings>("/settings", data)
    return response.data
  },
}
