import { useLayoutEffect } from "react"
import { useAuth } from "@clerk/clerk-react"
import { setAuthTokenGetter } from "@/api/client"

// Store the getToken function globally so it's available immediately
let globalGetToken: (() => Promise<string | null>) | null = null

/**
 * Component wrapper that sets up auth token using Clerk hooks.
 * Use this inside ClerkProvider.
 */
export function AuthTokenProvider({ children }: { children: React.ReactNode }) {
  const { getToken, isSignedIn, isLoaded } = useAuth()
  
  console.log("AuthTokenProvider render - isLoaded:", isLoaded, "isSignedIn:", isSignedIn)

  // Update global getToken whenever it changes
  globalGetToken = getToken

  // Set up the token getter immediately (synchronously) using useLayoutEffect
  useLayoutEffect(() => {
    console.log("AuthTokenProvider - Setting up token getter (useLayoutEffect)")
    setAuthTokenGetter(async () => {
      try {
        if (!globalGetToken) {
          console.log("Token getter - globalGetToken is null")
          return null
        }
        console.log("Token getter called - attempting to get token from Clerk")
        const token = await globalGetToken()
        console.log("Token getter - got token:", token ? `${token.substring(0, 20)}...` : "null")
        return token
      } catch (error) {
        console.error("Token getter error:", error)
        return null
      }
    })
  }, [])

  return <>{children}</>
}
