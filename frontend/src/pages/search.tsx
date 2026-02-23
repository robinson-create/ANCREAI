import { useState, useRef, useEffect, useCallback, useMemo } from "react";
import { useNavigate, useSearchParams, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Search,
  User,
  FileText,
  ChevronDown,
  ChevronUp,
  ChevronRight,
  Loader2,
  Send,
  SendHorizontal,
  Anchor,
  MessageSquare,
  Clock,
  Mic,
  MicOff,
  Copy,
  Check,
  FolderPlus,
  FileEdit,
  Mail,
  Folder,
  Plus,
  MoreVertical,
  Square,
  AlertCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import { assistantsApi } from "@/api/assistants";
import { chatApi } from "@/api/chat";
import { workspaceDocumentsApi } from "@/api/workspace-documents";
import type { Assistant, Citation } from "@/types";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useCopilotReadable } from "@copilotkit/react-core";
import { BlockRenderer } from "@/components/blocks/BlockRenderer";
import { useSearchStream } from "@/contexts/search-stream";
import { useSearchView } from "@/contexts/search-view-context";
import { AddToFolderDialog } from "@/components/folders/AddToFolderDialog";
import { FolderCreateDialog } from "@/components/folders/FolderCreateDialog";
import { FolderDetailPanel } from "@/components/folders/FolderDetailPanel";
import { foldersApi } from "@/api/folders";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useToast } from "@/hooks/use-toast";

// Même structure que le dashboard pour l'activité
const MOCK_EMAILS = [
  { subject: "Relance devis TechCo", to: "j.martin@techco.fr", date: "2026-02-10", status: "Envoyé" },
  { subject: "Proposition commerciale Q1", to: "j.martin@techco.fr", date: "2026-01-28", status: "Envoyé" },
  { subject: "Proposition partenariat Acme", to: "contact@acme.com", date: "2026-02-08", status: "Brouillon" },
  { subject: "Confirmation RDV vendredi", to: "s.dupont@client.fr", date: "2026-02-07", status: "Envoyé" },
  { subject: "Suivi projet phase 2", to: "s.dupont@client.fr", date: "2026-02-01", status: "Envoyé" },
];

const DOC_TYPE_LABELS: Record<string, string> = {
  contract: "Contrat",
  quote: "Devis",
  invoice: "Facture",
  nda: "NDA",
  report: "Rapport",
  note: "Note",
  email: "Email",
  other: "Document",
};

interface HistoryItem {
  id: string;
  type: "document" | "email" | "conversation";
  title: string;
  subtitle: string;
  date: string;
  sortDate: number;
  status?: string;
  path: string;
  /** Pour "Ajouter à un dossier" : type API folder */
  folderItemType?: "document" | "email_thread" | "conversation";
  folderItemId?: string;
}

const actions = [
  { id: "document", label: "Rédiger un document", icon: FileText, path: "/app/documents" },
  { id: "email", label: "Composer un email", icon: Mail, path: "/app/email" },
  { id: "search", label: "Rechercher une info", icon: Search, path: "/app/search" },
];

