import apiClient from "./client"

export interface SubscriptionInfo {
  plan: string
  status: string
  is_pro: boolean
  current_period_end: string | null
  cancel_at_period_end: boolean
}

export interface UsageInfo {
  plan: string
  status: string
  is_pro: boolean
  daily_chat_requests: number
  daily_chat_limit: number | null
  daily_chat_remaining: number | null
  total_files: number
  file_limit: number | null
  files_remaining: number | null
}

export interface Plan {
  id: string
  name: string
  price: number
  currency: string
  interval: string
  stripe_price_id?: string
  features: string[]
  popular?: boolean
}

export const billingApi = {
  getSubscription: async (): Promise<SubscriptionInfo> => {
    const response = await apiClient.get<SubscriptionInfo>("/billing/subscription")
    return response.data
  },

  getUsage: async (): Promise<UsageInfo> => {
    const response = await apiClient.get<UsageInfo>("/billing/usage")
    return response.data
  },

  getPlans: async (): Promise<Plan[]> => {
    const response = await apiClient.get<{ plans: Plan[] }>("/billing/plans")
    return response.data.plans
  },

  createCheckout: async (
    successUrl: string,
    cancelUrl: string
  ): Promise<string> => {
    const response = await apiClient.post<{ url: string }>("/billing/checkout", {
      success_url: successUrl,
      cancel_url: cancelUrl,
    })
    return response.data.url
  },

  createPortal: async (returnUrl: string): Promise<string> => {
    const response = await apiClient.post<{ url: string }>("/billing/portal", {
      return_url: returnUrl,
    })
    return response.data.url
  },
}
