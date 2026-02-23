import { useState, useRef, useEffect, useCallback } from "react";
import { Bot, Loader2, Send, Square, Trash2, Sparkles, Mic } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import { useEmailAssistant, type EmailDraftUpdate } from "@/contexts/email-assistant-stream";
import { MessageItem } from "@/components/chat/message-item";

interface EmailAssistantSidebarProps {
  className?: string;
  onDraftUpdate?: (update: EmailDraftUpdate) => void;
}

export function EmailAssistantSidebar({
  className,
  onDraftUpdate,
}: EmailAssistantSidebarProps) {
  const {
    messages,
    isStreaming,
    selectedAssistantId,
    sendMessage,
    resetConversation,
    abortStream,
  } = useEmailAssistant();

  const [input, setInput] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const scrollAreaRef = useRef<HTMLDivElement>(null);
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
    if (scrollAreaRef.current) {
      const viewport = scrollAreaRef.current.querySelector("[data-radix-scroll-area-viewport]");
      if (viewport) {
        viewport.scrollTop = viewport.scrollHeight;
      }
    }
  }, [messages]);

  const handleSubmit = (e?: React.FormEvent) => {
    e?.preventDefault();

    if (!input.trim() || isStreaming || !selectedAssistantId) return;

    const userMessage = input.trim();
    setInput("");

    // Send message with draft update callback
    sendMessage(userMessage, (update) => {
      if (onDraftUpdate) {
        onDraftUpdate(update);
      }
    });

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
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10">
            <Bot className="h-4 w-4 text-primary" />
          </div>
          <div>
            <h3 className="text-sm font-semibold">Assistant IA</h3>
            <p className="text-xs text-muted-foreground">
              {selectedAssistantId ? "Actif" : "Non configuré"}
            </p>
          </div>
        </div>

        {messages.length > 0 && (
          <Button
            variant="ghost"
            size="icon"
            onClick={resetConversation}
            className="h-8 w-8"
            title="Nouvelle conversation"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        )}
      </div>

      {/* Messages area */}
      <ScrollArea className="flex-1 p-4" ref={scrollAreaRef}>
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center px-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 mb-3">
              <Sparkles className="h-6 w-6 text-primary" />
            </div>
            <h4 className="text-sm font-medium mb-2">Assistant IA</h4>
            <p className="text-xs text-muted-foreground">
              Posez une question ou demandez de l'aide pour rédiger
            </p>
          </div>
        ) : (
          <div className="space-y-6">
            {messages.map((message) => (
              <MessageItem key={message.id} message={message} />
            ))}
          </div>
        )}
      </ScrollArea>

      <Separator />

      {/* Input area */}
      <div className="p-4">
        {!selectedAssistantId ? (
          <div className="text-xs text-muted-foreground text-center py-2">
            Sélectionnez un assistant dans l'éditeur pour commencer
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-2">
            <div className="relative">
              <Textarea
                ref={textareaRef}
                value={input}
                onChange={handleInputChange}
                onKeyDown={handleKeyDown}
                placeholder="Demandez à l'assistant..."
                disabled={isStreaming}
                className="min-h-[60px] max-h-[120px] resize-none pr-12"
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
                    onClick={abortStream}
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
