import { useCallback } from "react";
import { useDocumentAssistant, type DocumentDraftUpdate } from "@/contexts/document-assistant-stream";
import { AssistantSidebar } from "@/components/assistant/assistant-sidebar";
import { Button } from "@/components/ui/button";
import {
  Plus,
  FileText,
  Table2,
  Scale,
  ScrollText,
  PenLine,
  Variable
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { DocBlockKind } from "@/types";

interface DocumentAssistantSidebarProps {
  className?: string;
  onContentUpdate?: (update: DocumentDraftUpdate) => void;
  onAddBlock?: (type: DocBlockKind) => void;
}

const BLOCK_TYPES: { type: DocBlockKind; label: string; icon: typeof FileText }[] = [
  { type: "rich_text", label: "Texte riche", icon: FileText },
  { type: "line_items", label: "Lignes (devis/facture)", icon: Table2 },
  { type: "clause", label: "Clause", icon: Scale },
  { type: "terms", label: "Conditions", icon: ScrollText },
  { type: "signature", label: "Signature", icon: PenLine },
  { type: "variables", label: "Variables", icon: Variable },
];

export function DocumentAssistantSidebar({
  className,
  onContentUpdate,
  onAddBlock,
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
    <div className={className}>
      <AssistantSidebar
        messages={messages}
        isStreaming={isStreaming}
        selectedAssistantId={selectedAssistantId}
        onSendMessage={handleSendMessage}
        onResetConversation={resetConversation}
        onAbortStream={abortStream}
        placeholder="Demandez à l'assistant..."
        emptyStateTitle="Assistant IA"
        emptyStateDescription="Posez une question ou demandez de l'aide pour éditer"
        additionalActions={
          onAddBlock && (
            <div className="px-4 pb-3 border-t border-border">
              <div className="flex items-center justify-between mb-2 mt-3">
                <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Blocs
                </span>
              </div>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="outline"
                    size="sm"
                    className="w-full justify-start gap-2"
                  >
                    <Plus className="h-4 w-4" />
                    Ajouter un bloc
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="start" className="w-56">
                  {BLOCK_TYPES.map(({ type, label, icon: Icon }) => (
                    <DropdownMenuItem
                      key={type}
                      onClick={() => onAddBlock(type)}
                      className="gap-2"
                    >
                      <Icon className="h-4 w-4" />
                      {label}
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          )
        }
      />
    </div>
  );
}
