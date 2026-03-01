/**
 * SearchStreamContext — persists search streaming state across page navigations.
 *
 * When the user starts a search and navigates away, the fetch/stream continues
 * here (the provider lives above the router). When they come back to the search
 * page, the component reads the current state from this context.
 */

import {
  createContext,
  useContext,
  useState,
  useRef,
  useCallback,
  type ReactNode,
} from "react";
import { chatApi } from "@/api/chat";
import type { Block, Message } from "@/types";

export interface LocalMessage extends Message {
  isStreaming?: boolean;
  wasInterrupted?: boolean;
}

interface SearchStreamContextType {
  // State
  messages: LocalMessage[];
  conversationId: string | null;
  conversationTitle: string | null;
  isSearching: boolean;
  selectedAssistantId: string | null;

  // Setters
  setSelectedAssistantId: (id: string | null) => void;

  // Actions
  sendMessage: (
    assistantId: string,
    userText: string,
    onConversationListChanged?: () => void,
    attachmentIds?: string[],
  ) => void;
  loadConversation: (
    convId: string,
    assistantId: string,
    title: string,
  ) => Promise<void>;
  resetConversation: () => void;
  abortStream: () => void;
}

const SearchStreamContext = createContext<SearchStreamContextType | null>(null);

export function SearchStreamProvider({ children }: { children: ReactNode }) {
  const [messages, setMessages] = useState<LocalMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [conversationTitle, setConversationTitle] = useState<string | null>(
    null,
  );
  const [isSearching, setIsSearching] = useState(false);
  const [selectedAssistantId, setSelectedAssistantId] = useState<string | null>(
    null,
  );

  const abortRef = useRef<(() => void) | null>(null);
  const conversationIdRef = useRef(conversationId);
  conversationIdRef.current = conversationId;
  const isNewConversationRef = useRef(false);

  const isInvalidAssistantHistoryError = (error: string): boolean => {
    const normalized = error.toLowerCase();
    return (
      normalized.includes("invalid_request_assistant_message") ||
      normalized.includes("assistant message must have either content or tool_calls") ||
      normalized.includes("'3240'") ||
      normalized.includes("\"3240\"")
    );
  };

  const abortStream = useCallback(() => {
    if (abortRef.current) {
      abortRef.current();
      abortRef.current = null;
    }
    setIsSearching(false);

    // Mark the streaming message as interrupted
    setMessages((prev) =>
      prev.map((msg) =>
        msg.isStreaming ? { ...msg, isStreaming: false, wasInterrupted: true } : msg
      )
    );
  }, []);

  const resetConversation = useCallback(() => {
    abortStream();
    setMessages([]);
    setConversationId(null);
    conversationIdRef.current = null;
    setConversationTitle(null);
    setIsSearching(false);
  }, [abortStream]);

  const sendMessage = useCallback(
    (
      assistantId: string,
      userText: string,
      onConversationListChanged?: () => void,
      attachmentIds?: string[],
    ) => {
      abortStream();

      isNewConversationRef.current = !conversationIdRef.current;

      if (!conversationIdRef.current) {
        setConversationTitle(userText.slice(0, 60));
      }

      const userMsg: LocalMessage = {
        id: Date.now().toString(),
        role: "user",
        content: userText,
        created_at: new Date().toISOString(),
      };

      const assistantMessageId = (Date.now() + 1).toString();
      const assistantMsg: LocalMessage = {
        id: assistantMessageId,
        role: "assistant",
        content: "",
        isStreaming: true,
        created_at: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setIsSearching(true);
      const startStream = (forceFreshConversation: boolean) => {
        abortRef.current = chatApi.stream(
          assistantId,
          {
            message: userText,
            conversation_id: forceFreshConversation
              ? undefined
              : (conversationIdRef.current || undefined),
            include_history: forceFreshConversation
              ? false
              : !!conversationIdRef.current,
            attachment_ids: attachmentIds?.length ? attachmentIds : undefined,
          },
          (token) => {
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMessageId
                  ? { ...msg, content: msg.content + token }
                  : msg,
              ),
            );
          },
          (response) => {
            setConversationId(response.conversationId);
            conversationIdRef.current = response.conversationId;
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMessageId
                  ? { ...msg, isStreaming: false, citations: response.citations }
                  : msg,
              ),
            );
            setIsSearching(false);
            onConversationListChanged?.();
          },
          (error) => {
            if (!forceFreshConversation && isInvalidAssistantHistoryError(error)) {
              console.warn(
                "Search stream fallback: restarting without history due to invalid assistant message",
                error,
              );
              setConversationId(null);
              conversationIdRef.current = null;
              setConversationTitle(userText.slice(0, 60));
              isNewConversationRef.current = true;
              startStream(true);
              return;
            }

            console.error("Search error:", error);
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMessageId
                  ? {
                      ...msg,
                      content: "Une erreur s'est produite. Réessayez.",
                      isStreaming: false,
                    }
                  : msg,
              ),
            );
            setIsSearching(false);
          },
          (newConversationId) => {
            if (isNewConversationRef.current) {
              setConversationId(newConversationId);
              conversationIdRef.current = newConversationId;
              onConversationListChanged?.();
            }
          },
          (block: Block) => {
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMessageId
                  ? { ...msg, blocks: [...(msg.blocks || []), block] }
                  : msg,
              ),
            );
          },
        );
      };

      startStream(false);
    },
    [abortStream],
  );

  const messagesRef = useRef(messages);
  messagesRef.current = messages;

  const loadConversation = useCallback(
    async (convId: string, assistantId: string, title: string) => {
      // If this conversation is already active in the context (e.g. stream
      // still running or just completed), keep the context data — it may
      // contain a response that hasn't been persisted to the DB yet.
      if (conversationIdRef.current === convId && messagesRef.current.length > 0) {
        setConversationTitle(title);
        setSelectedAssistantId(assistantId);
        return;
      }

      abortStream();
      const history = await chatApi.getConversation(assistantId, convId);
      setMessages(
        history.map((msg) => ({
          id: msg.id,
          role: msg.role as "user" | "assistant" | "system",
          content: msg.content,
          citations: msg.citations,
          blocks: msg.blocks,
          created_at: msg.created_at,
        })),
      );
      setSelectedAssistantId(assistantId);
      setConversationId(convId);
      conversationIdRef.current = convId;
      setConversationTitle(title);
    },
    [abortStream],
  );

  return (
    <SearchStreamContext.Provider
      value={{
        messages,
        conversationId,
        conversationTitle,
        isSearching,
        selectedAssistantId,
        setSelectedAssistantId,
        sendMessage,
        loadConversation,
        resetConversation,
        abortStream,
      }}
    >
      {children}
    </SearchStreamContext.Provider>
  );
}

export function useSearchStream() {
  const ctx = useContext(SearchStreamContext);
  if (!ctx) {
    throw new Error("useSearchStream must be used within SearchStreamProvider");
  }
  return ctx;
}
