import apiClient from "./client"
import type {
  OrgMember,
  TenantWithMeta,
  TenantStats,
  AssistantPermission,
} from "@/types"

export const organizationApi = {
  // Tenant
  getTenant: async (): Promise<TenantWithMeta> => {
    const response = await apiClient.get<TenantWithMeta>("/tenants/me")
    return response.data
  },

  updateTenant: async (
    data: { name?: string; settings?: Record<string, unknown> }
  ): Promise<TenantWithMeta> => {
    const response = await apiClient.patch<TenantWithMeta>("/tenants/me", data)
    return response.data
  },

  getStats: async (): Promise<TenantStats> => {
    const response = await apiClient.get<TenantStats>("/tenants/me/stats")
    return response.data
  },

  // Members
  listMembers: async (): Promise<OrgMember[]> => {
    const response = await apiClient.get<OrgMember[]>("/tenants/me/members")
    return response.data
  },

  inviteMember: async (email: string): Promise<OrgMember> => {
    const response = await apiClient.post<OrgMember>("/tenants/me/members", {
      email,
    })
    return response.data
  },

  updateMember: async (
    memberId: string,
    data: { role?: string; status?: string }
  ): Promise<OrgMember> => {
    const response = await apiClient.patch<OrgMember>(
      `/tenants/me/members/${memberId}`,
      data
    )
    return response.data
  },

  removeMember: async (memberId: string): Promise<void> => {
    await apiClient.delete(`/tenants/me/members/${memberId}`)
  },

  // Assistant permissions
  listPermissions: async (assistantId: string): Promise<AssistantPermission[]> => {
    const response = await apiClient.get<AssistantPermission[]>(
      `/assistants/${assistantId}/permissions`
    )
    return response.data
  },

  setPermissions: async (
    assistantId: string,
    memberIds: string[]
  ): Promise<AssistantPermission[]> => {
    const response = await apiClient.put<AssistantPermission[]>(
      `/assistants/${assistantId}/permissions`,
      { member_ids: memberIds }
    )
    return response.data
  },

  addPermissions: async (
    assistantId: string,
    memberIds: string[]
  ): Promise<AssistantPermission[]> => {
    const response = await apiClient.post<AssistantPermission[]>(
      `/assistants/${assistantId}/permissions`,
      { member_ids: memberIds }
    )
    return response.data
  },

  removePermission: async (
    assistantId: string,
    memberId: string
  ): Promise<void> => {
    await apiClient.delete(
      `/assistants/${assistantId}/permissions/${memberId}`
    )
  },
}
