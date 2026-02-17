import { useState, useRef, useEffect, useCallback } from "react";
import { useSearchParams, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Search,
  User,
  FileText,
  Plug,
  ChevronDown,
  ChevronUp,
  ChevronRight,
  Loader2,
  Send,
  Anchor,
  MessageSquare,
  Clock,
  Mic,
  MicOff,
  Copy,
  Check,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import { assistantsApi } from "@/api/assistants";
import { chatApi } from "@/api/chat";
import type { Assistant, Citation } from "@/types";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useCopilotReadable } from "@copilotkit/react-core";
import { BlockRenderer } from "@/components/blocks/BlockRenderer";
import { useSearchStream } from "@/contexts/search-stream";

const suggestions = [
  "Résume le dernier échange avec le client Dupont",
  "Quelles sont les clauses du NDA en cours ?",
  "Trouve les tarifs actuels",
  "Cherche le contrat de prestation",
];

// ── Speech Recognition types (Web Speech API) ──

interface SpeechRecognitionEvent extends Event {
  results: SpeechRecognitionResultList;
  resultIndex: number;
}

interface SpeechRecognitionErrorEvent extends Event {
  error: string;
}

interface SpeechRecognitionInstance extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onresult: ((ev: SpeechRecognitionEvent) => void) | null;
  onerror: ((ev: SpeechRecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
}

declare global {
  interface Window {
    SpeechRecognition: new () => SpeechRecognitionInstance;
    webkitSpeechRecognition: new () => SpeechRecognitionInstance;
  }
}

function formatRelativeDate(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "À l'instant";
  if (diffMins < 60) return `Il y a ${diffMins} min`;
  if (diffHours < 24) return `Il y a ${diffHours}h`;
  if (diffDays < 7) return `Il y a ${diffDays}j`;
  return date.toLocaleDateString("fr-FR", { day: "numeric", month: "short" });
}

// ── Main component ──

export function SearchPage() {
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();

  // ── Stream state from persistent context (survives navigation) ──
  const {
    messages,
    conversationTitle,
    isSearching,
    selectedAssistantId,
    setSelectedAssistantId,
    sendMessage,
    loadConversation,
    resetConversation,
  } = useSearchStream();

  // ── Local UI state (resets on unmount — that's fine) ──
  const [query, setQuery] = useState("");
  const [expandedCitations, setExpandedCitations] = useState<Set<string>>(new Set());
  const [isRecording, setIsRecording] = useState(false);
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null);
  const [forceListView, setForceListView] = useState(false);

  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const initialLoadDone = useRef(false);

  // ── Speech Recognition (native Web Speech API) ──
  const wantsRecordingRef = useRef(false);

  const startRecording = useCallback(() => {
    const SpeechRecognitionCtor =
      window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognitionCtor) {
      console.error("Speech recognition not supported");
      return;
    }

    wantsRecordingRef.current = true;

    const recognition = new SpeechRecognitionCtor();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "fr-FR";

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let finalTranscript = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        if (result.isFinal) {
          finalTranscript += result[0].transcript;
        }
      }
      if (finalTranscript) {
        setQuery((prev) => {
          const separator = prev && !prev.endsWith(" ") ? " " : "";
          return prev + separator + finalTranscript;
        });
      }
    };

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      if (event.error === "aborted") return;
      if (event.error === "not-allowed" || event.error === "service-not-allowed") {
        console.error("Microphone access denied:", event.error);
        wantsRecordingRef.current = false;
        recognitionRef.current = null;
        setIsRecording(false);
        return;
      }
      console.error("Speech recognition error:", event.error);
    };

    recognition.onend = () => {
      if (wantsRecordingRef.current) {
        try {
          recognition.start();
        } catch {
          wantsRecordingRef.current = false;
          recognitionRef.current = null;
          setIsRecording(false);
        }
        return;
      }
      recognitionRef.current = null;
      setIsRecording(false);
    };

    recognitionRef.current = recognition;
    recognition.start();
    setIsRecording(true);
  }, []);

  const stopRecording = useCallback(() => {
    wantsRecordingRef.current = false;
    if (recognitionRef.current) {
      recognitionRef.current.stop();
    }
  }, []);

  const toggleRecording = useCallback(() => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  }, [isRecording, startRecording, stopRecording]);

  // Fetch assistants
  const { data: assistants = [] } = useQuery({
    queryKey: ["assistants"],
    queryFn: assistantsApi.list,
  });

  // Fetch conversations for ALL assistants (unified history)
  const [allConversations, setAllConversations] = useState<
    Array<{
      id: string;
      title: string;
      started_at: string;
      last_message_at: string;
      message_count: number;
      assistant: Assistant;
    }>
  >([]);

  const fetchAllConversations = useCallback(async () => {
    if (assistants.length === 0) return;
    const results = await Promise.allSettled(
      assistants.map(async (a: Assistant) => {
        const convos = await chatApi.listConversations(a.id);
        return convos.map((c) => ({ ...c, assistant: a }));
      })
    );
    const all = results
      .filter((r): r is PromiseFulfilledResult<typeof allConversations> => r.status === "fulfilled")
      .flatMap((r) => r.value)
      .sort((a, b) => new Date(b.last_message_at).getTime() - new Date(a.last_message_at).getTime());
    setAllConversations(all);
  }, [assistants]);

  useEffect(() => {
    fetchAllConversations();
  }, [fetchAllConversations]);

  // Auto-select first assistant (only if context doesn't already have one)
  useEffect(() => {
    if (assistants.length === 0) return;
    const paramAssistant = searchParams.get("assistant");
    if (paramAssistant && assistants.some((a: Assistant) => a.id === paramAssistant)) {
      setSelectedAssistantId(paramAssistant);
    } else if (!selectedAssistantId) {
      setSelectedAssistantId(assistants[0].id);
    }
  }, [assistants, selectedAssistantId, searchParams, setSelectedAssistantId]);

  // Auto-load conversation from URL param
  useEffect(() => {
    const paramConversation = searchParams.get("conversation");
    const paramAssistant = searchParams.get("assistant");
    if (
      paramConversation &&
      paramAssistant &&
      selectedAssistantId === paramAssistant &&
      !initialLoadDone.current
    ) {
      initialLoadDone.current = true;
      loadConversation(paramConversation, paramAssistant, "Conversation")
        .then(() => {
          setSearchParams({}, { replace: true });
        })
        .catch((error) => {
          console.error("Failed to load conversation from URL:", error);
          setSearchParams({}, { replace: true });
        });
    }
  }, [selectedAssistantId, searchParams, setSearchParams, loadConversation]);

  // Scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSearch = useCallback(() => {
    if (!query.trim() || !selectedAssistantId) return;

    // If we're on the list view, the user wants a fresh conversation
    // (not a follow-up to the previous one still in context).
    if (forceListView) {
      resetConversation();
    }
    setForceListView(false);

    const userText = query.trim();
    setQuery("");
    sendMessage(selectedAssistantId, userText, fetchAllConversations);
  }, [query, selectedAssistantId, sendMessage, fetchAllConversations, forceListView, resetConversation]);

  // Auto-search from ?q= param (e.g. from dashboard prompt)
  const pendingQueryRef = useRef<string | null>(null);

  useEffect(() => {
    const q = searchParams.get("q");
    if (q && !pendingQueryRef.current) {
      pendingQueryRef.current = q;
      setQuery(q);
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        next.delete("q");
        return next;
      }, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  useEffect(() => {
    if (pendingQueryRef.current && selectedAssistantId && query === pendingQueryRef.current) {
      pendingQueryRef.current = null;
      const timer = setTimeout(() => handleSearch(), 50);
      return () => clearTimeout(timer);
    }
  }, [query, selectedAssistantId, handleSearch]);

  const handleBackToList = useCallback(() => {
    // Only hide the conversation view — do NOT clear context data.
    // The stream keeps running in the background so the response is
    // still available when the user clicks back on the same conversation.
    setForceListView(true);
    setQuery("");
    setExpandedCitations(new Set());
    initialLoadDone.current = false;
    setSearchParams({}, { replace: true });
    fetchAllConversations();
  }, [setSearchParams, fetchAllConversations]);

  // Reset to list view when sidebar "Recherche" is clicked again
  useEffect(() => {
    if ((location.state as { reset?: number })?.reset) {
      handleBackToList();
      window.history.replaceState({}, "");
    }
  }, [(location.state as { reset?: number })?.reset]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleLoadConversation = useCallback(async (convId: string, assistantId: string, title: string) => {
    try {
      setForceListView(false);
      await loadConversation(convId, assistantId, title);
      setExpandedCitations(new Set());
      // Scroll to bottom instantly after loading (smooth is too slow for full history)
      requestAnimationFrame(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "instant" });
      });
    } catch (error) {
      console.error("Failed to load conversation:", error);
    }
  }, [loadConversation]);

  const toggleCitations = (messageId: string) => {
    setExpandedCitations((prev) => {
      const next = new Set(prev);
      if (next.has(messageId)) {
        next.delete(messageId);
      } else {
        next.add(messageId);
      }
      return next;
    });
  };

  const selectedAssistant = assistants.find((a: Assistant) => a.id === selectedAssistantId);
  const hasConversation = messages.length > 0 && !forceListView;

  const handleCopy = useCallback((messageId: string, content: string) => {
    navigator.clipboard.writeText(content);
    setCopiedMessageId(messageId);
    setTimeout(() => setCopiedMessageId(null), 2000);
  }, []);

  // Expose search context to CopilotKit popup
  useCopilotReadable({
    description: "Current search conversation messages",
    value: messages.length > 0
      ? messages.map((m) => `${m.role}: ${m.content}`).join("\n")
      : "No active search conversation",
  });

  useCopilotReadable({
    description: "Currently selected assistant for search",
    value: selectedAssistant
      ? `Assistant: ${selectedAssistant.name} (model: ${selectedAssistant.model})`
      : "No assistant selected",
  });

  // Get assistant settings helper
  const getAssistantEmoji = (a: Assistant) => {
    const settings = (a.settings || {}) as Record<string, unknown>;
    return (settings.emoji as string) || "";
  };

  return (
    <div className="flex flex-col h-full">
      {/* ── Header ── */}
      <div className="flex items-center gap-2 sm:gap-3 h-auto min-h-[3.5rem] px-3 sm:px-5 py-2 border-b border-border bg-surface-elevated shrink-0 flex-wrap">
        {hasConversation ? (
          /* Breadcrumb when in conversation */
          <div className="flex items-center gap-1.5 min-w-0 flex-1">
            <button
              onClick={handleBackToList}
              className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors shrink-0"
            >
              <Search className="h-4 w-4" />
              <span className="hidden sm:inline">Recherche</span>
            </button>
            <ChevronRight className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
            <span className="text-sm font-medium text-foreground truncate">
              {conversationTitle || "Conversation"}
            </span>
            {selectedAssistant && (
              <Badge variant="outline" className="ml-2 text-[10px] shrink-0 hidden sm:inline-flex">
                {getAssistantEmoji(selectedAssistant) && (
                  <span className="mr-1">{getAssistantEmoji(selectedAssistant)}</span>
                )}
                {selectedAssistant.name}
              </Badge>
            )}
          </div>
        ) : (
          /* Normal header */
          <>
            <Search className="h-4 w-4 text-primary shrink-0 hidden sm:block" />
            <h1 className="font-display font-semibold text-foreground text-sm sm:text-base">
              Recherche
            </h1>
            {assistants.length > 0 && (
              <select
                value={selectedAssistantId || ""}
                onChange={(e) => setSelectedAssistantId(e.target.value)}
                className="ml-auto text-xs bg-card border border-border rounded-md px-2 py-1.5 text-foreground outline-none focus:ring-4 focus:ring-ring/15 focus:border-ring/35"
              >
                {assistants.map((a: Assistant) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </select>
            )}
          </>
        )}
      </div>

      {/* ── Content ── */}
      {!hasConversation ? (
        /* ═══ List view: search bar + history cards ═══ */
        <div className="flex-1 overflow-auto bg-surface">
          <div className="max-w-3xl mx-auto px-4 sm:px-6">
            {/* Search hero */}
            <div className="pt-12 pb-6 text-center space-y-3">
              <div className="mx-auto w-14 h-14 rounded-lg bg-accent flex items-center justify-center">
                <Search className="h-6 w-6 text-primary" />
              </div>
              <div>
                <h2 className="font-display text-xl font-semibold text-foreground">
                  Interrogez vos sources
                </h2>
                <p className="text-sm text-muted-foreground mt-1 max-w-md mx-auto">
                  Posez une question en langage naturel. L'IA cherchera dans vos
                  documents et sources connectées.
                </p>
              </div>
              {selectedAssistant && (
                <div className="flex justify-center gap-2">
                  {selectedAssistant.collection_ids.length > 0 && (
                    <Badge variant="outline" className="gap-1">
                      <FileText className="h-3 w-3" />
                      {selectedAssistant.collection_ids.length} collection{selectedAssistant.collection_ids.length > 1 ? "s" : ""}
                    </Badge>
                  )}
                  {selectedAssistant.integration_ids.length > 0 && (
                    <Badge variant="outline" className="gap-1">
                      <Plug className="h-3 w-3" />
                      {selectedAssistant.integration_ids.length} connecteur{selectedAssistant.integration_ids.length > 1 ? "s" : ""}
                    </Badge>
                  )}
                </div>
              )}
            </div>

            {/* Search input */}
            <div className="sticky top-0 z-10 bg-surface pb-4">
              <div className="relative">
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                  placeholder="Rechercher dans vos sources..."
                  className="w-full text-sm bg-card border border-border rounded-lg px-4 py-4 pr-24 outline-none focus:ring-4 focus:ring-ring/15 focus:border-ring/35 text-foreground placeholder:text-muted-foreground shadow-soft transition-colors"
                  disabled={isSearching}
                  autoFocus
                />
                <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
                  <button
                    type="button"
                    onClick={toggleRecording}
                    disabled={isSearching}
                    className={cn(
                      "inline-flex h-9 w-9 items-center justify-center rounded-full transition-colors",
                      isRecording
                        ? "bg-destructive text-destructive-foreground animate-pulse"
                        : "text-muted-foreground hover:bg-muted hover:text-foreground"
                    )}
                    title={isRecording ? "Arrêter la dictée" : "Dicter"}
                  >
                    {isRecording ? (
                      <MicOff className="h-3.5 w-3.5" />
                    ) : (
                      <Mic className="h-4 w-4" />
                    )}
                  </button>
                  <Button
                    variant="premium"
                    size="icon"
                    className="h-9 w-9 rounded-full"
                    onClick={handleSearch}
                    disabled={!query.trim() || isSearching || !selectedAssistantId}
                  >
                    {isSearching ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Send className="h-4 w-4" />
                    )}
                  </Button>
                </div>
              </div>
            </div>

            {/* Suggestions */}
            <div className="space-y-2 pb-6">
              <p className="text-xs text-muted-foreground font-medium uppercase tracking-wider">
                Suggestions
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {suggestions.map((s) => (
                  <button
                    key={s}
                    onClick={() => setQuery(s)}
                    className="text-left text-sm px-4 py-3 rounded-lg bg-card border border-border hover:border-primary/30 hover:shadow-soft transition-all text-foreground"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>

            {/* ── History cards ── */}
            {allConversations.length > 0 && (
              <div className="pb-8">
                <div className="flex items-center gap-3 mb-4">
                  <div className="h-px flex-1 bg-border" />
                  <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    <Clock className="h-3.5 w-3.5" />
                    Recherches récentes
                  </div>
                  <div className="h-px flex-1 bg-border" />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {allConversations.map((conv) => {
                    const emoji = getAssistantEmoji(conv.assistant);
                    return (
                      <button
                        key={conv.id}
                        onClick={() => handleLoadConversation(conv.id, conv.assistant.id, conv.title)}
                        className="group flex flex-col text-left p-4 rounded-lg bg-card border border-border hover:shadow-soft hover:border-primary/20 transition-all"
                      >
                        <div className="flex items-start gap-3 mb-3">
                          <div className="w-8 h-8 rounded-lg bg-violet-500/10 flex items-center justify-center shrink-0">
                            {emoji ? (
                              <span className="text-sm">{emoji}</span>
                            ) : (
                              <MessageSquare className="h-4 w-4 text-violet-500" />
                            )}
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-foreground line-clamp-2 leading-snug">
                              {conv.title}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center gap-1.5 mt-auto min-w-0">
                          <span className="text-[11px] text-muted-foreground truncate">
                            {conv.assistant.name}
                          </span>
                          <span className="text-muted-foreground/30 shrink-0">·</span>
                          <Badge variant="outline" className="text-[10px] px-1.5 py-0 shrink-0 whitespace-nowrap">
                            {conv.message_count} msg
                          </Badge>
                          <span className="ml-auto text-[11px] text-muted-foreground shrink-0 whitespace-nowrap">
                            {formatRelativeDate(conv.last_message_at)}
                          </span>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </div>
      ) : (
        /* ═══ Conversation view ═══ */
        <>
          <ScrollArea className="flex-1 p-4">
            <div className="mx-auto max-w-3xl space-y-6">
              {messages.map((message) => (
                <div key={message.id} className="group flex gap-4">
                  {/* Avatar */}
                  <div
                    className={cn(
                      "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
                      message.role === "user"
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted"
                    )}
                  >
                    {message.role === "user" ? (
                      <User className="h-4 w-4" />
                    ) : (
                      <Anchor
                        className={cn(
                          "h-4 w-4",
                          message.isStreaming &&
                            (message.content
                              ? "animate-spin-anchor-fast"
                              : "animate-spin-anchor")
                        )}
                      />
                    )}
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0 space-y-2">
                    <div className="prose prose-sm max-w-none break-words dark:prose-invert">
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
                        <p className="whitespace-pre-wrap">{message.content}</p>
                      )}
                    </div>

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
                          className="h-auto p-1 text-xs text-muted-foreground"
                          onClick={() => toggleCitations(message.id)}
                        >
                          {expandedCitations.has(message.id) ? (
                            <ChevronUp className="mr-1 h-3 w-3" />
                          ) : (
                            <ChevronDown className="mr-1 h-3 w-3" />
                          )}
                          {message.citations.length} source{message.citations.length > 1 ? "s" : ""}
                        </Button>
                        {expandedCitations.has(message.id) && (
                          <div className="mt-2 space-y-2">
                            {message.citations.map((citation: Citation, idx: number) => (
                              <div
                                key={idx}
                                className="rounded-md border bg-muted/50 p-3 text-sm"
                              >
                                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                  <FileText className="h-3 w-3" />
                                  {citation.document_filename}
                                  {citation.page_number && (
                                    <span>· Page {citation.page_number}</span>
                                  )}
                                </div>
                                <p className="mt-1 text-xs italic text-foreground/70">
                                  "{citation.excerpt}"
                                </p>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Copy button */}
                  <div className="flex shrink-0 items-start gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                    <button
                      type="button"
                      onClick={() => handleCopy(message.id, message.content)}
                      className="inline-flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
                      title="Copier"
                    >
                      {copiedMessageId === message.id ? (
                        <Check className="h-3.5 w-3.5 text-green-500" />
                      ) : (
                        <Copy className="h-3.5 w-3.5" />
                      )}
                    </button>
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
          </ScrollArea>

          {/* Chat input - bottom bar */}
          <div className="border-t p-4 bg-surface">
            <div className="mx-auto max-w-3xl">
              <div className="relative flex items-end rounded-md border bg-background">
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleSearch();
                    }
                  }}
                  placeholder="Posez une question complémentaire..."
                  className="min-h-[48px] flex-1 border-0 bg-transparent px-3 py-3 pr-24 text-sm focus:outline-none focus:ring-0 text-foreground placeholder:text-muted-foreground"
                  disabled={isSearching}
                  autoFocus
                />
                <div className="absolute bottom-2 right-2 flex items-center gap-1">
                  <button
                    type="button"
                    onClick={toggleRecording}
                    disabled={isSearching}
                    className={cn(
                      "inline-flex h-8 w-8 items-center justify-center rounded-md transition-colors",
                      isRecording
                        ? "bg-destructive text-destructive-foreground animate-pulse"
                        : "text-muted-foreground hover:bg-muted hover:text-foreground"
                    )}
                    title={isRecording ? "Arrêter la dictée" : "Dicter"}
                  >
                    {isRecording ? (
                      <MicOff className="h-3.5 w-3.5" />
                    ) : (
                      <Mic className="h-4 w-4" />
                    )}
                  </button>
                  <Button
                    variant="premium"
                    size="icon"
                    className="h-8 w-8 rounded-full"
                    onClick={handleSearch}
                    disabled={!query.trim() || isSearching || !selectedAssistantId}
                  >
                    {isSearching ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Send className="h-4 w-4" />
                    )}
                  </Button>
                </div>
              </div>
              <p className="mt-2 text-center text-xs text-muted-foreground">
                Entrée pour envoyer
              </p>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
