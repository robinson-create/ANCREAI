/**
 * CopilotKit provider wrapper.
 *
 * Wraps children with the CopilotKit context and registers
 * global actions (tools) that the LLM can invoke to render
 * structured UI in the chat.
 *
 * Architecture note:
 *   CopilotKit uses its own LLM pipeline (via the runtime).
 *   Our existing SSE chat (RAG pipeline) is untouched.
 *   CopilotKit adds a complementary "AI assistant" popup that
 *   can call tools and render generative UI cards.
 */

import { CopilotKit } from "@copilotkit/react-core"
import type { ReactNode } from "react"

const COPILOTKIT_RUNTIME_URL =
  import.meta.env.VITE_COPILOTKIT_RUNTIME_URL || ""

interface CopilotProviderProps {
  children: ReactNode
}

/**
 * Wraps children with CopilotKit only when a valid runtime URL is configured.
 * In production (Vercel), the default "/copilotkit" path won't work since
 * there's no Vite proxy — so we skip CopilotKit unless an absolute URL is set.
 */
export function CopilotProvider({ children }: CopilotProviderProps) {
  // Skip CopilotKit if no runtime URL or if it's a relative path in production
  const isRelative = COPILOTKIT_RUNTIME_URL.startsWith("/") || !COPILOTKIT_RUNTIME_URL
  const isProduction = import.meta.env.PROD

  if (!COPILOTKIT_RUNTIME_URL || (isRelative && isProduction)) {
    return <>{children}</>
  }

  return (
    <CopilotKit runtimeUrl={COPILOTKIT_RUNTIME_URL}>
      {children}
    </CopilotKit>
  )
}
