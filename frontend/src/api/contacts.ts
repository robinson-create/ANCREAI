import apiClient from "./client"

// ── Types ──────────────────────────────────────────────────────────

export interface Company {
  id: string
  tenant_id: string
  company_name: string
  company_domain: string | null
  company_industry: string | null
  company_size: string | null
  notes: string | null
  created_at: string
  updated_at: string
}

export interface Contact {
  id: string
  tenant_id: string
  first_name: string | null
  last_name: string | null
  primary_email: string
  phone: string | null
  title: string | null
  contact_type: string
  language: string | null
  timezone: string | null
  company_id: string | null
  country: string | null
  city: string | null
  address: string | null
  notes: string | null
  tags: string[]
  source: string
  confidence_score: number
  field_confidence: Record<string, number> | null
  created_at: string
  updated_at: string
  company: Company | null
}

export interface ContactBrief {
  id: string
  first_name: string | null
  last_name: string | null
  primary_email: string
  contact_type: string
  company_name: string | null
}

export interface ContactUpdate {
  id: string
  update_type: string
  source: string | null
  field_name: string | null
  old_value: string | null
  new_value: string | null
  confidence: number | null
  evidence: Record<string, unknown> | null
  created_at: string
}

export interface ContactImportRequest {
  source: string
  mail_account_id: string
  date_range_days?: number
}

export interface ContactImportReport {
  total_emails_scanned: number
  contacts_created: number
  contacts_updated: number
  contacts_skipped: number
  errors: string[]
}

export interface ContactCreateData {
  primary_email: string
  first_name?: string | null
  last_name?: string | null
  phone?: string | null
  title?: string | null
  contact_type?: string
  language?: string | null
  timezone?: string | null
  company_id?: string | null
  country?: string | null
  city?: string | null
  address?: string | null
  notes?: string | null
  tags?: string[]
  source?: string
}

export interface ContactUpdateData {
  first_name?: string | null
  last_name?: string | null
  primary_email?: string | null
  phone?: string | null
  title?: string | null
  contact_type?: string | null
  language?: string | null
  timezone?: string | null
  company_id?: string | null
  country?: string | null
  city?: string | null
  address?: string | null
  notes?: string | null
  tags?: string[] | null
}

// ── API ────────────────────────────────────────────────────────────

export const contactsApi = {
  // Contacts
  list: async (params?: {
    search?: string
    contact_type?: string
    source?: string
    limit?: number
    offset?: number
  }): Promise<ContactBrief[]> => {
    const response = await apiClient.get<ContactBrief[]>("/contacts", {
      params,
    })
    return response.data
  },

  search: async (query: string, limit = 10): Promise<Contact[]> => {
    const response = await apiClient.get<Contact[]>("/contacts/search", {
      params: { q: query, limit },
    })
    return response.data
  },

  get: async (id: string): Promise<Contact> => {
    const response = await apiClient.get<Contact>(`/contacts/${id}`)
    return response.data
  },

  create: async (data: ContactCreateData): Promise<Contact> => {
    const response = await apiClient.post<Contact>("/contacts", data)
    return response.data
  },

  update: async (id: string, data: ContactUpdateData): Promise<Contact> => {
    const response = await apiClient.patch<Contact>(`/contacts/${id}`, data)
    return response.data
  },

  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/contacts/${id}`)
  },

  getUpdates: async (id: string): Promise<ContactUpdate[]> => {
    const response = await apiClient.get<ContactUpdate[]>(
      `/contacts/${id}/updates`
    )
    return response.data
  },

  // Import
  importFromEmail: async (
    data: ContactImportRequest
  ): Promise<ContactImportReport> => {
    const response = await apiClient.post<ContactImportReport>(
      "/contacts/import/email",
      data
    )
    return response.data
  },

  // Companies
  listCompanies: async (limit = 50): Promise<Company[]> => {
    const response = await apiClient.get<Company[]>("/contacts/companies", {
      params: { limit },
    })
    return response.data
  },

  createCompany: async (data: Partial<Company>): Promise<Company> => {
    const response = await apiClient.post<Company>(
      "/contacts/companies",
      data
    )
    return response.data
  },
}
