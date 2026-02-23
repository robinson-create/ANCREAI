import { createContext, useContext, useState, useRef, useCallback, ReactNode } from "react";
import { chatApi } from "@/api/chat";
import type { Block, Citation } from "@/types";

export interface LocalMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  isStreaming?: boolean;
  wasInterrupted?: boolean;
  blocks?: Block[];
  citations?: Citation[];
}

export interface EmailDraftUpdate {
  field: "to" | "subject" | "body";
  value: string;
}

interface EmailAssistantContextType {
  messages: LocalMessage[];
  conversationId: string | null;
  isStreaming: boolean;
  selectedAssistantId: string | null;

  setSelectedAssistantId: (id: string | null) => void;
  sendMessage: (
    userText: string,
    onDraftUpdate?: (update: EmailDraftUpdate) => void
  ) => void;
  resetConversation: () => void;
  abortStream: () => void;
}

const EmailAssistantContext = createContext<EmailAssistantContextType | undefined>(undefined);

export function useEmailAssistant() {
  const context = useContext(EmailAssistantContext);
  if (!context) {
    throw new Error("useEmailAssistant must be used within EmailAssistantProvider");
  }
  return context;
}

interface EmailAssistantProviderProps {
  children: ReactNode;
}

export function EmailAssistantProvider({ children }: EmailAssistantProviderProps) {
  const [messages, setMessages] = useState<LocalMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [selectedAssistantId, setSelectedAssistantId] = useState<string | null>(null);

  const abortControllerRef = useRef<(() => void) | null>(null);
  const streamingMessageIdRef = useRef<string | null>(null);

  const abortStream = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current();
      abortControllerRef.current = null;
    }
    setIsStreaming(false);

    // Mark the streaming message as complete and interrupted
    if (streamingMessageIdRef.current) {
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === streamingMessageIdRef.current
            ? { ...msg, isStreaming: false, wasInterrupted: true }
            : msg
        )
      );
      streamingMessageIdRef.current = null;
    }
  }, []);

  const resetConversation = useCallback(() => {
    abortStream();
    setMessages([]);
    setConversationId(null);
  }, [abortStream]);

  const sendMessage = useCallback(
    (userText: string, onDraftUpdate?: (update: EmailDraftUpdate) => void) => {
      if (!selectedAssistantId || isStreaming) return;

      // Abort any existing stream
      if (abortControllerRef.current) {
        abortControllerRef.current();
      }

      // Add user message
      const userMessageId = `user-${Date.now()}`;
      const userMessage: LocalMessage = {
        id: userMessageId,
        role: "user",
        content: userText,
      };

      setMessages((prev) => [...prev, userMessage]);

      // Create assistant message placeholder
      const assistantMessageId = `assistant-${Date.now()}`;
      const assistantMessage: LocalMessage = {
        id: assistantMessageId,
        role: "assistant",
        content: "",
        isStreaming: true,
        blocks: [],
        citations: [],
      };

      setMessages((prev) => [...prev, assistantMessage]);
      setIsStreaming(true);
      streamingMessageIdRef.current = assistantMessageId;

      // Start streaming
      const abort = chatApi.stream(
        selectedAssistantId,
        {
          message: userText,
          conversation_id: conversationId || undefined,
          include_history: true,
        },
        // onToken
        (token) => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId
                ? { ...msg, content: msg.content + token }
                : msg
            )
          );
        },
        // onComplete
        (response) => {
          setIsStreaming(false);
          streamingMessageIdRef.current = null;
          abortControllerRef.current = null;

          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId
                ? {
                    ...msg,
                    isStreaming: false,
                    citations: response.citations || [],
                  }
                : msg
            )
          );

          if (response.conversationId) {
            setConversationId(response.conversationId);
          }

          // Parse response for draft updates if callback provided
          if (onDraftUpdate) {
            const lastMessage = messages[messages.length - 1];
            if (lastMessage?.role === "assistant") {
              parseDraftUpdates(lastMessage.content, onDraftUpdate);
            }
          }
        },
        // onError
        (error) => {
          console.error("Email assistant stream error:", error);
          setIsStreaming(false);
          streamingMessageIdRef.current = null;
          abortControllerRef.current = null;

          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId
                ? {
                    ...msg,
                    content: msg.content || `Erreur: ${error}`,
                    isStreaming: false,
                  }
                : msg
            )
          );
        },
        // onConversationId
        (convId) => {
          setConversationId(convId);
        },
        // onBlock
        (block) => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId
                ? {
                    ...msg,
                    blocks: [...(msg.blocks || []), block],
                  }
                : msg
            )
          );
        }
      );

      abortControllerRef.current = abort;
    },
    [selectedAssistantId, conversationId, isStreaming, messages]
  );

  return (
    <EmailAssistantContext.Provider
      value={{
        messages,
        conversationId,
        isStreaming,
        selectedAssistantId,
        setSelectedAssistantId,
        sendMessage,
        resetConversation,
        abortStream,
      }}
    >
      {children}
    </EmailAssistantContext.Provider>
  );
}

/**
 * Parse AI response for email draft updates
 * Looks for structured patterns like:
 * - TO: email@example.com
 * - SUBJECT: subject text
 * - BODY: body content
 */
function parseDraftUpdates(
  content: string,
  onDraftUpdate: (update: EmailDraftUpdate) => void
) {
  // Look for TO: pattern
  const toMatch = content.match(/(?:^|\n)TO:\s*(.+?)(?:\n|$)/i);
  if (toMatch?.[1]) {
    onDraftUpdate({ field: "to", value: toMatch[1].trim() });
  }

  // Look for SUBJECT: pattern
  const subjectMatch = content.match(/(?:^|\n)SUBJECT:\s*(.+?)(?:\n|$)/i);
  if (subjectMatch?.[1]) {
    onDraftUpdate({ field: "subject", value: subjectMatch[1].trim() });
  }

  // Look for BODY: pattern (multi-line)
  const bodyMatch = content.match(/(?:^|\n)BODY:\s*\n([\s\S]+?)(?:\n---|\n\n|$)/i);
  if (bodyMatch?.[1]) {
    onDraftUpdate({ field: "body", value: bodyMatch[1].trim() });
  }
}
