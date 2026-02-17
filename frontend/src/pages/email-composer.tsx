import { Mail, Search, Send, ChevronRight, Reply, Forward, Mic, Plus, Sparkles, Bot, Loader2, Square, Paperclip, X, FileText, RefreshCw, AlertCircle, Check } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useState, useRef, useCallback, useEffect } from "react";
import { useLocation } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { assistantsApi } from "@/api/assistants";
import { chatApi } from "@/api/chat";
import { workspaceDocumentsApi } from "@/api/workspace-documents";
import { mailApi } from "@/api/mail";
import type { MailThreadSummary, MailMessage } from "@/api/mail";
import type { Assistant } from "@/types";

interface EmailAttachment {
  id: string;
  name: string;
  url: string;
  type: "pdf" | "file";
  sourceDocId?: string;
}

// ── Speech Recognition: see src/speech-recognition.d.ts ──

export const EmailComposer = () => {
  const location = useLocation();
  const queryClient = useQueryClient();

  // ── Mail account state ──
  const [selectedAccountId, setSelectedAccountId] = useState<string | null>(null);

  // ── Navigation state ──
  const [selectedThread, setSelectedThread] = useState<MailThreadSummary | null>(null);
  const [selectedMessage, setSelectedMessage] = useState<MailMessage | null>(null);
  const [search, setSearch] = useState("");
  const [replying, setReplying] = useState(false);
  const [replyBody, setReplyBody] = useState("");
  const [replyInstruction, setReplyInstruction] = useState("");

  // ── Compose new email state ──
  const [composing, setComposing] = useState(false);
  const [composeTo, setComposeTo] = useState("");
  const [composeSubject, setComposeSubject] = useState("");
  const [composeBody, setComposeBody] = useState("");
  const [composeInstruction, setComposeInstruction] = useState("");
  const [composeAttachments, setComposeAttachments] = useState<EmailAttachment[]>([]);
  const [showDocPicker, setShowDocPicker] = useState(false);
  const [docPickerTarget, setDocPickerTarget] = useState<"compose" | "reply">("compose");

  // ── Reply attachments ──
  const [replyAttachments, setReplyAttachments] = useState<EmailAttachment[]>([]);

  // ── Send state ──
  const [, setSendingClientId] = useState<string | null>(null);
  const [sendStatus, setSendStatus] = useState<"idle" | "sending" | "sent" | "failed">("idle");
  const [sendError, setSendError] = useState<string | null>(null);

  // ── Shared state ──
  const [isRecording, setIsRecording] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [selectedAssistantId, setSelectedAssistantId] = useState<string | null>(null);

  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);
  const wantsRecordingRef = useRef(false);
  const abortGenerationRef = useRef<(() => void) | null>(null);
  const dictationTargetRef = useRef<React.Dispatch<React.SetStateAction<string>>>(setComposeBody);
  const sendPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const finalizePollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Queries ──

  const { data: accounts = [] } = useQuery({
    queryKey: ["mail-accounts"],
    queryFn: mailApi.listAccounts,
    staleTime: 30_000,
  });

  // Auto-select first connected account
  useEffect(() => {
    if (!selectedAccountId && accounts.length > 0) {
      const connected = accounts.find((a) => a.status === "connected");
      if (connected) setSelectedAccountId(connected.id);
    }
  }, [accounts, selectedAccountId]);

  const { data: threads = [], isLoading: threadsLoading } = useQuery({
    queryKey: ["mail-threads", selectedAccountId],
    queryFn: () => mailApi.listThreads(selectedAccountId!, { limit: 50 }),
    enabled: !!selectedAccountId,
    staleTime: 15_000,
  });

  const { data: threadDetail } = useQuery({
    queryKey: ["mail-thread-detail", selectedAccountId, selectedThread?.thread_key],
    queryFn: () => mailApi.getThread(selectedThread!.thread_key, selectedAccountId!),
    enabled: !!selectedAccountId && !!selectedThread,
    staleTime: 10_000,
  });

  const { data: assistants = [] } = useQuery({
    queryKey: ["assistants"],
    queryFn: assistantsApi.list,
    staleTime: 30_000,
  });

  // Auto-select first assistant
  useEffect(() => {
    const first = assistants[0];
    if (first && !selectedAssistantId) {
      setSelectedAssistantId(first.id);
    }
  }, [assistants, selectedAssistantId]);

  // Auto-open compose with prompt from dashboard or document
  useEffect(() => {
    const state = location.state as {
      prompt?: string;
      fromDocument?: { id: string; title: string; pdfUrl: string };
    } | null;
    if (state?.fromDocument) {
      const doc = state.fromDocument;
      setComposing(true);
      setComposeSubject(doc.title);
      setComposeAttachments([
        {
          id: crypto.randomUUID(),
          name: `${doc.title}.pdf`,
          url: doc.pdfUrl,
          type: "pdf",
          sourceDocId: doc.id,
        },
      ]);
      setComposeInstruction(
        `Rédige un email d'accompagnement pour le document "${doc.title}" en pièce jointe. Sois bref et professionnel.`
      );
      window.history.replaceState({}, "");
    } else if (state?.prompt) {
      setComposing(true);
      setComposeInstruction(state.prompt);
      window.history.replaceState({}, "");
    }
  }, [location.state]);

  // ── Polling cleanup on unmount ──
  useEffect(() => {
    return () => {
      if (sendPollRef.current) clearInterval(sendPollRef.current);
      if (finalizePollRef.current) clearInterval(finalizePollRef.current);
    };
  }, []);

  // ── Filtered threads ──
  const filteredThreads = search
    ? threads.filter(
        (t) =>
          (t.subject || "").toLowerCase().includes(search.toLowerCase()) ||
          t.participants.some(
            (p) =>
              p.name?.toLowerCase().includes(search.toLowerCase()) ||
              p.email?.toLowerCase().includes(search.toLowerCase())
          )
      )
    : threads;

  const fileInputRef = useRef<HTMLInputElement>(null);
  const replyFileInputRef = useRef<HTMLInputElement>(null);

  // Fetch validated documents for attachment picker
  const { data: validatedDocs } = useQuery({
    queryKey: ["workspace-documents", "validated"],
    queryFn: () => workspaceDocumentsApi.list("validated"),
    enabled: showDocPicker,
  });

  const openCompose = () => {
    setComposing(true);
    setComposeTo("");
    setComposeSubject("");
    setComposeBody("");
    setComposeInstruction("");
    setComposeAttachments([]);
    setShowDocPicker(false);
    setSelectedThread(null);
    setSelectedMessage(null);
    setReplying(false);
    setReplyBody("");
    setReplyInstruction("");
    setSearch("");
    setSendStatus("idle");
    setSendError(null);
  };

  const handleAddLocalFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const url = URL.createObjectURL(file);
    setComposeAttachments((prev) => [
      ...prev,
      { id: crypto.randomUUID(), name: file.name, url, type: "file" },
    ]);
    e.target.value = "";
  };

  const handlePickDocument = async (docId: string, title: string) => {
    try {
      const { url } = await workspaceDocumentsApi.exportPdf(docId);
      setComposeAttachments((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          name: `${title}.pdf`,
          url,
          type: "pdf",
          sourceDocId: docId,
        },
      ]);
      setShowDocPicker(false);
    } catch {
      // silently fail
    }
  };

  const handleRemoveAttachment = (id: string) => {
    setComposeAttachments((prev) => prev.filter((a) => a.id !== id));
  };

  const handleAddReplyFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const url = URL.createObjectURL(file);
    setReplyAttachments((prev) => [
      ...prev,
      { id: crypto.randomUUID(), name: file.name, url, type: "file" },
    ]);
    e.target.value = "";
  };

  const handlePickDocumentForReply = async (docId: string, title: string) => {
    try {
      const { url } = await workspaceDocumentsApi.exportPdf(docId);
      setReplyAttachments((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          name: `${title}.pdf`,
          url,
          type: "pdf",
          sourceDocId: docId,
        },
      ]);
      setShowDocPicker(false);
    } catch {
      // silently fail
    }
  };

  const handleRemoveReplyAttachment = (id: string) => {
    setReplyAttachments((prev) => prev.filter((a) => a.id !== id));
  };

  // ── Send email ──

  const pollSendStatus = useCallback((clientSendId: string) => {
    if (sendPollRef.current) clearInterval(sendPollRef.current);
    sendPollRef.current = setInterval(async () => {
      try {
        const status = await mailApi.sendStatus(clientSendId);
        if (status.status === "sent") {
          setSendStatus("sent");
          setSendingClientId(null);
          if (sendPollRef.current) clearInterval(sendPollRef.current);
          // Refresh threads
          queryClient.invalidateQueries({ queryKey: ["mail-threads"] });
          queryClient.invalidateQueries({ queryKey: ["mail-thread-detail"] });
        } else if (status.status === "failed") {
          setSendStatus("failed");
          setSendError(status.error_message || "Erreur inconnue");
          setSendingClientId(null);
          if (sendPollRef.current) clearInterval(sendPollRef.current);
        }
      } catch {
        // Keep polling
      }
    }, 2000);
  }, [queryClient]);

  const handleSendCompose = useCallback(async () => {
    if (!selectedAccountId || !composeTo.trim() || !composeBody.trim()) return;
    const clientSendId = crypto.randomUUID();
    setSendStatus("sending");
    setSendError(null);
    setSendingClientId(clientSendId);

    try {
      await mailApi.send({
        client_send_id: clientSendId,
        mail_account_id: selectedAccountId,
        mode: "new",
        to_recipients: [{ name: "", email: composeTo.trim() }],
        subject: composeSubject,
        body_text: composeBody,
        body_html: null,
      });
      pollSendStatus(clientSendId);
    } catch (e: any) {
      setSendStatus("failed");
      setSendError(e?.message || "Erreur d'envoi");
      setSendingClientId(null);
    }
  }, [selectedAccountId, composeTo, composeSubject, composeBody, pollSendStatus]);

  const handleSendReply = useCallback(async () => {
    if (!selectedAccountId || !replyBody.trim() || !selectedMessage) return;
    const clientSendId = crypto.randomUUID();
    setSendStatus("sending");
    setSendError(null);
    setSendingClientId(clientSendId);

    try {
      await mailApi.send({
        client_send_id: clientSendId,
        mail_account_id: selectedAccountId,
        mode: "reply",
        to_recipients: [selectedMessage.sender],
        subject: `Re: ${selectedMessage.subject || ""}`,
        body_text: replyBody,
        body_html: null,
        in_reply_to_message_id: selectedMessage.id,
        provider_thread_id: selectedMessage.provider_thread_id || undefined,
      });
      pollSendStatus(clientSendId);
    } catch (e: any) {
      setSendStatus("failed");
      setSendError(e?.message || "Erreur d'envoi");
      setSendingClientId(null);
    }
  }, [selectedAccountId, replyBody, selectedMessage, pollSendStatus]);

  const handleRetrySend = useCallback(() => {
    setSendStatus("idle");
    setSendError(null);
    setSendingClientId(null);
  }, []);

  // ── Speech Recognition (context-aware target) ──

  const startRecording = useCallback((targetSetter: React.Dispatch<React.SetStateAction<string>>) => {
    const SpeechRecognitionCtor =
      window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognitionCtor) return;

    if (recognitionRef.current) {
      wantsRecordingRef.current = false;
      recognitionRef.current.stop();
      recognitionRef.current = null;
    }

    dictationTargetRef.current = targetSetter;
    wantsRecordingRef.current = true;
    const recognition = new SpeechRecognitionCtor();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "fr-FR";

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let finalTranscript = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        if (result?.isFinal) {
          finalTranscript += result[0]?.transcript ?? "";
        }
      }
      if (finalTranscript) {
        dictationTargetRef.current((prev) => {
          const separator = prev && !prev.endsWith(" ") && !prev.endsWith("\n") ? " " : "";
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

  const toggleRecordingFor = useCallback((targetSetter: React.Dispatch<React.SetStateAction<string>>) => {
    if (isRecording) stopRecording();
    else startRecording(targetSetter);
  }, [isRecording, startRecording, stopRecording]);

  // ── AI Generation (streaming) ──

  const generateWithAI = useCallback((
    prompt: string,
    targetSetter: React.Dispatch<React.SetStateAction<string>>,
  ) => {
    if (!selectedAssistantId) return;

    if (abortGenerationRef.current) {
      abortGenerationRef.current();
      abortGenerationRef.current = null;
    }

    setIsGenerating(true);
    targetSetter("");

    const abort = chatApi.stream(
      selectedAssistantId,
      { message: prompt },
      (token) => {
        targetSetter((prev) => prev + token);
      },
      () => {
        setIsGenerating(false);
        abortGenerationRef.current = null;
      },
      (error) => {
        console.error("AI generation error:", error);
        setIsGenerating(false);
        abortGenerationRef.current = null;
      },
    );

    abortGenerationRef.current = abort;
  }, [selectedAssistantId]);

  const stopGeneration = useCallback(() => {
    if (abortGenerationRef.current) {
      abortGenerationRef.current();
      abortGenerationRef.current = null;
    }
    setIsGenerating(false);
  }, []);

  const generateReply = useCallback(() => {
    if (!selectedMessage) return;
    if (!replyInstruction.trim()) return;
    const senderName = selectedMessage.sender?.name || selectedMessage.sender?.email || "";
    const prompt = `Tu es un assistant de rédaction d'emails professionnels. Rédige une réponse à l'email suivant.

Email original de ${senderName} :
Objet : ${selectedMessage.subject || "(sans objet)"}
---
${selectedMessage.body_text || selectedMessage.snippet || ""}
---

Consigne de l'utilisateur : ${replyInstruction.trim()}

Rédige UNIQUEMENT le corps de la réponse (pas d'objet, pas de "Re:"). Commence directement par la formule de salutation.`;

    generateWithAI(prompt, setReplyBody);
  }, [selectedMessage, replyInstruction, generateWithAI]);

  const generateComposeEmail = useCallback(() => {
    if (!composeInstruction.trim()) return;
    const prompt = `Tu es un assistant de rédaction d'emails professionnels. Rédige un email.

${composeTo ? `Destinataire : ${composeTo}` : ""}
${composeSubject ? `Objet : ${composeSubject}` : ""}

Consigne : ${composeInstruction.trim()}

Rédige UNIQUEMENT le corps de l'email. Commence directement par la formule de salutation.`;

    generateWithAI(prompt, setComposeBody);
  }, [composeTo, composeSubject, composeInstruction, generateWithAI]);

  // ── Determine current view ──
  const isThreadList = !composing && !selectedThread;
  const isThreadDetail = !composing && !!selectedThread;

  const connectedAccount = accounts.find((a) => a.id === selectedAccountId && a.status === "connected");
  const hasAccount = !!connectedAccount;

  // ── Send status banner ──
  const SendStatusBanner = () => {
    if (sendStatus === "idle") return null;
    return (
      <div className={`flex items-center gap-2 px-4 py-2.5 text-sm border-t ${
        sendStatus === "sending" ? "bg-primary/5 text-primary border-primary/20" :
        sendStatus === "sent" ? "bg-green-500/5 text-green-600 border-green-500/20" :
        "bg-destructive/5 text-destructive border-destructive/20"
      }`}>
        {sendStatus === "sending" && (
          <>
            <Loader2 className="h-4 w-4 animate-spin" />
            <span>Envoi en cours…</span>
          </>
        )}
        {sendStatus === "sent" && (
          <>
            <Check className="h-4 w-4" />
            <span>Email envoyé avec succès</span>
          </>
        )}
        {sendStatus === "failed" && (
          <>
            <AlertCircle className="h-4 w-4" />
            <span>Erreur : {sendError || "Erreur inconnue"}</span>
            <Button variant="outline" size="sm" className="ml-auto gap-1.5" onClick={handleRetrySend}>
              <RefreshCw className="h-3.5 w-3.5" />
              Réessayer
            </Button>
          </>
        )}
      </div>
    );
  };

  // ── Assistant selector widget ──
  const AssistantSelector = () => (
    assistants.length > 0 ? (
      <>
        <div className="w-px h-4 bg-border/50" />
        <Bot className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
        <select
          value={selectedAssistantId || ""}
          onChange={(e) => setSelectedAssistantId(e.target.value)}
          className="bg-transparent border-0 text-xs text-muted-foreground hover:text-foreground outline-none cursor-pointer py-0.5 pr-4 max-w-[140px] truncate"
        >
          {assistants.map((a: Assistant) => (
            <option key={a.id} value={a.id}>
              {a.name}
            </option>
          ))}
        </select>
      </>
    ) : null
  );

  // ── Helper: format date ──
  const formatDate = (dateStr: string) => {
    try {
      return new Date(dateStr).toLocaleDateString("fr-FR", {
        day: "numeric",
        month: "short",
        year: "numeric",
      });
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* ── Header with breadcrumb ── */}
      <div className="flex items-center gap-2 sm:gap-3 h-auto min-h-[3.5rem] px-3 sm:px-5 py-2 border-b border-border bg-surface-elevated shrink-0 flex-wrap">
        {/* Breadcrumb navigation */}
        {isThreadList && (
          <>
            <Mail className="h-4 w-4 text-primary shrink-0 hidden sm:block" />
            <h1 className="font-display font-semibold text-foreground text-sm sm:text-base">Emails</h1>
            {hasAccount && (
              <span className="text-xs text-muted-foreground hidden lg:inline">
                {connectedAccount?.email_address || connectedAccount?.provider} · {threads.length} threads
              </span>
            )}
          </>
        )}

        {isThreadDetail && selectedThread && (
          <div className="flex items-center gap-1.5 min-w-0 flex-1">
            <button
              onClick={() => { setSelectedThread(null); setSelectedMessage(null); setReplying(false); setReplyBody(""); setReplyAttachments([]); }}
              className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors shrink-0"
            >
              <Mail className="h-4 w-4" />
              <span className="hidden sm:inline">Emails</span>
            </button>
            <ChevronRight className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
            <span className="text-sm font-medium text-foreground truncate">{selectedThread.subject || "(sans objet)"}</span>
            <Badge variant="outline" className="ml-1 text-[10px] shrink-0 hidden sm:inline-flex">
              {selectedThread.message_count} message{selectedThread.message_count > 1 ? "s" : ""}
            </Badge>
          </div>
        )}

        {composing && (
          <div className="flex items-center gap-1.5 min-w-0 flex-1">
            <button
              onClick={() => setComposing(false)}
              className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors shrink-0"
            >
              <Mail className="h-4 w-4" />
              <span className="hidden sm:inline">Emails</span>
            </button>
            <ChevronRight className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
            <span className="text-sm font-medium text-foreground">Nouvel email</span>
          </div>
        )}

        {/* Right-side actions */}
        <div className="ml-auto flex items-center gap-2">
          {/* Account selector */}
          {accounts.length > 1 && (
            <select
              value={selectedAccountId || ""}
              onChange={(e) => setSelectedAccountId(e.target.value)}
              className="bg-transparent border border-border rounded-md text-xs px-2 py-1.5 outline-none"
            >
              {accounts.filter(a => a.status === "connected").map((a) => (
                <option key={a.id} value={a.id}>
                  {a.email_address || a.provider}
                </option>
              ))}
            </select>
          )}

          {isThreadList && (
            <div className="relative hidden sm:block">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
              <Input
                placeholder="Rechercher…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9 h-9 w-36 lg:w-56 text-sm"
              />
            </div>
          )}

          {hasAccount && (
            <Button
              variant="ghost"
              size="sm"
              className="gap-1.5 shrink-0"
              onClick={() => {
                if (selectedAccountId) {
                  mailApi.triggerSync(selectedAccountId);
                  queryClient.invalidateQueries({ queryKey: ["mail-threads"] });
                }
              }}
              title="Synchroniser"
            >
              <RefreshCw className="h-3.5 w-3.5" />
            </Button>
          )}

          <Button
            variant="premium"
            size="sm"
            className="gap-1.5 shrink-0"
            onClick={openCompose}
            disabled={!hasAccount}
          >
            <Plus className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Nouvel email</span>
            <span className="sm:hidden">Nouveau</span>
          </Button>
        </div>
      </div>

      {/* ── Content ── */}
      <div className="flex-1 overflow-auto">

        {/* ═══ No account connected ═══ */}
        {!hasAccount && !composing && (
          <div className="flex flex-col items-center justify-center h-full gap-4 px-4">
            <Mail className="h-12 w-12 text-muted-foreground/40" />
            <p className="text-sm text-muted-foreground text-center">
              Connectez un compte email pour commencer
            </p>
            <div className="flex gap-2">
              <Button
                variant="premium"
                size="sm"
                className="gap-1.5"
                onClick={async () => {
                  try {
                    const res = await mailApi.connect("gmail");
                    window.open(res.connect_url, "_blank", "width=600,height=700");
                    // Clear any previous finalize poll
                    if (finalizePollRef.current) clearInterval(finalizePollRef.current);
                    // After popup closes, finalize
                    const checkInterval = setInterval(async () => {
                      try {
                        const account = await mailApi.finalize(res.account_id);
                        if (account.status === "connected") {
                          clearInterval(checkInterval);
                          finalizePollRef.current = null;
                          queryClient.invalidateQueries({ queryKey: ["mail-accounts"] });
                          setSelectedAccountId(account.id);
                        }
                      } catch {
                        // Keep polling
                      }
                    }, 2000);
                    finalizePollRef.current = checkInterval;
                    setTimeout(() => { clearInterval(checkInterval); finalizePollRef.current = null; }, 60000);
                  } catch (e) {
                    console.error("Gmail connect error:", e);
                  }
                }}
              >
                <Mail className="h-3.5 w-3.5" />
                Gmail
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="gap-1.5"
                onClick={async () => {
                  try {
                    const res = await mailApi.connect("microsoft");
                    window.open(res.connect_url, "_blank", "width=600,height=700");
                    if (finalizePollRef.current) clearInterval(finalizePollRef.current);
                    const checkInterval = setInterval(async () => {
                      try {
                        const account = await mailApi.finalize(res.account_id);
                        if (account.status === "connected") {
                          clearInterval(checkInterval);
                          finalizePollRef.current = null;
                          queryClient.invalidateQueries({ queryKey: ["mail-accounts"] });
                          setSelectedAccountId(account.id);
                        }
                      } catch {
                        // Keep polling
                      }
                    }, 2000);
                    finalizePollRef.current = checkInterval;
                    setTimeout(() => { clearInterval(checkInterval); finalizePollRef.current = null; }, 60000);
                  } catch (e) {
                    console.error("Outlook connect error:", e);
                  }
                }}
              >
                <Mail className="h-3.5 w-3.5" />
                Outlook
              </Button>
            </div>
          </div>
        )}

        {/* ═══ Thread list ═══ */}
        {isThreadList && hasAccount && (
          <div className="max-w-3xl mx-auto px-4 sm:px-6 py-6">
            {/* Search on mobile */}
            <div className="relative sm:hidden mb-4">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
              <Input
                placeholder="Rechercher…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9 h-10 text-sm"
              />
            </div>

            {threadsLoading && (
              <div className="flex items-center justify-center py-16 text-muted-foreground">
                <Loader2 className="h-5 w-5 animate-spin mr-2" />
                Chargement…
              </div>
            )}

            {!threadsLoading && (
              <div className="space-y-2">
                {filteredThreads.map((thread) => {
                  const senderName = thread.participants?.[0]?.name || thread.participants?.[0]?.email || "?";
                  const initials = senderName.split(" ").map((n) => n[0]).join("").slice(0, 2).toUpperCase();
                  return (
                    <button
                      key={thread.thread_key}
                      onClick={() => { setSelectedThread(thread); setSelectedMessage(null); setReplying(false); }}
                      className="group flex items-center gap-4 w-full px-4 py-4 rounded-lg bg-card border border-border hover:shadow-soft hover:border-primary/20 transition-all text-left"
                    >
                      <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center shrink-0 font-display font-semibold text-xs text-foreground">
                        {initials}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium text-foreground truncate">{senderName}</span>
                          {thread.message_count > 1 && (
                            <span className="text-[10px] text-muted-foreground">({thread.message_count})</span>
                          )}
                        </div>
                        <div className="text-sm text-foreground truncate">{thread.subject || "(sans objet)"}</div>
                        <div className="text-xs text-muted-foreground mt-0.5 truncate">{thread.snippet}</div>
                      </div>
                      <div className="text-xs text-muted-foreground shrink-0 hidden sm:block">
                        {formatDate(thread.last_date)}
                      </div>
                      <ChevronRight className="h-4 w-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity shrink-0" />
                    </button>
                  );
                })}
              </div>
            )}

            {!threadsLoading && filteredThreads.length === 0 && (
              <div className="text-center py-16 text-sm text-muted-foreground">
                <Mail className="h-10 w-10 mx-auto mb-3 text-muted-foreground/40" />
                {search ? "Aucun thread trouvé" : "Aucun email synchronisé"}
              </div>
            )}
          </div>
        )}

        {/* ═══ Thread detail ═══ */}
        {isThreadDetail && selectedThread && (
          <div className="max-w-2xl mx-auto px-4 sm:px-6 py-6 space-y-4 animate-fade-in">
            {threadDetail?.messages.map((msg, idx) => {
              const senderInitials = (msg.sender?.name || msg.sender?.email || "?").split(" ").map((n) => n[0]).join("").slice(0, 2).toUpperCase();
              const isLast = idx === (threadDetail.messages.length - 1);
              return (
                <div key={msg.id} className="bg-card border border-border rounded-lg p-4 sm:p-6 shadow-soft">
                  <div className="flex items-center gap-3 pb-4 mb-4 border-b border-border">
                    <div className="w-9 h-9 rounded-full bg-muted flex items-center justify-center font-display font-semibold text-xs text-foreground shrink-0">
                      {senderInitials}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-medium text-foreground">{msg.sender?.name || msg.sender?.email}</div>
                      <div className="text-xs text-muted-foreground truncate">
                        {msg.is_sent ? `à ${msg.to_recipients?.map(r => r.name || r.email).join(", ")}` : `de ${msg.sender?.email}`}
                      </div>
                    </div>
                    <div className="ml-auto text-xs text-muted-foreground shrink-0 hidden sm:block">
                      {formatDate(msg.date)}
                    </div>
                    {msg.is_sent && <Badge variant="default" className="text-[10px] shrink-0">Envoyé</Badge>}
                  </div>
                  <div className="text-sm leading-relaxed text-foreground whitespace-pre-line">
                    {msg.body_text || msg.snippet || ""}
                  </div>

                  {/* Reply/Forward buttons on last message */}
                  {isLast && !replying && (
                    <div className="flex items-center gap-2 flex-wrap mt-4 pt-4 border-t border-border">
                      <Button variant="action" size="sm" className="gap-1.5" onClick={() => { setReplying(true); setReplyBody(""); setSelectedMessage(msg); setSendStatus("idle"); }}>
                        <Reply className="h-3.5 w-3.5" />
                        Répondre
                      </Button>
                      <Button variant="outline" size="sm" className="gap-1.5">
                        <Forward className="h-3.5 w-3.5" />
                        Transférer
                      </Button>
                    </div>
                  )}
                </div>
              );
            })}

            {/* Reply composer */}
            {replying && selectedMessage && (
              <div className="bg-card border border-border rounded-lg shadow-soft animate-fade-in">
                {/* Toolbar */}
                <div className="px-4 py-2.5 border-b border-border flex items-center gap-3 flex-wrap bg-muted/30">
                  <Reply className="h-3.5 w-3.5 text-primary shrink-0" />
                  <span className="text-xs text-muted-foreground shrink-0">Réponse à {selectedMessage.sender?.name || selectedMessage.sender?.email}</span>
                  <AssistantSelector />
                </div>

                {/* Main email body field */}
                <div className="relative">
                  <textarea
                    value={replyBody}
                    onChange={(e) => setReplyBody(e.target.value)}
                    className="w-full min-h-[160px] sm:min-h-[200px] p-4 pr-14 text-sm leading-relaxed bg-transparent outline-none resize-none text-foreground placeholder:text-muted-foreground"
                    placeholder="Rédigez directement votre réponse ici ou dictez-la…"
                    autoFocus
                  />
                  <button
                    onClick={() => toggleRecordingFor(setReplyBody)}
                    className={`absolute right-3 bottom-3 w-9 h-9 rounded-full flex items-center justify-center transition-all ${
                      isRecording && dictationTargetRef.current === setReplyBody
                        ? "bg-destructive text-destructive-foreground animate-pulse"
                        : "bg-muted hover:bg-accent/20 text-muted-foreground hover:text-foreground"
                    }`}
                    title={isRecording ? "Arrêter la dictée" : "Dicter le contenu"}
                  >
                    <Mic className="h-4 w-4" />
                  </button>
                </div>

                {/* Generating indicator */}
                {isGenerating && (
                  <div className="flex items-center gap-2 px-4 py-2 text-xs text-primary border-t border-border/50 bg-primary/5">
                    <Loader2 className="h-3 w-3 animate-spin" />
                    <span className="flex-1">L'IA rédige votre réponse…</span>
                    <button onClick={stopGeneration} className="text-xs text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1">
                      <Square className="h-3 w-3" />
                      Arrêter
                    </button>
                  </div>
                )}

                {/* Reply attachments */}
                {replyAttachments.length > 0 && (
                  <div className="px-4 py-2.5 border-t border-border/50 bg-muted/10 flex items-center gap-2 flex-wrap">
                    <Paperclip className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                    {replyAttachments.map((att) => (
                      <span
                        key={att.id}
                        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-accent/50 text-xs text-foreground border border-border"
                      >
                        <FileText className="h-3 w-3 text-primary shrink-0" />
                        <span className="truncate max-w-[160px]">{att.name}</span>
                        <button
                          onClick={() => handleRemoveReplyAttachment(att.id)}
                          className="text-muted-foreground hover:text-destructive transition-colors"
                        >
                          <X className="h-3 w-3" />
                        </button>
                      </span>
                    ))}
                  </div>
                )}

                {/* AI instruction field */}
                <div className="border-t border-border bg-muted/20">
                  <div className="px-4 pt-3 pb-1">
                    <label className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
                      <Sparkles className="h-3 w-3 text-primary" />
                      Consigne IA
                    </label>
                  </div>
                  <div className="relative px-4 pb-2">
                    <div className="flex gap-2">
                      <div className="relative flex-1">
                        <input
                          type="text"
                          value={replyInstruction}
                          onChange={(e) => setReplyInstruction(e.target.value)}
                          onKeyDown={(e) => { if (e.key === "Enter" && replyInstruction.trim() && !isGenerating) generateReply(); }}
                          className="w-full h-9 px-3 pr-10 text-sm bg-background border border-border rounded-md outline-none focus:ring-1 focus:ring-primary/30 placeholder:text-muted-foreground"
                          placeholder="Ex : Confirmer la réception et proposer un rendez-vous…"
                          disabled={isGenerating}
                        />
                        <button
                          onClick={() => toggleRecordingFor(setReplyInstruction)}
                          className={`absolute right-2 top-1/2 -translate-y-1/2 w-6 h-6 rounded-full flex items-center justify-center transition-all ${
                            isRecording && dictationTargetRef.current === setReplyInstruction
                              ? "bg-destructive text-destructive-foreground animate-pulse"
                              : "text-muted-foreground hover:text-foreground"
                          }`}
                          title="Dicter la consigne"
                        >
                          <Mic className="h-3.5 w-3.5" />
                        </button>
                      </div>
                      <Button
                        variant="premium"
                        size="sm"
                        className="gap-1.5 shrink-0 h-9"
                        onClick={generateReply}
                        disabled={!replyInstruction.trim() || isGenerating || !selectedAssistantId}
                      >
                        {isGenerating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
                        Générer
                      </Button>
                    </div>
                  </div>
                </div>

                {/* Recording indicator */}
                {isRecording && (
                  <div className="flex items-center justify-center gap-2 px-4 py-2 text-xs text-destructive border-t border-border/50 bg-destructive/5">
                    <span className="relative flex h-2 w-2">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-destructive opacity-75" />
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-destructive" />
                    </span>
                    Écoute en cours… Parlez pour dicter
                  </div>
                )}

                {/* Send status */}
                <SendStatusBanner />

                {/* Action bar */}
                <div className="px-4 py-3 border-t border-border flex items-center gap-2 flex-wrap">
                  <Button
                    variant="premium"
                    size="sm"
                    className="gap-1.5"
                    disabled={!replyBody.trim() || isGenerating || sendStatus === "sending"}
                    onClick={handleSendReply}
                  >
                    {sendStatus === "sending" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
                    Envoyer
                  </Button>

                  {/* Attach button for reply */}
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="outline" size="sm" className="gap-1.5">
                        <Paperclip className="h-3.5 w-3.5" />
                        Joindre
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent side="top" align="start" sideOffset={8}>
                      <DropdownMenuItem onClick={() => replyFileInputRef.current?.click()}>
                        <Paperclip className="h-4 w-4 mr-2" />
                        Importer un fichier
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => { setDocPickerTarget("reply"); setShowDocPicker(true); }}>
                        <FileText className="h-4 w-4 mr-2" />
                        Depuis mes documents
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                  <input
                    ref={replyFileInputRef}
                    type="file"
                    className="hidden"
                    onChange={handleAddReplyFile}
                  />

                  <div className="flex-1" />
                  <Button variant="ghost" size="sm" onClick={() => { setReplying(false); setReplyBody(""); setReplyInstruction(""); setReplyAttachments([]); stopGeneration(); stopRecording(); setSendStatus("idle"); }}>
                    Annuler
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ═══ Compose new email ═══ */}
        {composing && (
          <div className="max-w-2xl mx-auto px-4 sm:px-6 py-6 animate-fade-in">
            <div className="bg-card border border-border rounded-xl shadow-soft overflow-hidden">
              {/* To + Subject fields */}
              <div className="border-b border-border">
                <div className="flex items-center border-b border-border/50">
                  <span className="text-xs font-medium text-muted-foreground pl-4 w-10 shrink-0">À</span>
                  <Input
                    value={composeTo}
                    onChange={(e) => setComposeTo(e.target.value)}
                    placeholder="nom@exemple.com"
                    className="border-0 shadow-none rounded-none h-10 text-sm focus-visible:ring-0"
                  />
                </div>
                <div className="flex items-center">
                  <span className="text-xs font-medium text-muted-foreground pl-4 w-10 shrink-0">Obj.</span>
                  <Input
                    value={composeSubject}
                    onChange={(e) => setComposeSubject(e.target.value)}
                    placeholder="Objet de l'email"
                    className="border-0 shadow-none rounded-none h-10 text-sm focus-visible:ring-0"
                  />
                </div>
              </div>

              {/* Assistant selector bar */}
              <div className="px-4 py-2.5 border-b border-border/50 flex items-center gap-3 bg-muted/30 flex-wrap">
                <Sparkles className="h-3.5 w-3.5 text-primary shrink-0" />
                <AssistantSelector />
              </div>

              {/* Body */}
              <div className="relative">
                <textarea
                  value={composeBody}
                  onChange={(e) => setComposeBody(e.target.value)}
                  className="w-full min-h-[220px] p-4 pr-14 text-sm leading-relaxed bg-transparent outline-none resize-none text-foreground placeholder:text-muted-foreground"
                  placeholder="Rédigez votre email ici ou dictez-le…"
                  autoFocus
                />
                <button
                  onClick={() => toggleRecordingFor(setComposeBody)}
                  className={`absolute right-3 bottom-3 w-9 h-9 rounded-full flex items-center justify-center transition-all ${
                    isRecording && dictationTargetRef.current === setComposeBody
                      ? "bg-destructive text-destructive-foreground animate-pulse"
                      : "bg-muted hover:bg-accent/20 text-muted-foreground hover:text-foreground"
                  }`}
                  title={isRecording ? "Arrêter la dictée" : "Dicter le contenu"}
                >
                  <Mic className="h-4 w-4" />
                </button>
              </div>

              {/* Generating indicator */}
              {isGenerating && (
                <div className="flex items-center gap-2 px-4 py-2 text-xs text-primary border-t border-border/50 bg-primary/5">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  <span className="flex-1">L'IA rédige votre email…</span>
                  <button onClick={stopGeneration} className="text-xs text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1">
                    <Square className="h-3 w-3" />
                    Arrêter
                  </button>
                </div>
              )}

              {/* Attachments */}
              {composeAttachments.length > 0 && (
                <div className="px-4 py-2.5 border-t border-border/50 bg-muted/10 flex items-center gap-2 flex-wrap">
                  <Paperclip className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                  {composeAttachments.map((att) => (
                    <span
                      key={att.id}
                      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-accent/50 text-xs text-foreground border border-border"
                    >
                      <FileText className="h-3 w-3 text-primary shrink-0" />
                      <span className="truncate max-w-[160px]">{att.name}</span>
                      <button
                        onClick={() => handleRemoveAttachment(att.id)}
                        className="text-muted-foreground hover:text-destructive transition-colors"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </span>
                  ))}
                </div>
              )}

              {/* AI instruction field */}
              <div className="border-t border-border bg-muted/20">
                <div className="px-4 pt-3 pb-1">
                  <label className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
                    <Sparkles className="h-3 w-3 text-primary" />
                    Consigne IA
                  </label>
                </div>
                <div className="relative px-4 pb-2">
                  <div className="flex gap-2">
                    <div className="relative flex-1">
                      <input
                        type="text"
                        value={composeInstruction}
                        onChange={(e) => setComposeInstruction(e.target.value)}
                        onKeyDown={(e) => { if (e.key === "Enter" && composeInstruction.trim() && !isGenerating) generateComposeEmail(); }}
                        className="w-full h-9 px-3 pr-10 text-sm bg-background border border-border rounded-md outline-none focus:ring-1 focus:ring-primary/30 placeholder:text-muted-foreground"
                        placeholder="Ex : Email de relance suite au devis envoyé la semaine dernière…"
                        disabled={isGenerating}
                      />
                      <button
                        onClick={() => toggleRecordingFor(setComposeInstruction)}
                        className={`absolute right-2 top-1/2 -translate-y-1/2 w-6 h-6 rounded-full flex items-center justify-center transition-all ${
                          isRecording && dictationTargetRef.current === setComposeInstruction
                            ? "bg-destructive text-destructive-foreground animate-pulse"
                            : "text-muted-foreground hover:text-foreground"
                        }`}
                        title="Dicter la consigne"
                      >
                        <Mic className="h-3.5 w-3.5" />
                      </button>
                    </div>
                    <Button
                      variant="premium"
                      size="sm"
                      className="gap-1.5 shrink-0 h-9"
                      onClick={generateComposeEmail}
                      disabled={!composeInstruction.trim() || isGenerating || !selectedAssistantId}
                    >
                      {isGenerating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
                      Générer
                    </Button>
                  </div>
                </div>
              </div>

              {/* Recording indicator */}
              {isRecording && (
                <div className="flex items-center justify-center gap-2 px-4 py-2 text-xs text-destructive border-t border-border/50 bg-destructive/5">
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-destructive opacity-75" />
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-destructive" />
                  </span>
                  Écoute en cours… Parlez pour dicter
                </div>
              )}

              {/* Send status */}
              <SendStatusBanner />

              {/* Actions bar */}
              <div className="px-4 py-3 border-t border-border flex items-center gap-2 bg-muted/20 flex-wrap">
                <Button
                  variant="premium"
                  size="sm"
                  className="gap-1.5"
                  disabled={!composeTo.trim() || !composeBody.trim() || isGenerating || sendStatus === "sending"}
                  onClick={handleSendCompose}
                >
                  {sendStatus === "sending" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
                  Envoyer
                </Button>
                <Button variant="outline" size="sm" disabled={!composeBody.trim() || isGenerating}>
                  Brouillon
                </Button>

                {/* Attach button */}
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="outline" size="sm" className="gap-1.5">
                      <Paperclip className="h-3.5 w-3.5" />
                      Joindre
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent side="top" align="start" sideOffset={8}>
                    <DropdownMenuItem onClick={() => fileInputRef.current?.click()}>
                      <Paperclip className="h-4 w-4 mr-2" />
                      Importer un fichier
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => { setDocPickerTarget("compose"); setShowDocPicker(true); }}>
                      <FileText className="h-4 w-4 mr-2" />
                      Depuis mes documents
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
                <input
                  ref={fileInputRef}
                  type="file"
                  className="hidden"
                  onChange={handleAddLocalFile}
                />

                <div className="flex-1" />
                <Button variant="ghost" size="sm" onClick={() => { setComposing(false); setComposeInstruction(""); setComposeAttachments([]); stopGeneration(); stopRecording(); setSendStatus("idle"); }}>
                  Annuler
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* Document picker dialog */}
        <Dialog open={showDocPicker} onOpenChange={setShowDocPicker}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle>Joindre un document</DialogTitle>
              <DialogDescription>
                Sélectionnez un document validé à joindre en PDF.
              </DialogDescription>
            </DialogHeader>
            <div className="max-h-[300px] overflow-auto space-y-1 py-2">
              {!validatedDocs && (
                <div className="flex items-center justify-center py-8 text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  Chargement…
                </div>
              )}
              {validatedDocs && validatedDocs.length === 0 && (
                <p className="text-sm text-muted-foreground text-center py-8">
                  Aucun document validé disponible.
                </p>
              )}
              {validatedDocs?.map((doc) => (
                <button
                  key={doc.id}
                  onClick={() =>
                    docPickerTarget === "reply"
                      ? handlePickDocumentForReply(doc.id, doc.title)
                      : handlePickDocument(doc.id, doc.title)
                  }
                  className="w-full flex items-center gap-3 px-3 py-2.5 rounded-md hover:bg-accent/50 transition-colors text-left"
                >
                  <FileText className="h-4 w-4 text-primary shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-foreground truncate">{doc.title}</div>
                    <div className="text-xs text-muted-foreground">
                      {new Date(doc.updated_at).toLocaleDateString("fr-FR")}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
};

export default EmailComposer;
