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
  import.meta.env.VITE_COPILOTKIT_RUNTIME_URL || "/copilotkit"

interface CopilotProviderProps {
  children: ReactNode
}

export function CopilotProvider({ children }: CopilotProviderProps) {
  return (
    <CopilotKit runtimeUrl={COPILOTKIT_RUNTIME_URL}>
      {children}
    </CopilotKit>
  )
}
