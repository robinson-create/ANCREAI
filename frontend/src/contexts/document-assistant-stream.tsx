import { createContext, useContext, useState, useRef, useCallback, ReactNode, useEffect } from "react";
import { chatApi } from "@/api/chat";
import type { Block, Citation } from "@/types";

export interface LocalMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  isStreaming?: boolean;
  blocks?: Block[];
  citations?: Citation[];
}

export interface DocumentDraftUpdate {
  content: string;
  blockId?: string;
}

interface DocumentAssistantContextType {
  messages: LocalMessage[];
  conversationId: string | null;
  isStreaming: boolean;
  selectedAssistantId: string | null;

  setSelectedAssistantId: (id: string | null) => void;
  sendMessage: (
    userText: string,
    onContentUpdate?: (update: DocumentDraftUpdate) => void
  ) => void;
  resetConversation: () => void;
  abortStream: () => void;
  loadHistoryForDocument: (documentId: string) => void;
}

const DocumentAssistantContext = createContext<DocumentAssistantContextType | undefined>(undefined);

export function useDocumentAssistant() {
  const context = useContext(DocumentAssistantContext);
  if (!context) {
    throw new Error("useDocumentAssistant must be used within DocumentAssistantProvider");
  }
  return context;
}

interface DocumentAssistantProviderProps {
  children: ReactNode;
  documentId?: string;
}

// Storage key for conversation history per document
const STORAGE_PREFIX = "doc-assistant-history-";

function saveHistoryForDocument(documentId: string, messages: LocalMessage[], conversationId: string | null) {
  try {
    const data = {
      messages,
      conversationId,
      savedAt: new Date().toISOString(),
    };
    localStorage.setItem(`${STORAGE_PREFIX}${documentId}`, JSON.stringify(data));
  } catch (err) {
    console.error("Failed to save conversation history:", err);
  }
}

function loadHistoryFromStorage(documentId: string): { messages: LocalMessage[], conversationId: string | null } | null {
  try {
    const raw = localStorage.getItem(`${STORAGE_PREFIX}${documentId}`);
    if (!raw) return null;
    const data = JSON.parse(raw);
    // Only restore non-streaming messages
    const messages = (data.messages || []).map((m: LocalMessage) => ({
      ...m,
      isStreaming: false,
    }));
    return {
      messages,
      conversationId: data.conversationId || null,
    };
  } catch (err) {
    console.error("Failed to load conversation history:", err);
    return null;
  }
}

export function DocumentAssistantProvider({ children, documentId }: DocumentAssistantProviderProps) {
  const [messages, setMessages] = useState<LocalMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [selectedAssistantId, setSelectedAssistantId] = useState<string | null>(null);

  const abortControllerRef = useRef<(() => void) | null>(null);
  const streamingMessageIdRef = useRef<string | null>(null);
  const currentDocIdRef = useRef<string | undefined>(documentId);

  // Load history when documentId changes
  useEffect(() => {
    if (documentId && documentId !== currentDocIdRef.current) {
      currentDocIdRef.current = documentId;
      const history = loadHistoryFromStorage(documentId);
      if (history) {
        setMessages(history.messages);
        setConversationId(history.conversationId);
      } else {
        setMessages([]);
        setConversationId(null);
      }
    }
  }, [documentId]);

  // Auto-save history when messages change
  useEffect(() => {
    if (documentId && messages.length > 0 && !isStreaming) {
      saveHistoryForDocument(documentId, messages, conversationId);
    }
  }, [messages, conversationId, isStreaming, documentId]);

  const abortStream = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current();
      abortControllerRef.current = null;
    }
    setIsStreaming(false);

    if (streamingMessageIdRef.current) {
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === streamingMessageIdRef.current
            ? { ...msg, isStreaming: false }
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
    if (documentId) {
      try {
        localStorage.removeItem(`${STORAGE_PREFIX}${documentId}`);
      } catch (err) {
        console.error("Failed to clear history:", err);
      }
    }
  }, [abortStream, documentId]);

  const loadHistoryForDocument = useCallback((docId: string) => {
    const history = loadHistoryFromStorage(docId);
    if (history) {
      setMessages(history.messages);
      setConversationId(history.conversationId);
    } else {
      setMessages([]);
      setConversationId(null);
    }
  }, []);

  const sendMessage = useCallback(
    (userText: string, onContentUpdate?: (update: DocumentDraftUpdate) => void) => {
      if (!selectedAssistantId || isStreaming) return;

      if (abortControllerRef.current) {
        abortControllerRef.current();
      }

      const userMessageId = `user-${Date.now()}`;
      const userMessage: LocalMessage = {
        id: userMessageId,
        role: "user",
        content: userText,
      };

      setMessages((prev) => [...prev, userMessage]);

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

          // Optionally notify parent of content updates
          if (onContentUpdate) {
            const lastMessage = messages[messages.length - 1];
            if (lastMessage?.role === "assistant" && lastMessage.content) {
              onContentUpdate({ content: lastMessage.content });
            }
          }
        },
        // onError
        (error) => {
          console.error("Document assistant stream error:", error);
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
    <DocumentAssistantContext.Provider
      value={{
        messages,
        conversationId,
        isStreaming,
        selectedAssistantId,
        setSelectedAssistantId,
        sendMessage,
        resetConversation,
        abortStream,
        loadHistoryForDocument,
      }}
    >
      {children}
    </DocumentAssistantContext.Provider>
  );
}
