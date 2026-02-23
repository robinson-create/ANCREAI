import { useCallback } from "react";
import { useDocumentAssistant, type DocumentDraftUpdate } from "@/contexts/document-assistant-stream";
import { AssistantSidebar } from "@/components/assistant/assistant-sidebar";

interface DocumentAssistantSidebarProps {
  className?: string;
  onContentUpdate?: (update: DocumentDraftUpdate) => void;
}

export function DocumentAssistantSidebar({
  className,
  onContentUpdate,
}: DocumentAssistantSidebarProps) {
  const {
    messages,
    isStreaming,
    selectedAssistantId,
    sendMessage,
    resetConversation,
    abortStream,
  } = useDocumentAssistant();

  const handleSendMessage = useCallback((text: string) => {
    sendMessage(text, (update) => {
      if (onContentUpdate) {
        onContentUpdate(update);
      }
    });
  }, [sendMessage, onContentUpdate]);

  return (
    <AssistantSidebar
      className={className}
      messages={messages}
      isStreaming={isStreaming}
      selectedAssistantId={selectedAssistantId}
      onSendMessage={handleSendMessage}
      onResetConversation={resetConversation}
      onAbortStream={abortStream}
      placeholder="Demandez à l'assistant..."
      emptyStateTitle="Assistant IA"
      emptyStateDescription="Posez une question ou demandez de l'aide pour éditer"
    />
  );
}
