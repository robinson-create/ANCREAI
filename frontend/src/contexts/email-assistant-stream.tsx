import { createContext, useContext, useState, useRef, useCallback, ReactNode } from "react";
import { chatApi } from "@/api/chat";
import type { Block, Citation } from "@/types";

export interface LocalMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  isStreaming?: boolean;
  isDrafting?: boolean;
  documentInserted?: boolean;
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
            ? { ...msg, isStreaming: false, isDrafting: false, wasInterrupted: true }
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
          context_hint: "email",
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
                    isDrafting: false,
                    citations: response.citations || [],
                  }
                : msg
            )
          );

          if (response.conversationId) {
            setConversationId(response.conversationId);
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
                    isDrafting: false,
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
        },
        // onDraftUpdate — fills the email editor directly
        (draftData) => {
          if (onDraftUpdate) {
            if (draftData.subject) {
              onDraftUpdate({ field: "subject", value: draftData.subject });
            }
            if (draftData.body_draft) {
              onDraftUpdate({ field: "body", value: draftData.body_draft });
            }
          }

          // Mark message as drafting (shows "Rédaction en cours..." indicator)
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId
                ? { ...msg, isDrafting: true }
                : msg
            )
          );
        }
      );

      abortControllerRef.current = abort;
    },
    [selectedAssistantId, conversationId, isStreaming]
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
