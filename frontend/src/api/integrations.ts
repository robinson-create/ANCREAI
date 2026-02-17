import apiClient from "./client"

export interface NangoConnection {
  id: string
  provider: string
  nango_connection_id: string
  tenant_id: string
  status: string
  created_at: string
}

export interface NangoConnectResponse {
  connect_url: string
  connection_id: string
  provider: string
}

export const integrationsApi = {
  /**
   * Initiate an OAuth connection via Nango.
   * Returns a connect_url that the frontend should open (popup or redirect).
   */
  connect: async (provider: string): Promise<NangoConnectResponse> => {
    const response = await apiClient.post<NangoConnectResponse>(
      `/integrations/nango/connect/${provider}`
    )
    return response.data
  },

  /**
   * Notify our backend that an OAuth callback completed successfully.
   */
  callback: async (
    providerConfigKey: string,
    connectionId: string
  ): Promise<{ status: string; provider: string }> => {
    const response = await apiClient.get("/integrations/nango/callback", {
      params: { providerConfigKey, connectionId },
    })
    return response.data
  },

  /**
   * List all Nango connections for the current tenant.
   */
  listConnections: async (): Promise<NangoConnection[]> => {
    const response = await apiClient.get<{ connections: NangoConnection[] }>(
      "/integrations/nango/connections"
    )
    return response.data.connections
  },

  /**
   * Delete a Nango connection for a given provider.
   */
  deleteConnection: async (
    provider: string
  ): Promise<{ status: string; provider: string }> => {
    const response = await apiClient.delete(
      `/integrations/nango/connections/${provider}`
    )
    return response.data
  },
}
