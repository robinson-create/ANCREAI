import { RedirectToSignIn, useAuth } from "@clerk/clerk-react"
import { useQuery } from "@tanstack/react-query"
import { Navigate } from "react-router-dom"
import { onboardingApi } from "@/api/onboarding"

interface ProtectedRouteProps {
  children: React.ReactNode
  /** Skip onboarding check (used on the onboarding page itself) */
  skipOnboardingCheck?: boolean
}

export function ProtectedRoute({
  children,
  skipOnboardingCheck = false,
}: ProtectedRouteProps) {
  const { isLoaded, isSignedIn } = useAuth()

  // Check onboarding status (only when signed in and not skipping)
  const {
    data: onboardingStatus,
    isLoading: isOnboardingLoading,
    isError: isOnboardingError,
  } = useQuery({
    queryKey: ["onboarding-status"],
    queryFn: onboardingApi.getStatus,
    enabled: isLoaded && isSignedIn === true && !skipOnboardingCheck,
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes
    retry: 1,
  })

  // Show loading state while Clerk loads
  if (!isLoaded) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    )
  }

  if (!isSignedIn) {
    return <RedirectToSignIn />
  }

  // Wait for onboarding check (unless skipping)
  if (!skipOnboardingCheck && isOnboardingLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    )
  }

  // If onboarding API fails, let the user through (don't block)
  if (isOnboardingError) {
    return <>{children}</>
  }

  // Redirect to onboarding if not completed
  if (
    !skipOnboardingCheck &&
    onboardingStatus &&
    !onboardingStatus.onboarding_completed
  ) {
    return <Navigate to="/app/onboarding" replace />
  }

  return <>{children}</>
}
