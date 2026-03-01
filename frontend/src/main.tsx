import React from "react"
import ReactDOM from "react-dom/client"
import { BrowserRouter } from "react-router-dom"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { ClerkProvider } from "@clerk/clerk-react"
import { frFR } from "@clerk/localizations"
import { CopilotProvider } from "@/components/copilotkit/CopilotProvider"
import { CopilotActions } from "@/components/copilotkit/CopilotActions"
import { CopilotChatPopup } from "@/components/copilotkit/CopilotChatPopup"
import App from "./App"
import "./index.css"

// Get Clerk publishable key from environment (ignore placeholders so app runs without auth)
const rawKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY
const CLERK_PUBLISHABLE_KEY =
  rawKey &&
  typeof rawKey === "string" &&
  rawKey.length > 20 &&
  !/^pk_(test|live)_xxx$/i.test(rawKey)
    ? rawKey
    : undefined

// CopilotKit is only available when a valid (absolute) runtime URL is set
const copilotUrl = import.meta.env.VITE_COPILOTKIT_RUNTIME_URL || ""
const COPILOTKIT_ENABLED =
  !!copilotUrl && (!copilotUrl.startsWith("/") || !import.meta.env.PROD)

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes
      retry: 1,
    },
  },
})

// Render with or without Clerk based on config
const AppWithProviders = () => (
  <QueryClientProvider client={queryClient}>
    <CopilotProvider>
      <BrowserRouter>
        {COPILOTKIT_ENABLED && <CopilotActions />}
        <App />
      </BrowserRouter>
      {COPILOTKIT_ENABLED && <CopilotChatPopup />}
    </CopilotProvider>
  </QueryClientProvider>
)

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {CLERK_PUBLISHABLE_KEY ? (
      <ClerkProvider 
        publishableKey={CLERK_PUBLISHABLE_KEY}
        localization={frFR}
        afterSignOutUrl="/"
      >
        <AppWithProviders />
      </ClerkProvider>
    ) : (
      <>
        {console.warn(
          "⚠️ Clerk disabled: set VITE_CLERK_PUBLISHABLE_KEY in .env with a real key from https://dashboard.clerk.com (not the placeholder pk_test_xxx)"
        )}
        <AppWithProviders />
      </>
    )}
  </React.StrictMode>
)
