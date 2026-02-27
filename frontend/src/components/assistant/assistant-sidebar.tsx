import { useState, useRef, useEffect, useCallback } from "react";
import { Loader2, Send, Square, Sparkles, Mic } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
// NOTE: Radix ScrollArea removed — its internal setRef causes "Maximum update
// depth exceeded" when message content updates rapidly during streaming.
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import { MessageItem } from "@/components/chat/message-item";
import type { LocalMessage } from "@/contexts/email-assistant-stream";

interface AssistantSidebarProps {
  className?: string;
  messages: LocalMessage[];
  isStreaming: boolean;
  selectedAssistantId: string | null;
  onSendMessage: (text: string) => void;
  onResetConversation: () => void;
  onAbortStream: () => void;
  placeholder?: string;
  emptyStateTitle?: string;
  emptyStateDescription?: string;
  additionalActions?: React.ReactNode;
}

export function AssistantSidebar({
  className,
  messages,
  isStreaming,
  selectedAssistantId,
  onSendMessage,
  onResetConversation: _onResetConversation,
  onAbortStream,
  placeholder = "Demandez à l'assistant...",
  emptyStateTitle = "Assistant IA",
  emptyStateDescription = "Posez une question ou demandez de l'aide",
  additionalActions,
}: AssistantSidebarProps) {
  const [input, setInput] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const recognitionRef = useRef<any>(null);
  const wantsRecordingRef = useRef(false);

  // Speech recognition
  const startRecording = useCallback(() => {
    const SpeechRecognitionCtor =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognitionCtor) return;

    if (recognitionRef.current) {
      wantsRecordingRef.current = false;
      recognitionRef.current.stop();
      recognitionRef.current = null;
    }

    wantsRecordingRef.current = true;
    const recognition = new SpeechRecognitionCtor();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "fr-FR";

    recognition.onresult = (event: any) => {
      let finalTranscript = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        if (result?.isFinal) {
          finalTranscript += result[0]?.transcript ?? "";
        }
      }
      if (finalTranscript) {
        setInput((prev) => {
          const separator = prev && !prev.endsWith(" ") && !prev.endsWith("\n") ? " " : "";
          return prev + separator + finalTranscript;
        });
      }
    };

    recognition.onerror = (event: any) => {
      if (event.error === "aborted") return;
      if (event.error === "not-allowed" || event.error === "service-not-allowed") {
        wantsRecordingRef.current = false;
        recognitionRef.current = null;
        setIsRecording(false);
        return;
      }
    };

    recognition.onend = () => {
      if (wantsRecordingRef.current) {
        try { recognition.start(); } catch {
          wantsRecordingRef.current = false;
          recognitionRef.current = null;
          setIsRecording(false);
        }
        return;
      }
      recognitionRef.current = null;
      setIsRecording(false);
    };

    try {
      recognition.start();
      recognitionRef.current = recognition;
      setIsRecording(true);
    } catch (err) {
      console.error("Failed to start recording:", err);
    }
  }, []);

  const stopRecording = useCallback(() => {
    wantsRecordingRef.current = false;
    if (recognitionRef.current) {
      recognitionRef.current.stop();
      recognitionRef.current = null;
    }
    setIsRecording(false);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
    };
  }, []);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "instant" });
  }, [messages]);

  const handleSubmit = (e?: React.FormEvent) => {
    e?.preventDefault();

    if (!input.trim() || isStreaming || !selectedAssistantId) return;

    const userMessage = input.trim();
    setInput("");
    onSendMessage(userMessage);

    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);

    // Auto-resize textarea
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  };

  return (
    <div
      className={cn(
        "flex flex-col h-full bg-muted/30 border-l border-border",
        className
      )}
    >
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto p-4 pt-6">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center px-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 mb-3">
              <Sparkles className="h-6 w-6 text-primary" />
            </div>
            <h4 className="text-sm font-medium mb-2">{emptyStateTitle}</h4>
            <p className="text-xs text-muted-foreground">
              {emptyStateDescription}
            </p>
          </div>
        ) : (
          <div className="space-y-6">
            {messages.map((message) => (
              <MessageItem key={message.id} message={message} />
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Additional actions (e.g., block types for document editor) */}
      {additionalActions}

      <Separator />

      {/* Input area */}
      <div className="p-4">
        {!selectedAssistantId ? (
          <div className="text-xs text-muted-foreground text-center py-2">
            Sélectionnez un assistant pour commencer
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-2">
            <div className="relative">
              <Textarea
                ref={textareaRef}
                value={input}
                onChange={handleInputChange}
                onKeyDown={handleKeyDown}
                placeholder={placeholder}
                disabled={isStreaming}
                className="min-h-[60px] max-h-[120px] resize-none pr-20"
                rows={2}
              />
              <div className="absolute bottom-2 right-2 flex gap-1">
                {/* Microphone button */}
                {!isStreaming && (
                  <Button
                    type="button"
                    size="icon"
                    variant="ghost"
                    className={`h-8 w-8 ${isRecording ? "text-red-500" : ""}`}
                    onClick={isRecording ? stopRecording : startRecording}
                    title={isRecording ? "Arrêter la dictée" : "Dicter"}
                  >
                    <Mic className={`h-4 w-4 ${isRecording ? "animate-pulse" : ""}`} />
                  </Button>
                )}

                {/* Send/Stop button */}
                {isStreaming ? (
                  <Button
                    type="button"
                    size="icon"
                    variant="ghost"
                    className="h-8 w-8"
                    onClick={onAbortStream}
                  >
                    <Square className="h-4 w-4" />
                  </Button>
                ) : (
                  <Button
                    type="submit"
                    size="icon"
                    variant="ghost"
                    className="h-8 w-8"
                    disabled={!input.trim() || !selectedAssistantId}
                  >
                    <Send className="h-4 w-4" />
                  </Button>
                )}
              </div>
            </div>
            <p className="text-xs text-muted-foreground">
              {isStreaming ? (
                <span className="flex items-center gap-1">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  Génération en cours...
                </span>
              ) : (
                "Entrée pour envoyer, Shift+Entrée pour une nouvelle ligne"
              )}
            </p>
          </form>
        )}
      </div>
    </div>
  );
}
