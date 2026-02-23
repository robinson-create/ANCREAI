import { useNavigate } from "react-router-dom";
import {
  FileText,
  Mail,
  Search,
  Mic,
  MicOff,
  SendHorizontal,
  MessageSquare,
  Clock,
  ArrowRight,
  Send,
  FileEdit,
  ChevronRight,
} from "lucide-react";
import { useState, useEffect, useMemo, useRef, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { workspaceDocumentsApi } from "@/api/workspace-documents";
import { assistantsApi } from "@/api/assistants";
import { chatApi } from "@/api/chat";
import type { Assistant } from "@/types";

const actions = [
  {
    id: "document",
    label: "Rédiger un document",
    description: "Contrat, devis, NDA, compte-rendu, note…",
    icon: FileText,
    path: "/app/documents",
  },
  {
    id: "email",
    label: "Composer un email",
    description: "Avec ton, contexte et sources",
    icon: Mail,
    path: "/app/email",
  },
  {
    id: "search",
    label: "Rechercher une info",
    description: "Interroger vos documents et sources",
    icon: Search,
    path: "/app/search",
  },
];

// Mock emails (same source as email-composer until a real API is available)
const MOCK_EMAILS = [
  { subject: "Relance devis TechCo", to: "j.martin@techco.fr", date: "2026-02-10", status: "Envoyé" },
  { subject: "Proposition commerciale Q1", to: "j.martin@techco.fr", date: "2026-01-28", status: "Envoyé" },
  { subject: "Proposition partenariat Acme", to: "contact@acme.com", date: "2026-02-08", status: "Brouillon" },
  { subject: "Confirmation RDV vendredi", to: "s.dupont@client.fr", date: "2026-02-07", status: "Envoyé" },
  { subject: "Suivi projet phase 2", to: "s.dupont@client.fr", date: "2026-02-01", status: "Envoyé" },
  { subject: "Demande d'informations RGPD", to: "legal@partenaire.fr", date: "2026-02-05", status: "Envoyé" },
  { subject: "Suivi onboarding nouveau client", to: "n.bernard@newco.fr", date: "2026-02-03", status: "Brouillon" },
];

// ── Unified history item ──

interface HistoryItem {
  id: string;
  type: "document" | "email" | "conversation";
  title: string;
  subtitle: string;
  date: string;
  sortDate: number;
  status?: string;
  path: string;
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

const DOC_STATUS_LABELS: Record<string, string> = {
  draft: "Brouillon",
  validated: "Validé",
  sent: "Envoyé",
  archived: "Archivé",
};

// ── Tab filter ──

type HistoryFilter = "all" | "document" | "email" | "conversation";

const FILTER_TABS: { value: HistoryFilter; label: string; icon: typeof FileText }[] = [
  { value: "all", label: "Tout", icon: Clock },
  { value: "document", label: "Documents", icon: FileText },
  { value: "email", label: "Emails", icon: Mail },
  { value: "conversation", label: "Discussions", icon: MessageSquare },
];

// ── Speech Recognition types: see src/speech-recognition.d.ts ──

// Keywords that indicate intent
const EMAIL_KEYWORDS = ["email", "e-mail", "mail", "courriel", "envoyer un mail", "écrire un mail", "rédiger un mail", "composer un mail", "répondre"];
const DOC_KEYWORDS = ["document", "contrat", "devis", "nda", "compte-rendu", "compte rendu", "rapport", "note", "facture", "rédiger un", "rédige un", "écrire un"];

function detectIntent(text: string): "email" | "document" | "search" {
  const lower = text.toLowerCase();
  if (EMAIL_KEYWORDS.some((kw) => lower.includes(kw))) return "email";
  if (DOC_KEYWORDS.some((kw) => lower.includes(kw))) return "document";
  return "search";
}

export function DashboardPage() {
  const navigate = useNavigate();
  const [prompt, setPrompt] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [filter, setFilter] = useState<HistoryFilter>("all");
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);
  const wantsRecordingRef = useRef(false);

  // ── Speech Recognition (définis en premier pour être utilisés dans handleSubmit)
  const startRecording = useCallback(() => {
    const SpeechRecognitionCtor =
      window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognitionCtor) return;

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
        setPrompt((prev) => {
          const separator = prev && !prev.endsWith(" ") ? " " : "";
          return prev + separator + finalTranscript;
        });
      }
    };

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
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

  const handleSubmit = useCallback(() => {
    const text = prompt.trim();
    if (!text) return;
    stopRecording();
    const intent = detectIntent(text);
    switch (intent) {
      case "email":
        navigate("/app/email", { state: { prompt: text, autoGenerate: true } });
        break;
      case "document":
        navigate("/app/documents", { state: { prompt: text } });
        break;
      default:
        navigate(`/app/search?q=${encodeURIComponent(text)}`);
        break;
    }
  }, [prompt, navigate, stopRecording]);

  const toggleRecording = useCallback(() => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  }, [isRecording, startRecording, stopRecording]);

  // Arrêter le micro au démontage (navigation vers une autre page)
  useEffect(() => {
    return () => stopRecording();
  }, [stopRecording]);

  // ── Fetch documents ──
  const { data: documents = [] } = useQuery({
    queryKey: ["workspace-documents"],
    queryFn: () => workspaceDocumentsApi.list(),
    staleTime: 30_000,
  });

  // ── Fetch assistants ──
  const { data: assistants = [] } = useQuery({
    queryKey: ["assistants"],
    queryFn: () => assistantsApi.list(),
    staleTime: 30_000,
  });

  // ── Fetch conversations for each assistant ──
  const [conversations, setConversations] = useState<
    Array<{
      id: string;
      title: string;
      last_message_at: string;
      message_count: number;
      assistant: Assistant;
    }>
  >([]);

  useEffect(() => {
    if (assistants.length === 0) return;

    const fetchAll = async () => {
      const results = await Promise.allSettled(
        assistants.map(async (a) => {
          const convos = await chatApi.listConversations(a.id);
          return convos.map((c) => ({ ...c, assistant: a }));
        })
      );

      const allConvos = results
        .filter((r) => r.status === "fulfilled")
        .flatMap((r) => (r as PromiseFulfilledResult<Array<{ id: string; title: string; started_at: string; last_message_at: string; message_count: number; assistant: Assistant }>>).value);

      setConversations(allConvos);
    };

    fetchAll();
  }, [assistants]);

  // ── Build unified history ──
  const historyItems = useMemo<HistoryItem[]>(() => {
    const items: HistoryItem[] = [];

    // Documents
    for (const doc of documents) {
      items.push({
        id: `doc-${doc.id}`,
        type: "document",
        title: doc.title || "Sans titre",
        subtitle: DOC_TYPE_LABELS[doc.doc_type] || doc.doc_type,
        date: formatRelativeDate(doc.updated_at),
        sortDate: new Date(doc.updated_at).getTime(),
        status: DOC_STATUS_LABELS[doc.status] || doc.status,
        path: `/app/documents/${doc.id}`,
      });
    }

    // Emails (mock)
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
      });
    }

    // Conversations
    for (const convo of conversations) {
      items.push({
        id: `convo-${convo.id}`,
        type: "conversation",
        title: convo.title || "Nouvelle discussion",
        subtitle: convo.assistant.name,
        date: formatRelativeDate(convo.last_message_at),
        sortDate: new Date(convo.last_message_at).getTime(),
        status: `${convo.message_count} msg`,
        path: `/app/search?assistant=${convo.assistant.id}&conversation=${convo.id}`,
      });
    }

    // Sort by most recent
    items.sort((a, b) => b.sortDate - a.sortDate);
    return items;
  }, [documents, conversations]);

  const filteredItems = filter === "all"
    ? historyItems
    : historyItems.filter((i) => i.type === filter);

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

  return (
    <div className="flex flex-col min-h-full animate-fade-in overflow-auto">
      {/* Top section - prompt first (primary), generous spacing like Lovable */}
      <div className="flex-1 flex items-center justify-center px-6 py-16 md:py-24">
        <div className="max-w-2xl w-full space-y-10 text-center">
          <div className="space-y-3">
            <h1 className="font-heading text-3xl md:text-4xl font-bold text-white tracking-tight">
              Que souhaitez-vous faire ?
            </h1>
            <p className="text-sm text-white/90 md:text-base font-body">
              Décrivez votre besoin ci-dessous ou choisissez une action rapide.
            </p>
          </div>

          {/* Prompt bar — primary, encourage writing */}
          <div className="space-y-2">
            <p className="text-xs text-white/80 font-medium uppercase tracking-wider font-body">Décrivez votre besoin</p>
            <div className="relative">
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey && prompt.trim()) {
                    e.preventDefault();
                    handleSubmit();
                  }
                }}
                rows={3}
                placeholder="Ex : Rédige un email de relance pour le client TechCo concernant le devis en attente…"
                className="w-full text-sm font-body bg-card/95 backdrop-blur-sm border border-border rounded-2xl px-5 py-4 pr-28 outline-none focus:ring-4 focus:ring-primary/20 focus:border-primary/40 text-foreground placeholder:text-muted-foreground/60 shadow-xl resize-none leading-relaxed transition-all"
              />
              <div className="absolute right-3 bottom-3 flex items-center gap-1.5">
                <button
                  onClick={toggleRecording}
                  className={`w-10 h-10 rounded-full flex items-center justify-center transition-all ${
                    isRecording
                      ? "bg-destructive text-destructive-foreground animate-pulse"
                      : "bg-muted hover:bg-accent/20 text-muted-foreground hover:text-foreground"
                  }`}
                  title={isRecording ? "Arrêter la dictée" : "Dicter"}
                >
                  {isRecording ? (
                    <MicOff className="h-4 w-4" />
                  ) : (
                    <Mic className="h-4 w-4" />
                  )}
                </button>
                <Button variant="premium" size="icon" className="h-10 w-10 rounded-full" disabled={!prompt.trim()} onClick={handleSubmit}>
                  <SendHorizontal className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </div>

          {/* Smaller CTAs — below prompt to encourage chat-first usage */}
          <div className="flex flex-wrap items-center justify-center gap-2 pt-2">
            {actions.map((a) => (
              <button
                key={a.id}
                onClick={() => navigate(a.path)}
                className="group inline-flex items-center gap-2 px-4 py-2.5 rounded-lg text-xs font-medium font-body bg-card/80 backdrop-blur-sm hover:bg-accent/20 border border-border/50 hover:border-primary/30 text-muted-foreground hover:text-foreground transition-all shadow-sm hover:shadow-md"
              >
                <a.icon className="h-3.5 w-3.5 group-hover:text-primary transition-colors" />
                <span>{a.label}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Activity history section - fond blanc opaque 100 % */}
      {historyItems.length > 0 && (
        <div className="flex-shrink-0 mt-auto px-6 py-6 md:py-8 border-t border-border bg-background">
          <div className="max-w-3xl mx-auto">
            {/* Section header */}
            <div className="flex items-center gap-3 mb-4">
              <div className="h-px flex-1 bg-border" />
              <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider font-body">
                <Clock className="h-3.5 w-3.5" />
                Activité récente
              </div>
              <div className="h-px flex-1 bg-border" />
            </div>

            {/* Filter tabs */}
            <div className="flex items-center gap-1 mb-4 bg-muted backdrop-blur-sm rounded-lg p-1 w-fit mx-auto">
              {FILTER_TABS.map((tab) => (
                <button
                  key={tab.value}
                  onClick={() => setFilter(tab.value)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium font-body transition-all ${
                    filter === tab.value
                      ? "bg-primary text-primary-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  <tab.icon className="h-3 w-3" />
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Items list */}
            <div className="space-y-1.5">
              {filteredItems.slice(0, 15).map((item) => (
                <button
                  key={item.id}
                  onClick={() => navigate(item.path)}
                  className="group flex items-center gap-3 w-full px-4 py-3 rounded-lg bg-card border border-border hover:shadow-lg hover:border-primary/20 transition-all text-left"
                >
                  <div className={`w-8 h-8 rounded-lg ${typeBg(item.type)} flex items-center justify-center shrink-0`}>
                    {typeIcon(item.type)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-foreground truncate font-body">
                      {item.title}
                    </div>
                    <div className="text-xs text-muted-foreground truncate font-body">
                      {item.subtitle}
                    </div>
                  </div>
                  {item.status && (
                    <Badge variant="outline" className="shrink-0 text-[10px] font-medium hidden sm:inline-flex">
                      {item.status}
                    </Badge>
                  )}
                  <span className="text-[11px] text-muted-foreground shrink-0 hidden sm:block font-body">
                    {item.date}
                  </span>
                  <ChevronRight className="h-3.5 w-3.5 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity shrink-0" />
                </button>
              ))}
            </div>

            {/* Show more hint */}
            {filteredItems.length > 15 && (
              <div className="text-center mt-3">
                <button
                  onClick={() => {
                    if (filter === "document") navigate("/app/documents");
                    else if (filter === "email") navigate("/app/email");
                    else navigate("/app/documents");
                  }}
                  className="text-xs text-primary hover:underline inline-flex items-center gap-1"
                >
                  Voir tout
                  <ArrowRight className="h-3 w-3" />
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
