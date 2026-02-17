import apiClient from "./client"

// ── Types ──

export interface MailAccount {
  id: string
  tenant_id: string
  user_id: string
  provider: string
  email_address: string | null
  status: string
  created_at: string
  updated_at: string
}

export interface MailConnectResponse {
  account_id: string
  connect_url: string
  provider: string
}

export interface MailRecipient {
  name: string
  email: string
}

export interface MailMessageBrief {
  id: string
  provider_message_id: string
  provider_thread_id: string | null
  sender: MailRecipient
  to_recipients: MailRecipient[]
  subject: string | null
  date: string
  snippet: string | null
  is_read: boolean
  is_sent: boolean
  has_attachments: boolean
}

export interface MailMessage extends MailMessageBrief {
  cc_recipients: MailRecipient[] | null
  bcc_recipients: MailRecipient[] | null
  body_text: string | null
  body_html: string | null
  internet_message_id: string | null
  raw_headers: Record<string, string> | null
  is_draft: boolean
  created_at: string
  updated_at: string
}

export interface MailThreadSummary {
  thread_key: string
  subject: string | null
  last_date: string
  snippet: string | null
  message_count: number
  participants: MailRecipient[]
}

export interface MailThreadDetail {
  thread_key: string
  subject: string | null
  messages: MailMessage[]
}

export interface MailSendRequest {
  client_send_id: string
  mail_account_id: string
  mode: "new" | "reply" | "forward"
  to_recipients: MailRecipient[]
  cc_recipients?: MailRecipient[] | null
  bcc_recipients?: MailRecipient[] | null
  subject: string
  body_text?: string | null
  body_html?: string | null
  in_reply_to_message_id?: string | null
  provider_thread_id?: string | null
}

export interface MailSendResponse {
  id: string
  client_send_id: string
  status: string
}

export interface MailSendStatus {
  client_send_id: string
  status: string
  provider_message_id: string | null
  error_code: string | null
  error_message: string | null
}

// ── API ──

export const mailApi = {
  // Accounts
  listAccounts: async (): Promise<MailAccount[]> => {
    const response = await apiClient.get<MailAccount[]>("/mail/accounts")
    return response.data
  },

  connect: async (provider: string): Promise<MailConnectResponse> => {
    const response = await apiClient.post<MailConnectResponse>(
      `/mail/accounts/connect/${provider}`
    )
    return response.data
  },

  finalize: async (accountId: string): Promise<MailAccount> => {
    const response = await apiClient.get<MailAccount>(
      `/mail/accounts/${accountId}/finalize`
    )
    return response.data
  },

  disconnect: async (accountId: string): Promise<void> => {
    await apiClient.delete(`/mail/accounts/${accountId}`)
  },

  // Send
  send: async (data: MailSendRequest): Promise<MailSendResponse> => {
    const response = await apiClient.post<MailSendResponse>("/mail/send", data)
    return response.data
  },

  sendStatus: async (clientSendId: string): Promise<MailSendStatus> => {
    const response = await apiClient.get<MailSendStatus>(
      `/mail/send-status/${clientSendId}`
    )
    return response.data
  },

  // Threads & Messages
  listThreads: async (
    accountId: string,
    params?: { limit?: number; offset?: number }
  ): Promise<MailThreadSummary[]> => {
    const response = await apiClient.get<MailThreadSummary[]>("/mail/threads", {
      params: { account_id: accountId, ...params },
    })
    return response.data
  },

  getThread: async (
    threadKey: string,
    accountId: string
  ): Promise<MailThreadDetail> => {
    const response = await apiClient.get<MailThreadDetail>(
      `/mail/threads/${encodeURIComponent(threadKey)}`,
      { params: { account_id: accountId } }
    )
    return response.data
  },

  getMessage: async (messageId: string): Promise<MailMessage> => {
    const response = await apiClient.get<MailMessage>(
      `/mail/messages/${messageId}`
    )
    return response.data
  },

  // Sync (manual trigger)
  triggerSync: async (accountId: string): Promise<void> => {
    await apiClient.post(`/mail/sync/${accountId}`)
  },
}
