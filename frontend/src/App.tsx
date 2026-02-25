import { Routes, Route, Navigate } from "react-router-dom"
import { SignIn } from "@clerk/clerk-react"
import { Toaster } from "@/components/ui/toaster"
import { Toaster as Sonner } from "@/components/ui/sonner"
import { AuthTokenProvider } from "@/hooks/use-auth-token"
import { SearchStreamProvider } from "@/contexts/search-stream"
import { DocumentGenerationProvider } from "@/contexts/document-generation-context"
import { SearchViewProvider } from "@/contexts/search-view-context"

// Layouts
import { PublicLayout } from "@/components/layout/public-layout"
import { NewAppLayout } from "@/components/layout/AppLayout"
import { ProtectedRoute } from "@/components/auth/protected-route"

// Public pages
import HomePage from "@/pages/home"
import { PricingPage } from "@/pages/pricing"
import { CGVPage } from "@/pages/cgv"
import PublicOnboarding from "@/pages/public-onboarding"

// Protected pages
import { AssistantsPage } from "@/pages/assistants"
import { DocumentsPage } from "@/pages/documents"
import { DocumentEditorPage } from "@/pages/document-editor"
import { ProfilePage } from "@/pages/profile"
import { BillingPage } from "@/pages/billing"
import { AssistantPage } from "@/pages/assistant-page"
import { EmailComposer } from "@/pages/email-composer"
import { DocumentWorkspace } from "@/pages/document-workspace"
import { SearchPage } from "@/pages/search"
import OnboardingV2 from "@/pages/onboarding-v2"
import OnboardingTransition from "@/pages/onboarding/transition"
import OnboardingSetup from "@/pages/onboarding/setup"
import { CalendarPage } from "@/pages/CalendarPage"
import { ContactsPage } from "@/pages/ContactsPage"
import { ContactDetailPage } from "@/pages/ContactDetailPage"
import { PresentationEditorPage } from "@/pages/presentation-editor"

function App() {
  return (
    <AuthTokenProvider>
      <Routes>
        {/* Home page - standalone (has its own navbar/footer) */}
        <Route path="/" element={<HomePage />} />

        {/* Public routes */}
        <Route element={<PublicLayout />}>
          <Route path="/pricing" element={<PricingPage />} />
          <Route path="/cgv" element={<CGVPage />} />
          <Route
            path="/login/*"
            element={
              <div className="flex min-h-[calc(100vh-4rem)] items-center justify-center py-12">
                <SignIn
                  routing="path"
                  path="/login"
                  signUpUrl="/onboarding"
                  afterSignInUrl="/app/onboarding"
                />
              </div>
            }
          />
        </Route>

        {/* Public onboarding - full screen, no header/footer */}
        <Route path="/onboarding/*" element={<PublicOnboarding />} />

        {/* Onboarding — full screen, no sidebar */}
        <Route
          path="/app/onboarding"
          element={
            <ProtectedRoute skipOnboardingCheck>
              <OnboardingV2 />
            </ProtectedRoute>
          }
        />
        <Route
          path="/app/onboarding/transition"
          element={
            <ProtectedRoute skipOnboardingCheck>
              <OnboardingTransition />
            </ProtectedRoute>
          }
        />
        <Route
          path="/app/onboarding/setup"
          element={
            <ProtectedRoute skipOnboardingCheck>
              <OnboardingSetup />
            </ProtectedRoute>
          }
        />

        {/* Protected routes with new sidebar layout */}
        <Route
          element={
            <ProtectedRoute>
              <SearchStreamProvider>
                <DocumentGenerationProvider>
                  <SearchViewProvider>
                    <NewAppLayout />
                  </SearchViewProvider>
                </DocumentGenerationProvider>
              </SearchStreamProvider>
            </ProtectedRoute>
          }
        >
          <Route path="/app" element={<Navigate to="/app/search" replace />} />
          <Route path="/app/assistants" element={<AssistantsPage />} />
          {/* Redirect old chat route to assistant config page */}
          <Route path="/app/assistants/:id" element={<Navigate to="/app/assistants" replace />} />
          <Route path="/app/documents" element={<DocumentsPage />} />
          <Route path="/app/documents/:id" element={<DocumentEditorPage />} />
          <Route path="/app/presentations/:id" element={<PresentationEditorPage />} />
          <Route path="/app/profile" element={<ProfilePage />} />
          <Route path="/app/billing" element={<BillingPage />} />
          <Route path="/app/assistant/:id" element={<AssistantPage />} />
          <Route path="/app/workspace" element={<DocumentWorkspace />} />
          <Route path="/app/email" element={<EmailComposer />} />
          <Route path="/app/search" element={<SearchPage />} />
          <Route path="/app/contacts" element={<ContactsPage />} />
          <Route path="/app/contacts/:contactId" element={<ContactDetailPage />} />
          <Route path="/app/calendar" element={<CalendarPage />} />
        </Route>
      </Routes>
      <Toaster />
      <Sonner />
    </AuthTokenProvider>
  )
}

export default App
