import axios, { AxiosError } from "axios"
import type { ApiError } from "@/types"

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL
  ? `${import.meta.env.VITE_API_BASE_URL}/api/v1`
  : "/api/v1"

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
})

// Token getter function - will be set by auth hook
let getAuthToken: (() => Promise<string | null>) | null = null

export function setAuthTokenGetter(getter: () => Promise<string | null>) {
  getAuthToken = getter
}

export async function getCurrentAuthToken(): Promise<string | null> {
  if (!getAuthToken) {
    console.warn("getAuthToken is not set - cannot get current token")
    return null
  }
  try {
    return await getAuthToken()
  } catch (error) {
    console.error("Failed to get current auth token:", error)
    return null
  }
}

// Request interceptor to add auth token
apiClient.interceptors.request.use(
  async (config) => {
    console.log("API Request interceptor - getAuthToken defined:", !!getAuthToken)
    if (getAuthToken) {
      try {
        const token = await getAuthToken()
        console.log("Got token from Clerk:", token ? `${token.substring(0, 30)}...` : "null")
        if (token) {
          config.headers.Authorization = `Bearer ${token}`
        }
      } catch (error) {
        console.error("Failed to get auth token:", error)
      }
    } else {
      console.warn("getAuthToken is not set - token will not be sent")
    }
    
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiError>) => {
    // Don't redirect on 401 - let Clerk handle authentication
    // The ProtectedRoute component will redirect if needed
    if (error.response?.status === 401) {
      console.warn("API returned 401 - token may be invalid or backend not configured")
    }
    return Promise.reject(error)
  }
)

export default apiClient
