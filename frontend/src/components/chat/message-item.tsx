import { useState } from "react";
import { User, Anchor, ChevronDown, ChevronUp, FileText, AlertCircle, Pencil, CheckCircle2 } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { LocalMessage } from "@/contexts/email-assistant-stream";
import { BlockRenderer } from "@/components/blocks/BlockRenderer";

interface MessageItemProps {
  message: LocalMessage;
  className?: string;
}

export function MessageItem({ message, className }: MessageItemProps) {
  const [showCitations, setShowCitations] = useState(false);

  return (
    <div className={cn("group flex gap-4", className)}>
      {/* Avatar */}
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted">
        {message.role === "user" ? (
          <User className="h-4 w-4 text-muted-foreground" />
        ) : (
          <Anchor
            className={cn(
              "h-4 w-4 text-primary",
              message.isStreaming &&
                (message.content
                  ? "animate-spin-anchor-fast"
                  : "animate-spin-anchor")
            )}
          />
        )}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0 overflow-hidden space-y-2">
        {/* Message text */}
        <div className="prose prose-sm max-w-none break-words overflow-x-auto dark:prose-invert">
          {message.role === "assistant" ? (
            <>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {message.content}
              </ReactMarkdown>
              {message.isStreaming && !message.content && (
                <span className="inline-block h-4 w-1.5 animate-pulse rounded-sm bg-primary" />
              )}
            </>
          ) : (
            <p className="whitespace-pre-wrap text-sm">{message.content}</p>
          )}
        </div>

        {/* Drafting indicator — shown when assistant is writing to editor */}
        {message.isDrafting && (
          <div className="mt-2 flex items-center gap-2 rounded-lg border border-blue-500/30 bg-blue-50/50 dark:bg-blue-950/20 px-3 py-2.5">
            <Pencil className="h-3.5 w-3.5 text-blue-600 dark:text-blue-400 animate-pulse shrink-0" />
            <span className="text-xs font-medium text-blue-700 dark:text-blue-300">
              Rédaction en cours...
            </span>
            <span className="flex gap-0.5 ml-1">
              <span className="h-1 w-1 rounded-full bg-blue-500 animate-bounce" style={{ animationDelay: "0ms" }} />
              <span className="h-1 w-1 rounded-full bg-blue-500 animate-bounce" style={{ animationDelay: "150ms" }} />
              <span className="h-1 w-1 rounded-full bg-blue-500 animate-bounce" style={{ animationDelay: "300ms" }} />
            </span>
          </div>
        )}

        {/* Document inserted confirmation — shown after content was added to editor */}
        {message.documentInserted && !message.isDrafting && (
          <div className="mt-2 flex items-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-50/50 dark:bg-emerald-950/20 px-3 py-2">
            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
            <span className="text-xs font-medium text-emerald-700 dark:text-emerald-300">
              Contenu inséré dans l'éditeur
            </span>
          </div>
        )}

        {/* Interrupted indicator */}
        {message.wasInterrupted && (
          <div className="mt-2 flex items-center gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
            <AlertCircle className="h-3.5 w-3.5 flex-shrink-0" />
            <span>Génération interrompue. Vous pouvez continuer la conversation.</span>
          </div>
        )}

        {/* Generative UI Blocks */}
        {message.blocks && message.blocks.length > 0 && (
          <div className="mt-3 space-y-3">
            {message.blocks.map((block) => (
              <BlockRenderer key={block.id} block={block} />
            ))}
          </div>
        )}

        {/* Citations */}
        {message.citations && message.citations.length > 0 && (
          <div className="mt-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowCitations(!showCitations)}
              className="h-auto py-1 px-2 text-xs"
            >
              {showCitations ? (
                <ChevronUp className="mr-1 h-3 w-3" />
              ) : (
                <ChevronDown className="mr-1 h-3 w-3" />
              )}
              {message.citations.length} source(s)
            </Button>
            {showCitations && (
              <div className="mt-2 space-y-2">
                {message.citations.map((citation, idx) => (
                  <div
                    key={idx}
                    className="rounded-md border bg-muted/50 p-3 text-sm"
                  >
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <FileText className="h-3 w-3" />
                      <span>{citation.document_filename}</span>
                      {citation.page_number && (
                        <span>• Page {citation.page_number}</span>
                      )}
                    </div>
                    <p className="mt-1 text-xs italic text-muted-foreground">
                      "{citation.excerpt}"
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