// ── Speech Recognition: see src/speech-recognition.d.ts ──

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
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { toast } = useToast();
  const queryClient = useQueryClient();

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
    conversationId,
    abortStream,
  } = useSearchStream();
  const searchViewCtx = useSearchView();
  const setSearchHome = searchViewCtx?.setSearchHome;

  // ── Local UI state (resets on unmount — that's fine) ──
  const [query, setQuery] = useState("");
  const [expandedCitations, setExpandedCitations] = useState<Set<string>>(new Set());
  const [isRecording, setIsRecording] = useState(false);
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null);
  const [forceListView, setForceListView] = useState(false);
  const [addToFolderTarget, setAddToFolderTarget] = useState<{
    itemType: "document" | "email_thread" | "conversation";
    itemId: string;
    itemTitle?: string;
  } | null>(null);
  const [folderCreateOpen, setFolderCreateOpen] = useState(false);

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
        if (result?.isFinal && result[0]) {
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

  // Fetch documents for activity list
  const { data: documents = [] } = useQuery({
    queryKey: ["workspace-documents"],
    queryFn: () => workspaceDocumentsApi.list(),
    staleTime: 30_000,
  });

  // Fetch folders for Dossiers section
  const { data: folders = [] } = useQuery({
    queryKey: ["folders"],
    queryFn: () => foldersApi.list(),
  });

  const folderCreateMutation = useMutation({
    mutationFn: (name: string) => foldersApi.create({ name }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["folders"] });
      toast({ title: "Dossier créé" });
      setFolderCreateOpen(false);
    },
    onError: () => {
      toast({ variant: "destructive", title: "Erreur", description: "Impossible de créer le dossier." });
    },
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
      .filter((r) => r.status === "fulfilled")
      .flatMap((r) => (r as PromiseFulfilledResult<Array<{ id: string; title: string; started_at: string; last_message_at: string; message_count: number; assistant: Assistant }>>).value)
      .sort((a, b) => new Date(b.last_message_at).getTime() - new Date(a.last_message_at).getTime());
    setAllConversations(all);
  }, [assistants]);

  useEffect(() => {
    fetchAllConversations();
  }, [fetchAllConversations]);

  // Build unified history (documents + emails + conversations) for "Documents récents"
  const historyItems = useMemo<HistoryItem[]>(() => {
    const items: HistoryItem[] = [];
    for (const doc of documents) {
      items.push({
        id: `doc-${doc.id}`,
        type: "document",
        title: doc.title || "Sans titre",
        subtitle: DOC_TYPE_LABELS[doc.doc_type] || doc.doc_type,
        date: formatRelativeDate(doc.updated_at),
        sortDate: new Date(doc.updated_at).getTime(),
        status: doc.status,
        path: `/app/documents/${doc.id}`,
        folderItemType: "document",
        folderItemId: doc.id,
      });
    }
    for (const email of MOCK_EMAILS) {
      items.push({
        id: `email-${email.subject}`,
        type: "email",
        title: email.subject,
        subtitle: `À : ${email.to}`,
        date: formatRelativeDate(email.date),
        sortDate: new Date(email.date).getTime(),
        status: email.status,
        path: "/app/email",
        // Pas de folderItemId : emails mock sans thread_key réel
      });
    }
    for (const convo of allConversations) {
      items.push({
        id: `convo-${convo.id}`,
        type: "conversation",
        title: convo.title || "Nouvelle discussion",
        subtitle: convo.assistant.name,
        date: formatRelativeDate(convo.last_message_at),
        sortDate: new Date(convo.last_message_at).getTime(),
        status: `${convo.message_count} msg`,
        path: `/app/search?assistant=${convo.assistant.id}&conversation=${convo.id}`,
        folderItemType: "conversation",
        folderItemId: convo.id,
      });
    }
    items.sort((a, b) => b.sortDate - a.sortDate);
    return items;
  }, [documents, allConversations]);

  const typeIcon = (type: HistoryItem["type"]) => {
    switch (type) {
      case "document":
        return <FileEdit className="h-4 w-4 text-blue-500" />;
      case "email":
        return <Send className="h-4 w-4 text-emerald-500" />;
      case "conversation":
        return <MessageSquare className="h-4 w-4 text-violet-500" />;
    }
  };

  const typeBg = (type: HistoryItem["type"]) => {
    switch (type) {
      case "document":
        return "bg-blue-500/10";
      case "email":
        return "bg-emerald-500/10";
      case "conversation":
        return "bg-violet-500/10";
    }
  };

  // Auto-select first assistant (only if context doesn't already have one)
  useEffect(() => {
    if (assistants.length === 0) return;
    const paramAssistant = searchParams.get("assistant");
    if (paramAssistant && assistants.some((a: Assistant) => a.id === paramAssistant)) {
      setSelectedAssistantId(paramAssistant);
    } else if (!selectedAssistantId && assistants[0]) {
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

  // Sync search home state for wallpaper in AppLayout
  useEffect(() => {
    setSearchHome?.(!hasConversation);
    return () => setSearchHome?.(true);
  }, [hasConversation, setSearchHome]);

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
      {/* ── Content ── */}
      {!hasConversation ? (
        /* ═══ Vue accueil : design identique au dashboard ═══ */
        <div className="flex flex-col min-h-full animate-fade-in overflow-auto">
          {/* Hero — fond mer, prompt centré (identique dashboard) */}
          <div className="flex-1 flex items-center justify-center px-6 py-16 md:py-24">
            <div className="max-w-2xl w-full space-y-10 text-center">
              <div className="space-y-3">
                <h1 className="font-display text-3xl md:text-4xl font-bold text-white tracking-tight">
                  Que souhaitez-vous faire ?
                </h1>
                <p className="text-sm text-white/90 md:text-base">
                  Décrivez votre besoin ci-dessous ou choisissez une action rapide.
                </p>
              </div>

              {/* Prompt bar — style dashboard */}
              <div className="space-y-2">
                <p className="text-xs text-white/80 font-medium uppercase tracking-wider">
                  Décrivez votre besoin
                </p>
                <div className="relative">
                  <textarea
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey && query.trim()) {
                        e.preventDefault();
                        handleSearch();
                      }
                    }}
                    rows={3}
                    placeholder="Ex : Rédige un email de relance pour le client TechCo concernant le devis en attente…"
                    className="w-full text-sm bg-card/95 backdrop-blur-sm border border-border rounded-[var(--radius)] px-5 py-4 pr-28 outline-none focus:ring-4 focus:ring-ring/15 focus:border-ring/35 text-foreground placeholder:text-muted-foreground shadow-soft resize-none leading-relaxed transition-colors"
                    disabled={isSearching}
                  />
                  <div className="absolute right-3 bottom-3 flex items-center gap-1.5">
                    <button
                      onClick={toggleRecording}
                      className={cn(
                        "w-10 h-10 rounded-full flex items-center justify-center transition-all",
                        isRecording
                          ? "bg-destructive text-destructive-foreground animate-pulse"
                          : "bg-muted hover:bg-accent/20 text-muted-foreground hover:text-foreground"
                      )}
                      title={isRecording ? "Arrêter la dictée" : "Dicter"}
                    >
                      {isRecording ? (
                        <MicOff className="h-4 w-4" />
                      ) : (
                        <Mic className="h-4 w-4" />
                      )}
                    </button>
                    {isSearching ? (
                      <Button
                        variant="premium"
                        size="icon"
                        className="h-10 w-10 rounded-full"
                        onClick={abortStream}
                        title="Arrêter la génération"
                      >
                        <Square className="h-4 w-4" />
                      </Button>
                    ) : (
                      <Button
                        variant="premium"
                        size="icon"
                        className="h-10 w-10 rounded-full"
                        disabled={!query.trim() || !selectedAssistantId}
                        onClick={handleSearch}
                      >
                        <SendHorizontal className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                </div>
              </div>

              {/* Quick actions — style dashboard */}
              <div className="flex flex-wrap items-center justify-center gap-2 pt-2">
                {actions.map((a) => (
                  <button
                    key={a.id}
                    onClick={() => navigate(a.path)}
                    className="group inline-flex items-center gap-2 px-3 py-2 rounded-lg text-xs bg-muted/50 hover:bg-accent/30 border border-transparent hover:border-primary/20 transition-all"
                  >
                    <a.icon className="h-3.5 w-3.5 text-muted-foreground group-hover:text-primary" />
                    <span className="text-muted-foreground group-hover:text-foreground">
                      {a.label}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Partie blanche : Dossiers + Documents récents */}
          <div className="flex-shrink-0 mt-auto px-6 py-6 md:py-8 border-t border-border bg-white">
            <div className="max-w-3xl mx-auto space-y-8">
              {/* Section Dossiers */}
              <div>
                <div className="flex items-center gap-3 mb-4">
                  <div className="h-px flex-1 bg-border" />
                  <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    <Folder className="h-3.5 w-3.5" />
                    Dossiers
                  </div>
                  <div className="h-px flex-1 bg-border" />
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  {folders.map((f) => (
                    <button
                      key={f.id}
                      onClick={() => setSearchParams((p) => {
                        const n = new URLSearchParams(p);
                        n.set("folder", f.id);
                        return n;
                      })}
                      className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-card border border-border hover:shadow-soft hover:border-primary/20 transition-all text-sm font-medium text-foreground"
                    >
                      <span
                        className="h-2 w-2 rounded-full shrink-0"
                        style={{ backgroundColor: f.color || "var(--muted)" }}
                      />
                      {f.name}
                    </button>
                  ))}
                  <button
                    onClick={() => setFolderCreateOpen(true)}
                    className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-dashed border-border hover:border-primary/30 hover:bg-accent/20 transition-all text-sm text-muted-foreground hover:text-foreground"
                  >
                    <Plus className="h-3.5 w-3.5" />
                    Nouveau dossier
                  </button>
                </div>
              </div>

              {/* Section Documents récents / Activité récente */}
              {historyItems.length > 0 && (
                <div>
                  <div className="flex items-center gap-3 mb-4">
                    <div className="h-px flex-1 bg-border" />
                    <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      <Clock className="h-3.5 w-3.5" />
                      Documents récents
                    </div>
                    <div className="h-px flex-1 bg-border" />
                  </div>
                  <div className="space-y-1.5">
                    {historyItems.slice(0, 15).map((item) => (
                      <div
                        key={item.id}
                        className="group flex items-center gap-3 w-full px-4 py-3 rounded-lg bg-card/95 backdrop-blur-sm border border-border hover:shadow-soft hover:border-primary/20 transition-all"
                      >
                        <button
                          onClick={() => {
                            if (item.type === "conversation") {
                              const convId = item.id.replace("convo-", "");
                              const match = item.path.match(/assistant=([^&]+)/);
                              const assistantId = match?.[1];
                              const assistant = assistants.find((a: Assistant) => a.id === assistantId);
                              if (assistant) {
                                handleLoadConversation(convId, assistant.id, item.title);
                              }
                            } else {
                              navigate(item.path);
                            }
                          }}
                          className="flex items-center gap-3 flex-1 min-w-0 text-left"
                        >
                          <div
                            className={`w-8 h-8 rounded-lg ${typeBg(item.type)} flex items-center justify-center shrink-0`}
                          >
                            {typeIcon(item.type)}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="text-sm font-medium text-foreground truncate">
                              {item.title}
                            </div>
                            <div className="text-xs text-muted-foreground truncate">
                              {item.subtitle}
                            </div>
                          </div>
                          {item.status && (
                            <Badge variant="outline" className="shrink-0 text-[10px] hidden sm:inline-flex">
                              {item.status}
                            </Badge>
                          )}
                          <span className="text-[11px] text-muted-foreground shrink-0 hidden sm:block">
                            {item.date}
                          </span>
                          <ChevronRight className="h-3.5 w-3.5 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity shrink-0" />
                        </button>
                        {item.folderItemId && item.folderItemType && (
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-7 w-7 p-0 opacity-0 group-hover:opacity-100 transition-opacity shrink-0"
                                onClick={(e) => e.stopPropagation()}
                              >
                                <MoreVertical className="h-4 w-4" />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end" onClick={(e) => e.stopPropagation()}>
                              <DropdownMenuItem
                                onClick={() =>
                                  setAddToFolderTarget({
                                    itemType: item.folderItemType!,
                                    itemId: item.folderItemId!,
                                    itemTitle: item.title,
                                  })
                                }
                              >
                                <FolderPlus className="h-4 w-4 mr-2" />
                                Ajouter à un dossier
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          <FolderCreateDialog
            open={folderCreateOpen}
            onOpenChange={setFolderCreateOpen}
            onSubmit={(name) => folderCreateMutation.mutateAsync(name).then(() => undefined)}
            mode="create"
          />

          {searchParams.get("folder") && (
            <FolderDetailPanel
              folderId={searchParams.get("folder")!}
              onClose={() => setSearchParams((p) => {
                const n = new URLSearchParams(p);
                n.delete("folder");
                return n;
              })}
            />
          )}
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

                    {/* Interrupted indicator */}
                    {message.wasInterrupted && (
                      <div className="flex items-center gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
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
                  {isSearching ? (
                    <Button
                      variant="premium"
                      size="icon"
                      className="h-8 w-8 rounded-full"
                      onClick={abortStream}
                      title="Arrêter la génération"
                    >
                      <Square className="h-4 w-4" />
                    </Button>
                  ) : (
                    <Button
                      variant="premium"
                      size="icon"
                      className="h-8 w-8 rounded-full"
                      onClick={handleSearch}
                      disabled={!query.trim() || !selectedAssistantId}
                    >
                      <Send className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              </div>
              <p className="mt-2 text-center text-xs text-muted-foreground">
                Entrée pour envoyer
              </p>
            </div>
          </div>
        </>
      )}

      <AddToFolderDialog
        open={!!addToFolderTarget}
        onOpenChange={(open) => !open && setAddToFolderTarget(null)}
        itemType={addToFolderTarget?.itemType ?? "conversation"}
        itemId={addToFolderTarget?.itemId ?? ""}
        itemTitle={addToFolderTarget?.itemTitle}
        onSuccess={() => queryClient.invalidateQueries({ queryKey: ["folders"] })}
      />
    </div>
  );
}
