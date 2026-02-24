import { Mail, Search, Send, ChevronRight, Reply, Forward, Mic, Plus, Sparkles, Bot, Loader2, Square, Paperclip, X, FileText, RefreshCw, AlertCircle, Check, Server, MoreVertical, Trash2, Inbox, FileEdit, Calendar, Bold, Italic, List, ListOrdered, Link as LinkIcon, Type, MessageSquare } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { marked } from "marked";
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
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { Label } from "@/components/ui/label";
import { useState, useRef, useCallback, useEffect } from "react";
import { useToast } from "@/hooks/use-toast";
import { useLocation, useSearchParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { assistantsApi } from "@/api/assistants";
import { chatApi } from "@/api/chat";
import { workspaceDocumentsApi } from "@/api/workspace-documents";
import { mailApi } from "@/api/mail";
import { settingsApi } from "@/api/settings";
import { contactsApi } from "@/api/contacts";
import type { MailThreadSummary, MailMessage, MailDraft, MailContactSummary } from "@/api/mail";
import type { Assistant } from "@/types";
import { AddToFolderDialog } from "@/components/folders/AddToFolderDialog";
import { EmailAssistantProvider, useEmailAssistant, type EmailDraftUpdate } from "@/contexts/email-assistant-stream";
import { EmailAssistantSidebar } from "@/components/email/email-assistant-sidebar";

interface EmailAttachment {
  id: string;
  name: string;
  url: string;
  type: "pdf" | "file";
  sourceDocId?: string;
}

// ── Speech Recognition: see src/speech-recognition.d.ts ──

const DRAFT_STORAGE_KEY = "ancre-email-draft";

interface EmailDraft {
  to: string;
  subject: string;
  body: string;
  instruction: string;
  savedAt: string;
}

function loadDraft(): EmailDraft | null {
  try {
    const raw = localStorage.getItem(DRAFT_STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as EmailDraft;
  } catch {
    return null;
  }
}


function clearDraft() {
  try {
    localStorage.removeItem(DRAFT_STORAGE_KEY);
  } catch {
    // ignore
  }
}

function stripHtmlToText(html: string): string {
  if (!html.trim()) return "";
  const div = document.createElement("div");
  div.innerHTML = html;
  return div.textContent || div.innerText || "";
}

function extractRecipientEmail(input: string): string {
  const value = input.trim();
  if (!value) return "";
  const angleMatch = value.match(/<([^>]+)>/);
  if (angleMatch?.[1]) return angleMatch[1].trim();
  return value;
}

function extractRecipientNameFromText(text: string): string | null {
  const match = text.match(/(?:\b(?:a|à)\b)\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ' -]{1,80})/i);
  if (!match?.[1]) return null;
  return match[1].replace(/[.,;:!?]+$/g, "").trim();
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function buildForwardBody(message: MailMessage): string {
  const originalBody = message.body_html?.trim()
    ? message.body_html
    : `<p>${escapeHtml(message.body_text || message.snippet || "")}</p>`;
  const from = message.sender?.name
    ? `${message.sender.name} &lt;${message.sender.email}&gt;`
    : (message.sender?.email || "");
  return `
<p><br/></p>
<p>---------- Message transfere ----------</p>
<p><strong>De :</strong> ${from}</p>
<p><strong>Date :</strong> ${message.date}</p>
<p><strong>Objet :</strong> ${escapeHtml(message.subject || "(sans objet)")}</p>
<p><br/></p>
${originalBody}
  `.trim();
}

const EmailComposerContent = () => {
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const { toast } = useToast();

  // ── Mail account state ──
  const [selectedAccountId, setSelectedAccountId] = useState<string | null>(null);

  // ── Signature mail (paramètres tenant) ──
  const { data: tenantSettings } = useQuery({
    queryKey: ["tenant-settings"],
    queryFn: settingsApi.get,
  });
  const mailSignature = tenantSettings?.mail_signature?.trim() ?? "";

  // ── Navigation state ──
  const [selectedThread, setSelectedThread] = useState<MailThreadSummary | null>(null);
  const [selectedMessage, setSelectedMessage] = useState<MailMessage | null>(null);
  const [search, setSearch] = useState("");
  const [replying, setReplying] = useState(false);
  const [replyBody, setReplyBody] = useState("");
  const [, setReplyInstruction] = useState("");

  // ── Compose new email state ──
  const [composing, setComposing] = useState(false);
  const [composeTo, setComposeTo] = useState("");
  const [composeSubject, setComposeSubject] = useState("");
  const [composeBody, setComposeBody] = useState("");
  const [composeInstruction, setComposeInstruction] = useState("");
  const [composeAttachments, setComposeAttachments] = useState<EmailAttachment[]>([]);
  const [showDocPicker, setShowDocPicker] = useState(false);
  const [docPickerTarget, setDocPickerTarget] = useState<"compose" | "reply">("compose");
  const [currentDraftId, setCurrentDraftId] = useState<string | null>(null);
  const [scheduleDate, setScheduleDate] = useState<string | null>(null);
  const [showSchedulePicker, setShowSchedulePicker] = useState(false);
  const [showLinkDialog, setShowLinkDialog] = useState(false);
  const [linkUrl, setLinkUrl] = useState("");
  const [linkText, setLinkText] = useState("");
  const [linkContext, setLinkContext] = useState<'compose' | 'reply'>('compose');
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
  const composeBodyRef = useRef<HTMLDivElement>(null);
  const replyBodyRef = useRef<HTMLDivElement>(null);
  const isUserTypingCompose = useRef(false);
  const isUserTypingReply = useRef(false);

  // ── SMTP connect ──
  const [showSmtpDialog, setShowSmtpDialog] = useState(false);
  const [smtpHost, setSmtpHost] = useState("");
  const [smtpPort, setSmtpPort] = useState("587");
  const [smtpUser, setSmtpUser] = useState("");
  const [smtpPassword, setSmtpPassword] = useState("");
  const [smtpUseTls, setSmtpUseTls] = useState(true);
  const [smtpEmail, setSmtpEmail] = useState("");
  const [smtpError, setSmtpError] = useState<string | null>(null);
  const [smtpLoading, setSmtpLoading] = useState(false);

  // ── Reply attachments ──
  const [replyAttachments, setReplyAttachments] = useState<EmailAttachment[]>([]);

  // ── Send state ──
  const [, setSendingClientId] = useState<string | null>(null);
  const [sendStatus, setSendStatus] = useState<"idle" | "sending" | "sent" | "failed">("idle");
  const [sendError, setSendError] = useState<string | null>(null);

  // ── Tabs ──
  const [activeTab, setActiveTab] = useState<"inbox" | "sent" | "scheduled" | "drafts" | "deleted">("inbox");

  // ── Navigation level (contacts → threads → detail) ──
  const [viewLevel, setViewLevel] = useState<"contacts" | "threads" | "detail">("contacts");
  const [selectedContact, setSelectedContact] = useState<MailContactSummary | null>(null);

  // ── Add to folder ──
  const [addToFolderTarget, setAddToFolderTarget] = useState<{ threadKey: string; subject: string } | null>(null);

  // ── Shared state ──
  const [isRecording, setIsRecording] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [selectedAssistantId, setSelectedAssistantId] = useState<string | null>(null);

  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);
  const wantsRecordingRef = useRef(false);
  const abortGenerationRef = useRef<(() => void) | null>(null);
  const pendingAutoGenerateRef = useRef<string | null>(null);
  const dictationTargetRef = useRef<React.Dispatch<React.SetStateAction<string>>>(setComposeBody);
  const sendPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const finalizePollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const draftIdRef = useRef<string | null>(null);
  draftIdRef.current = currentDraftId;

  // Keep refs in sync for unmount draft save (e.g. user navigates away)
  const draftRef = useRef({ to: "", subject: "", body: "", instruction: "", composing: false, sendStatus: "idle" as string });
  draftRef.current = { to: composeTo, subject: composeSubject, body: composeBody, instruction: composeInstruction, composing, sendStatus };
  const accountIdRef = useRef<string | null>(null);
  accountIdRef.current = selectedAccountId;
  useEffect(() => {
    return () => {
      const d = draftRef.current;
      const accountId = accountIdRef.current;
      const draftId = draftIdRef.current;
      if (d.composing && d.sendStatus !== "sent" && accountId && (d.body.trim() || d.to.trim() || d.subject.trim())) {
        const recipientEmail = extractRecipientEmail(d.to);
        const toRecipients = recipientEmail ? [{ name: "", email: recipientEmail }] : [];
        mailApi.saveDraft({
          mail_account_id: accountId,
          to_recipients: toRecipients,
          subject: d.subject,
          body_html: d.body,
          instruction: d.instruction,
          draft_id: draftId || undefined,
        }).catch(() => {});
        clearDraft();
      }
    };
  }, []);

  // ── Contact prefill from URL param ──
  useEffect(() => {
    const contactId = searchParams.get("contact");
    if (contactId && !composing) {
      // Fetch contact and prefill recipient
      contactsApi
        .get(contactId)
        .then((contact) => {
          setComposeTo(contact.primary_email);
          setComposing(true);

          // Optional: Set instruction based on contact type for tone adaptation
          const toneMap: Record<string, string> = {
            client: "professionnel et chaleureux",
            prospect: "engageant et informatif",
            partenaire: "collaboratif",
            fournisseur: "courtois et direct",
            candidat: "accueillant et encourageant",
            interne: "décontracté et efficace",
            autre: "neutre",
          };
          const suggestedTone = toneMap[contact.contact_type] || "neutre";

          // Prefill instruction hint (user can override)
          if (!composeInstruction) {
            setComposeInstruction(`Ton suggéré: ${suggestedTone}`);
          }

          // Remove contact param to avoid re-triggering
          searchParams.delete("contact");
          setSearchParams(searchParams, { replace: true });
        })
        .catch((err) => {
          console.error("Failed to fetch contact for prefill:", err);
          toast({
            variant: "destructive",
            title: "Erreur",
            description: "Impossible de charger le contact.",
          });
        });
    }
  }, [searchParams, composing, composeInstruction, setSearchParams, toast]);

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

  const { data: contacts = [], isLoading: loadingContacts } = useQuery({
    queryKey: ["mail-contacts", selectedAccountId],
    queryFn: () => mailApi.listContacts(selectedAccountId!),
    enabled: !!selectedAccountId && activeTab === "inbox",
    staleTime: 15_000,
  });

  const { data: threads = [], isLoading: threadsLoading } = useQuery({
    queryKey: ["mail-threads", selectedAccountId, selectedContact?.email],
    queryFn: () => mailApi.listThreads(selectedAccountId!, {
      limit: 50,
      contact_email: selectedContact?.email || undefined,
    }),
    enabled: !!selectedAccountId && activeTab === "inbox" && viewLevel === "threads",
    staleTime: 15_000,
  });

  const { data: threadDetail } = useQuery({
    queryKey: ["mail-thread-detail", selectedAccountId, selectedThread?.thread_key],
    queryFn: () => mailApi.getThread(selectedThread!.thread_key, selectedAccountId!),
    enabled: !!selectedAccountId && !!selectedThread,
    staleTime: 10_000,
  });

  const { data: drafts = [] } = useQuery({
    queryKey: ["mail-drafts", selectedAccountId],
    queryFn: () => mailApi.listDrafts(selectedAccountId!),
    enabled: !!selectedAccountId,
    staleTime: 10_000,
  });

  const { data: scheduledEmails = [] } = useQuery({
    queryKey: ["mail-scheduled", selectedAccountId],
    queryFn: () => mailApi.listScheduledEmails(selectedAccountId!),
    enabled: !!selectedAccountId && activeTab === "scheduled",
    staleTime: 10_000,
  });

  const saveDraftMutation = useMutation({
    mutationFn: (params: {
      to_recipients: { name: string; email: string }[];
      subject: string;
      body_html: string;
      instruction: string;
      draft_id?: string;
    }) =>
      mailApi.saveDraft({
        mail_account_id: selectedAccountId!,
        ...params,
      }),
    onSuccess: (saved) => {
      setCurrentDraftId(saved.id);
      clearDraft();
      queryClient.invalidateQueries({ queryKey: ["mail-drafts"] });
      toast({
        title: "Brouillon sauvegardé",
        description: "Votre email apparaît dans la liste des brouillons.",
      });
    },
    onError: () => {
      toast({
        variant: "destructive",
        title: "Erreur",
        description: "Impossible de sauvegarder le brouillon.",
      });
    },
  });

  const deleteDraftMutation = useMutation({
    mutationFn: (draftId: string) => mailApi.deleteDraft(draftId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["mail-drafts"] });
      toast({ title: "Brouillon supprimé" });
    },
    onError: () => {
      toast({
        variant: "destructive",
        title: "Erreur",
        description: "Impossible de supprimer le brouillon.",
      });
    },
  });

  const scheduleEmailMutation = useMutation({
    mutationFn: mailApi.scheduleEmail,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["mail-scheduled"] });
      toast({
        title: "Email programmé",
        description: "Votre email sera envoyé à l'heure prévue"
      });
      handleLeaveCompose();
    },
    onError: () => {
      toast({
        variant: "destructive",
        title: "Erreur",
        description: "Impossible de programmer l'email.",
      });
    },
  });

  const cancelScheduledEmailMutation = useMutation({
    mutationFn: (scheduledEmailId: string) => mailApi.cancelScheduledEmail(scheduledEmailId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["mail-scheduled"] });
      toast({ title: "Email annulé" });
    },
    onError: () => {
      toast({
        variant: "destructive",
        title: "Erreur",
        description: "Impossible d'annuler l'email programmé.",
      });
    },
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
      autoGenerate?: boolean;
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
      if (state.autoGenerate) {
        pendingAutoGenerateRef.current = state.prompt;
      }
      window.history.replaceState({}, "");
    }
  }, [location.state]);

  // Load email draft bundle from chat suggestion
  useEffect(() => {
    const bundleId = searchParams.get("bundle");
    if (!bundleId) return;

    console.log("[Analytics] email_bundle_loading", { bundle_id: bundleId });

    mailApi
      .getBundle(bundleId)
      .then((bundle) => {
        setComposing(true);
        if (bundle.subject) setComposeSubject(bundle.subject);
        if (bundle.body_draft) setComposeBody(marked.parse(bundle.body_draft) as string);
        const instructionFromBundle = bundle.reason?.trim()
          || (bundle.tone ? `Ton : ${bundle.tone}` : "");
        if (instructionFromBundle) {
          setComposeInstruction(instructionFromBundle);
          if (!bundle.body_draft) {
            pendingAutoGenerateRef.current = instructionFromBundle;
          }
        }
        if (!composeTo.trim() && bundle.reason) {
          const guessedName = extractRecipientNameFromText(bundle.reason);
          if (guessedName) {
            contactsApi.search(guessedName, 5).then((matches) => {
              const exact = matches.find((c) => {
                const fullName = `${c.first_name || ""} ${c.last_name || ""}`.trim().toLowerCase();
                return fullName === guessedName.toLowerCase();
              });
              const selected = exact || matches[0];
              if (selected?.primary_email) {
                const fullName = `${selected.first_name || ""} ${selected.last_name || ""}`.trim();
                const recipient = fullName
                  ? `${fullName} <${selected.primary_email}>`
                  : selected.primary_email;
                setComposeTo(recipient);
              }
            }).catch(() => {
              // ignore if contact search fails
            });
          }
        }
        console.log("[Analytics] email_bundle_loaded", { bundle_id: bundleId });
        // Clear the bundle param to avoid re-fetching
        const nextParams = new URLSearchParams(searchParams);
        nextParams.delete("bundle");
        setSearchParams(nextParams, { replace: true });
      })
      .catch((err) => {
        console.error("[Analytics] email_bundle_load_failed", { bundle_id: bundleId, error: err });
        toast({
          title: "Erreur",
          description: "Impossible de charger le brouillon suggéré.",
          variant: "destructive",
        });
      });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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

  const openDraft = (draft: MailDraft) => {
    setCurrentDraftId(draft.id);
    setComposeTo(draft.to_recipients?.[0]?.email || "");
    setComposeSubject(draft.subject || "");
    setComposeBody(draft.body_html || "");
    setComposeInstruction(draft.instruction || "");
    setComposing(true);
  };

  const openCompose = () => {
    setCurrentDraftId(null);
    setComposing(true);
    const draft = loadDraft();
    if (draft && (draft.body || draft.to || draft.subject)) {
      setComposeTo(draft.to || "");
      setComposeSubject(draft.subject || "");
      setComposeBody(draft.body || "");
      setComposeInstruction(draft.instruction || "");
      toast({ title: "Brouillon restauré", description: "Votre email en cours a été rechargé." });
    } else {
      setComposeTo("");
      setComposeSubject("");
      setComposeBody("");
      setComposeInstruction("");
    }
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
          clearDraft(); // Don't restore sent email as draft
          if (draftIdRef.current) {
            mailApi.deleteDraft(draftIdRef.current).catch(() => {});
            queryClient.invalidateQueries({ queryKey: ["mail-drafts"] });
          }
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
    const recipientEmail = extractRecipientEmail(composeTo);
    if (!selectedAccountId || !recipientEmail || !composeBody.trim()) return;
    const clientSendId = crypto.randomUUID();
    setSendStatus("sending");
    setSendError(null);
    setSendingClientId(clientSendId);

    try {
      // composeBody is HTML (from AI or contenteditable); append tenant signature
      const bodyHtml = composeBody.trim()
        ? composeBody + (mailSignature ? `<br/><br/>${mailSignature}` : "")
        : null;
      const bodyText = stripHtmlToText(bodyHtml || composeBody);
      await mailApi.send({
        client_send_id: clientSendId,
        mail_account_id: selectedAccountId,
        mode: "new",
        to_recipients: [{ name: "", email: recipientEmail }],
        subject: composeSubject,
        body_text: bodyText || composeBody,
        body_html: bodyHtml,
      });
      pollSendStatus(clientSendId);
    } catch (e: any) {
      setSendStatus("failed");
      setSendError(e?.message || "Erreur d'envoi");
      setSendingClientId(null);
    }
  }, [selectedAccountId, composeTo, composeSubject, composeBody, mailSignature, pollSendStatus]);

  const handleSendReply = useCallback(async () => {
    if (!selectedAccountId || !replyBody.trim() || !selectedMessage) return;
    const clientSendId = crypto.randomUUID();
    setSendStatus("sending");
    setSendError(null);
    setSendingClientId(clientSendId);

    try {
      const replyHtml = replyBody.trim()
        ? replyBody + (mailSignature ? `<br/><br/>${mailSignature}` : "")
        : null;
      const bodyText = stripHtmlToText(replyHtml || replyBody);
      await mailApi.send({
        client_send_id: clientSendId,
        mail_account_id: selectedAccountId,
        mode: "reply",
        to_recipients: [selectedMessage.sender],
        subject: `Re: ${selectedMessage.subject || ""}`,
        body_text: bodyText || replyBody,
        body_html: replyHtml,
        in_reply_to_message_id: selectedMessage.id,
        provider_thread_id: selectedMessage.provider_thread_id || undefined,
      });
      pollSendStatus(clientSendId);
    } catch (e: any) {
      setSendStatus("failed");
      setSendError(e?.message || "Erreur d'envoi");
      setSendingClientId(null);
    }
  }, [selectedAccountId, replyBody, selectedMessage, mailSignature, pollSendStatus]);

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
      { message: prompt, include_history: false },
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

  const handleLeaveCompose = useCallback(() => {
    const recipientEmail = extractRecipientEmail(composeTo);
    // Auto-save draft to server if there's content and email wasn't sent
    if (sendStatus !== "sent" && selectedAccountId && (composeBody.trim() || composeTo.trim() || composeSubject.trim())) {
      const toRecipients = recipientEmail
        ? [{ name: "", email: recipientEmail }]
        : [];
      saveDraftMutation.mutate({
        to_recipients: toRecipients,
        subject: composeSubject,
        body_html: composeBody,
        instruction: composeInstruction,
        draft_id: currentDraftId || undefined,
      });
      clearDraft();
    }
    if (sendStatus === "sent") clearDraft();
    setCurrentDraftId(null);
    setComposing(false);
    setComposeTo("");
    setComposeSubject("");
    setComposeBody("");
    setComposeInstruction("");
    setComposeAttachments([]);
    setShowDocPicker(false);
    stopGeneration();
    stopRecording();
    setSendStatus("idle");
    setSendError(null);
  }, [composeTo, composeSubject, composeBody, composeInstruction, sendStatus, currentDraftId, selectedAccountId, saveDraftMutation, stopGeneration, stopRecording]);

  const handleForwardMessage = useCallback((message: MailMessage) => {
    setComposing(true);
    setCurrentDraftId(null);
    setComposeTo("");
    setComposeSubject(`Fwd: ${message.subject || "(sans objet)"}`);
    setComposeBody(buildForwardBody(message));
    setComposeInstruction("");
    setComposeAttachments([]);
    setSelectedMessage(message);
    setReplying(false);
    setReplyBody("");
    setReplyInstruction("");
    setReplyAttachments([]);
    setSendStatus("idle");
    setSendError(null);
  }, []);

  const generateComposeEmail = useCallback(() => {
    if (!composeInstruction.trim()) return;
    const prompt = `Tu es un assistant de rédaction d'emails professionnels. Rédige un email.

${composeTo ? `Destinataire : ${composeTo}` : ""}
${composeSubject ? `Objet : ${composeSubject}` : ""}

Consigne : ${composeInstruction.trim()}

IMPORTANT : Si du contexte documentaire est fourni, utilise-le UNIQUEMENT s'il est directement lié à la consigne ci-dessus. N'invente pas de contenu à partir de documents sans rapport avec la demande. En cas de doute, ignore le contexte et rédige un email simple basé uniquement sur la consigne.
Génère le corps de l'email en HTML compatible Gmail, sans Markdown.
Utilise uniquement ces balises : <p>, <br>, <strong>, <em>, <ul>, <ol>, <li>, <a href="...">.
Pas de CSS, pas de scripts, pas d'attributs style.
N'écris AUCUNE phrase d'introduction ou de mise en contexte (pas de "Voici une proposition", "Voici le mail", etc.).
Ne rédige PAS de signature (formule de politesse finale, nom, coordonnées). La signature est ajoutée automatiquement.
Commence directement par la formule de salutation (Bonjour, Madame, Monsieur, etc.).`;

    generateWithAI(prompt, setComposeBody);
  }, [composeTo, composeSubject, composeInstruction, generateWithAI]);

  // Auto-lancer la génération quand on arrive depuis le dashboard avec une dictée
  useEffect(() => {
    const pending = pendingAutoGenerateRef.current;
    if (
      pending &&
      composing &&
      composeInstruction.trim() === pending.trim() &&
      selectedAssistantId &&
      !isGenerating
    ) {
      pendingAutoGenerateRef.current = null;
      generateComposeEmail();
    }
  }, [composing, composeInstruction, selectedAssistantId, isGenerating, generateComposeEmail]);

  // Prefill recipient from direct query params (name/email) when available
  useEffect(() => {
    const contactName = searchParams.get("contact_name")
      || searchParams.get("recipient")
      || searchParams.get("to");
    if (!contactName || composeTo.trim()) return;

    contactsApi
      .search(contactName, 5)
      .then((matches) => {
        const wanted = contactName.toLowerCase().trim();
        const exact = matches.find((c) => {
          const fullName = `${c.first_name || ""} ${c.last_name || ""}`.trim().toLowerCase();
          return fullName === wanted;
        });
        const selected = exact || matches[0];
        if (selected?.primary_email) {
          const fullName = `${selected.first_name || ""} ${selected.last_name || ""}`.trim();
          const recipient = fullName
            ? `${fullName} <${selected.primary_email}>`
            : selected.primary_email;
          setComposeTo(recipient);
          setComposing(true);
        }
      })
      .catch(() => {
        // ignore if contact search fails
      })
      .finally(() => {
        const nextParams = new URLSearchParams(searchParams);
        nextParams.delete("contact_name");
        nextParams.delete("recipient");
        nextParams.delete("to");
        setSearchParams(nextParams, { replace: true });
      });
  }, [searchParams, composeTo, setSearchParams]);

  // ── Reset to inbox when sidebar "Emails" is re-clicked ──
  useEffect(() => {
    const resetTs = (location.state as { reset?: number } | null)?.reset;
    if (resetTs) {
      setViewLevel("contacts");
      setSelectedContact(null);
      setSelectedThread(null);
      setSelectedMessage(null);
      setReplying(false);
      setReplyBody("");
      setReplyInstruction("");
      setReplyAttachments([]);
      setActiveTab("inbox");
      if (composing) {
        handleLeaveCompose();
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [(location.state as { reset?: number } | null)?.reset]);

  // ── Navigation handlers ──
  const handleContactClick = (contact: MailContactSummary) => {
    setSelectedContact(contact);
    setViewLevel("threads");
  };

  const handleThreadClick = (thread: MailThreadSummary) => {
    setSelectedThread(thread);
    setViewLevel("detail");
    setSelectedMessage(null);
    setReplying(false);
  };

  const handleBackToThreads = () => {
    setSelectedThread(null);
    setViewLevel("threads");
    setReplying(false);
  };

  const handleBackToContacts = () => {
    setSelectedContact(null);
    setSelectedThread(null);
    setViewLevel("contacts");
    setReplying(false);
  };

  // ── Determine current view ──
  const isThreadList = !composing && !selectedThread;
  const isThreadDetail = !composing && !!selectedThread && viewLevel === "detail";

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

  // Sync external changes to compose body (e.g., from AI generation)
  useEffect(() => {
    if (!isUserTypingCompose.current && composeBodyRef.current) {
      if (composeBodyRef.current.innerHTML !== composeBody) {
        const selection = window.getSelection();
        const range = selection && selection.rangeCount > 0 ? selection.getRangeAt(0) : null;

        composeBodyRef.current.innerHTML = composeBody || "";

        // Restore cursor position if possible
        if (range && composeBodyRef.current.contains(range.startContainer)) {
          try {
            selection?.removeAllRanges();
            selection?.addRange(range);
          } catch (e) {
            // Ignore errors
          }
        }
      }
    }
  }, [composeBody]);

  // Sync external changes to reply body
  useEffect(() => {
    if (!isUserTypingReply.current && replyBodyRef.current) {
      if (replyBodyRef.current.innerHTML !== replyBody) {
        const selection = window.getSelection();
        const range = selection && selection.rangeCount > 0 ? selection.getRangeAt(0) : null;

        replyBodyRef.current.innerHTML = replyBody || "";

        // Restore cursor position if possible
        if (range && replyBodyRef.current.contains(range.startContainer)) {
          try {
            selection?.removeAllRanges();
            selection?.addRange(range);
          } catch (e) {
            // Ignore errors
          }
        }
      }
    }
  }, [replyBody]);

  // Text formatting functions
  const formatText = (command: string, value?: string, isReply = false) => {
    document.execCommand(command, false, value);
    if (isReply) {
      replyBodyRef.current?.focus();
    } else {
      composeBodyRef.current?.focus();
    }
  };

  const insertLink = (isReply = false) => {
    const selection = window.getSelection();
    if (selection && selection.toString()) {
      setLinkText(selection.toString());
    }
    setLinkContext(isReply ? 'reply' : 'compose');
    setShowLinkDialog(true);
  };

  const applyLink = () => {
    if (!linkUrl) return;

    const url = linkUrl.startsWith('http') ? linkUrl : `https://${linkUrl}`;

    if (linkText) {
      // Insert new link
      document.execCommand('insertHTML', false, `<a href="${url}" target="_blank">${linkText}</a>`);
    } else {
      // Wrap selection in link
      document.execCommand('createLink', false, url);
    }

    setShowLinkDialog(false);
    setLinkUrl("");
    setLinkText("");

    if (linkContext === 'reply') {
      replyBodyRef.current?.focus();
    } else {
      composeBodyRef.current?.focus();
    }
  };

  // Get email assistant context
  const { setSelectedAssistantId: setAssistantForSidebar } = useEmailAssistant();

  // Sync selected assistant with sidebar
  useEffect(() => {
    setAssistantForSidebar(selectedAssistantId);
  }, [selectedAssistantId, setAssistantForSidebar]);

  // Handle draft updates from AI assistant
  const handleDraftUpdate = useCallback((update: EmailDraftUpdate) => {
    switch (update.field) {
      case "to":
        setComposeTo(update.value);
        break;
      case "subject":
        setComposeSubject(update.value);
        break;
      case "body":
        setComposeBody(update.value);
        break;
    }

    toast({
      title: "Email mis à jour",
      description: `Le champ "${update.field === "to" ? "destinataire" : update.field === "subject" ? "objet" : "corps"}" a été mis à jour par l'assistant`,
    });
  }, [toast]);

  return (
    <>
    <div className="flex h-full">
      {/* Main content area */}
      <div className="flex flex-col flex-1 min-w-0">
        {/* ── Header with breadcrumb ── */}
        <div className="flex items-center gap-3 p-6 border-b bg-background shrink-0 flex-wrap">
        {/* Breadcrumb navigation */}
        {isThreadList && (
          <>
            <Mail className="h-4 w-4 text-primary shrink-0 hidden sm:block" />
            <h1 className="font-heading text-2xl font-bold tracking-tight text-foreground">Emails</h1>
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
              onClick={handleLeaveCompose}
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

          {hasAccount && selectedAccountId && (() => {
            const acc = accounts.find((a) => a.id === selectedAccountId);
            const canSync = acc?.provider !== "smtp";
            return canSync ? (
              <Button
                variant="ghost"
                size="sm"
                className="gap-1.5 shrink-0"
                onClick={() => {
                  mailApi.triggerSync(selectedAccountId);
                  queryClient.invalidateQueries({ queryKey: ["mail-threads"] });
                }}
                title="Synchroniser"
              >
                <RefreshCw className="h-3.5 w-3.5" />
              </Button>
            ) : null;
          })()}

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
              <Button
                variant="outline"
                size="sm"
                className="gap-1.5"
                onClick={() => {
                  setSmtpHost("");
                  setSmtpPort("587");
                  setSmtpUser("");
                  setSmtpPassword("");
                  setSmtpUseTls(true);
                  setSmtpEmail("");
                  setSmtpError(null);
                  setShowSmtpDialog(true);
                }}
              >
                <Server className="h-3.5 w-3.5" />
                SMTP
              </Button>
            </div>
          </div>
        )}

        {/* SMTP Connect Dialog */}
        <Dialog open={showSmtpDialog} onOpenChange={(open) => { setShowSmtpDialog(open); if (!open) setSmtpError(null); }}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle>Connexion SMTP</DialogTitle>
              <DialogDescription>
                Gmail (mot de passe d&apos;application), Outlook ou serveur SMTP personnalisé.
              </DialogDescription>
            </DialogHeader>
            <div className="flex gap-2 mb-4">
              <Button
                variant="outline"
                size="sm"
                className="flex-1"
                onClick={() => {
                  setSmtpHost("smtp.gmail.com");
                  setSmtpPort("587");
                  setSmtpUseTls(true);
                }}
              >
                Gmail SMTP
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="flex-1"
                onClick={() => {
                  setSmtpHost("smtp.office365.com");
                  setSmtpPort("587");
                  setSmtpUseTls(true);
                }}
              >
                Outlook SMTP
              </Button>
            </div>
            <form
              className="space-y-4"
              onSubmit={async (e) => {
                e.preventDefault();
                setSmtpError(null);
                setSmtpLoading(true);
                try {
                  const account = await mailApi.connectSmtp({
                    host: smtpHost,
                    port: parseInt(smtpPort, 10) || 587,
                    user: smtpUser,
                    password: smtpPassword,
                    use_tls: smtpUseTls,
                    email_address: smtpEmail || smtpUser || undefined,
                  });
                  queryClient.invalidateQueries({ queryKey: ["mail-accounts"] });
                  setSelectedAccountId(account.id);
                  setShowSmtpDialog(false);
                  setSmtpPassword("");
                } catch (err: unknown) {
                  const msg = err && typeof err === "object" && "response" in err
                    ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
                    : (err as Error)?.message;
                  setSmtpError(msg || "Erreur de connexion SMTP");
                } finally {
                  setSmtpLoading(false);
                }
              }}
            >
              <div className="space-y-2">
                <Label htmlFor="smtp-host">Serveur</Label>
                <Input
                  id="smtp-host"
                  placeholder="smtp.example.com"
                  value={smtpHost}
                  onChange={(e) => setSmtpHost(e.target.value)}
                  required
                />
              </div>
              <div className="flex gap-2">
                <div className="space-y-2 flex-1">
                  <Label htmlFor="smtp-port">Port</Label>
                  <Input
                    id="smtp-port"
                    type="number"
                    placeholder="587"
                    value={smtpPort}
                    onChange={(e) => setSmtpPort(e.target.value)}
                  />
                </div>
                <div className="flex items-end gap-2 pb-2">
                  <label className="flex items-center gap-2 text-sm cursor-pointer">
                    <input
                      type="checkbox"
                      checked={smtpUseTls}
                      onChange={(e) => setSmtpUseTls(e.target.checked)}
                    />
                    TLS
                  </label>
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="smtp-user">Utilisateur (email)</Label>
                <Input
                  id="smtp-user"
                  type="email"
                  placeholder="vous@exemple.com"
                  value={smtpUser}
                  onChange={(e) => setSmtpUser(e.target.value)}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="smtp-password">Mot de passe</Label>
                <Input
                  id="smtp-password"
                  type="password"
                  placeholder="Mot de passe ou mot de passe d'application"
                  value={smtpPassword}
                  onChange={(e) => setSmtpPassword(e.target.value)}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="smtp-email">Email affiché (optionnel)</Label>
                <Input
                  id="smtp-email"
                  type="email"
                  placeholder="Même que l'utilisateur par défaut"
                  value={smtpEmail}
                  onChange={(e) => setSmtpEmail(e.target.value)}
                />
              </div>
              {smtpError && (
                <p className="text-sm text-destructive">{smtpError}</p>
              )}
              <Button type="submit" className="w-full" disabled={smtpLoading}>
                {smtpLoading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                Connecter
              </Button>
            </form>
          </DialogContent>
        </Dialog>

        {/* ═══ Thread list ═══ */}
        {isThreadList && hasAccount && (
          <div className="w-full max-w-3xl lg:max-w-4xl xl:max-w-5xl mx-auto px-4 sm:px-6 py-6">
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

            {/* Tabs */}
            <div className="flex items-center gap-1 border-b border-border mb-4 overflow-x-auto">
              <button
                className={`flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${activeTab === "inbox" ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground"}`}
                onClick={() => setActiveTab("inbox")}
              >
                <Inbox className="h-4 w-4" />
                Boîte de réception ({filteredThreads.length})
              </button>
              <button
                className={`flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${activeTab === "sent" ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground"}`}
                onClick={() => setActiveTab("sent")}
              >
                <Send className="h-4 w-4" />
                Envoyés
              </button>
              <button
                className={`flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${activeTab === "scheduled" ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground"}`}
                onClick={() => setActiveTab("scheduled")}
              >
                <Calendar className="h-4 w-4" />
                Programmés ({scheduledEmails.length})
              </button>
              <button
                className={`flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${activeTab === "drafts" ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground"}`}
                onClick={() => setActiveTab("drafts")}
              >
                <FileEdit className="h-4 w-4" />
                Brouillons ({drafts.length})
              </button>
              <button
                className={`flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${activeTab === "deleted" ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground"}`}
                onClick={() => setActiveTab("deleted")}
              >
                <Trash2 className="h-4 w-4" />
                Supprimés
              </button>
            </div>

            {threadsLoading && (
              <div className="flex items-center justify-center py-16 text-muted-foreground">
                <Loader2 className="h-5 w-5 animate-spin mr-2" />
                Chargement…
              </div>
            )}

            {!threadsLoading && (
              <div className="space-y-2">
                {/* Brouillons tab */}
                {activeTab === "drafts" &&
                  drafts.map((draft) => {
                    const toStr = draft.to_recipients?.[0]?.email || "(pas de destinataire)";
                    const snippet =
                      draft.body_html?.replace(/<[^>]+>/g, "").slice(0, 80) || "";
                    return (
                      <div
                        key={draft.id}
                        className="group flex items-center gap-4 w-full px-4 py-4 rounded-lg bg-card border border-border border-dashed hover:shadow-soft hover:border-primary/30 transition-all text-left"
                      >
                        <button
                          onClick={() => openDraft(draft)}
                          className="flex items-center gap-4 flex-1 min-w-0 text-left"
                        >
                          <div className="w-10 h-10 rounded-full bg-amber-500/10 flex items-center justify-center shrink-0">
                            <Mail className="h-5 w-5 text-amber-600" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-medium text-foreground truncate">
                                à {toStr}
                              </span>
                              <Badge variant="outline" className="text-[10px] shrink-0">
                                Brouillon
                              </Badge>
                            </div>
                            <div className="text-sm text-foreground truncate">
                              {draft.subject || "(sans objet)"}
                            </div>
                            <div className="text-xs text-muted-foreground mt-0.5 truncate">
                              {snippet}
                              {snippet ? "…" : ""}
                            </div>
                          </div>
                          <div className="text-xs text-muted-foreground shrink-0 hidden sm:block">
                            {formatDate(draft.updated_at)}
                          </div>
                          <ChevronRight className="h-4 w-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity shrink-0" />
                        </button>
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
                              onClick={() => deleteDraftMutation.mutate(draft.id)}
                              className="text-destructive focus:text-destructive"
                            >
                              <Trash2 className="h-4 w-4 mr-2" />
                              Supprimer
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </div>
                    );
                  })}
                {/* Inbox tab - Vue contacts (level 1) */}
                {activeTab === "inbox" && viewLevel === "contacts" &&
                  contacts.map((contact) => {
                  const initials = (contact.name || contact.email)
                    .split(" ")
                    .map((n) => n[0])
                    .join("")
                    .slice(0, 2)
                    .toUpperCase();
                  return (
                    <button
                      key={contact.email}
                      onClick={() => handleContactClick(contact)}
                      className="flex items-center gap-4 w-full px-4 py-4 rounded-lg bg-card border border-border hover:shadow-soft hover:border-primary/20 transition-all text-left"
                    >
                      <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center shrink-0 font-display font-semibold text-xs text-foreground">
                        {initials}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-foreground truncate">
                          {contact.name || contact.email}
                        </div>
                        <div className="text-xs text-muted-foreground truncate">
                          {contact.email}
                        </div>
                      </div>
                      {contact.unread_count > 0 && (
                        <Badge variant="default" className="shrink-0">
                          {contact.unread_count}
                        </Badge>
                      )}
                      <div className="text-xs text-muted-foreground shrink-0 hidden sm:block">
                        {formatDate(contact.last_date)}
                      </div>
                      <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />
                    </button>
                  );
                })}

                {/* Inbox tab - Vue threads d'un contact (level 2) */}
                {activeTab === "inbox" && viewLevel === "threads" && selectedContact && (
                  <>
                    <Button variant="ghost" onClick={handleBackToContacts} className="mb-2">
                      ← {selectedContact.name || selectedContact.email}
                    </Button>
                    {threads.map((thread) => (
                      <button
                        key={thread.thread_key}
                        onClick={() => handleThreadClick(thread)}
                        className="flex items-center gap-4 w-full px-4 py-4 rounded-lg bg-card border border-border hover:shadow-soft hover:border-primary/20 transition-all text-left"
                      >
                        {thread.has_unread && (
                          <div className="w-2 h-2 rounded-full bg-primary shrink-0" />
                        )}
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium text-foreground truncate">
                            {thread.subject || "(sans objet)"}
                          </div>
                          <div className="text-xs text-muted-foreground mt-0.5 truncate">
                            {thread.snippet}
                          </div>
                        </div>
                        <div className="text-xs text-muted-foreground shrink-0 hidden sm:block">
                          {formatDate(thread.last_date)}
                        </div>
                        <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />
                      </button>
                    ))}
                  </>
                )}
              </div>
            )}

            {!loadingContacts && !threadsLoading && activeTab === "inbox" && viewLevel === "contacts" && contacts.length === 0 && (
              <div className="text-center py-16 text-sm text-muted-foreground">
                <Mail className="h-10 w-10 mx-auto mb-3 text-muted-foreground/40" />
                Aucun email synchronisé
              </div>
            )}

            {!threadsLoading && activeTab === "inbox" && viewLevel === "threads" && threads.length === 0 && (
              <div className="text-center py-16 text-sm text-muted-foreground">
                <Mail className="h-10 w-10 mx-auto mb-3 text-muted-foreground/40" />
                Aucune conversation avec ce contact
              </div>
            )}

            {!threadsLoading && activeTab === "drafts" && drafts.length === 0 && (
              <div className="text-center py-16 text-sm text-muted-foreground">
                <Mail className="h-10 w-10 mx-auto mb-3 text-muted-foreground/40" />
                Aucun brouillon
              </div>
            )}

            {activeTab === "sent" && (
              <div className="text-center py-16 text-sm text-muted-foreground">
                <Send className="h-10 w-10 mx-auto mb-3 text-muted-foreground/40" />
                <div className="font-medium mb-1">Emails envoyés</div>
                <div className="text-xs">Cette fonctionnalité sera bientôt disponible</div>
              </div>
            )}

            {activeTab === "scheduled" && scheduledEmails.length > 0 && (
              <>
                {scheduledEmails.map((scheduled) => {
                  const toStr = scheduled.to_recipients?.[0]?.email || "(pas de destinataire)";
                  const scheduledDate = new Date(scheduled.scheduled_at);

                  return (
                    <button
                      key={scheduled.id}
                      className="flex items-center gap-4 w-full px-4 py-4 rounded-lg bg-card border border-border hover:shadow-soft hover:border-primary/20 transition-all text-left"
                    >
                      <div className="flex-1 min-w-0" onClick={(e) => e.stopPropagation()}>
                        <div className="flex items-center gap-2 mb-1">
                          <Badge variant="outline" className="text-xs">
                            <Calendar className="h-3 w-3 mr-1" />
                            {scheduledDate.toLocaleString("fr-FR", {
                              day: "2-digit",
                              month: "short",
                              hour: "2-digit",
                              minute: "2-digit",
                            })}
                          </Badge>
                        </div>
                        <div className="text-sm font-medium text-foreground truncate">
                          {scheduled.subject || "(sans objet)"}
                        </div>
                        <div className="text-xs text-muted-foreground mt-0.5 truncate">
                          À : {toStr}
                        </div>
                      </div>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <button
                            className="p-2 hover:bg-accent rounded-md"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <MoreVertical className="h-4 w-4 text-muted-foreground" />
                          </button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem
                            onClick={() => cancelScheduledEmailMutation.mutate(scheduled.id)}
                            className="text-destructive"
                          >
                            <X className="h-4 w-4 mr-2" />
                            Annuler l'envoi
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </button>
                  );
                })}
              </>
            )}

            {activeTab === "scheduled" && scheduledEmails.length === 0 && (
              <div className="text-center py-16 text-sm text-muted-foreground">
                <Calendar className="h-10 w-10 mx-auto mb-3 text-muted-foreground/40" />
                <div className="font-medium mb-1">Aucun email programmé</div>
                <div className="text-xs">Programmez un envoi depuis le composeur</div>
              </div>
            )}

            {activeTab === "deleted" && (
              <div className="text-center py-16 text-sm text-muted-foreground">
                <Trash2 className="h-10 w-10 mx-auto mb-3 text-muted-foreground/40" />
                <div className="font-medium mb-1">Emails supprimés</div>
                <div className="text-xs">Cette fonctionnalité sera bientôt disponible</div>
              </div>
            )}
          </div>
        )}

        {/* ═══ Thread detail ═══ */}
        {isThreadDetail && selectedThread && (
          <div className="w-full max-w-2xl lg:max-w-4xl xl:max-w-5xl mx-auto px-4 sm:px-6 py-6 space-y-4 animate-fade-in">
            {/* Back button to threads list */}
            <Button variant="ghost" onClick={handleBackToThreads} className="mb-2 gap-2">
              ← Retour aux conversations
            </Button>

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
                  <div className="text-sm leading-relaxed text-foreground prose prose-sm dark:prose-invert max-w-none">
                    {msg.body_html ? (
                      <div dangerouslySetInnerHTML={{ __html: msg.body_html }} />
                    ) : (
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {msg.body_text || msg.snippet || ""}
                      </ReactMarkdown>
                    )}
                  </div>

                  {/* Reply/Forward buttons on last message */}
                  {isLast && !replying && (
                    <div className="flex items-center gap-2 flex-wrap mt-4 pt-4 border-t border-border">
                      <Button variant="action" size="sm" className="gap-1.5" onClick={() => { setReplying(true); setReplyBody(""); setSelectedMessage(msg); setSendStatus("idle"); }}>
                        <Reply className="h-3.5 w-3.5" />
                        Répondre
                      </Button>
                      <Button variant="outline" size="sm" className="gap-1.5" onClick={() => handleForwardMessage(msg)}>
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

                {/* Main email body field - single HTML block, copyable (Gmail-ready) */}
                <div className="relative border-b border-border/50">
                  {/* Formatting Toolbar */}
                  <div className="flex items-center gap-1 px-2 py-2 border-b border-border/30 bg-muted/20">
                    <button
                      type="button"
                      onClick={() => formatText('bold', undefined, true)}
                      className="p-2 hover:bg-accent rounded-md transition-colors"
                      title="Gras (Ctrl+B)"
                    >
                      <Bold className="h-4 w-4" />
                    </button>
                    <button
                      type="button"
                      onClick={() => formatText('italic', undefined, true)}
                      className="p-2 hover:bg-accent rounded-md transition-colors"
                      title="Italique (Ctrl+I)"
                    >
                      <Italic className="h-4 w-4" />
                    </button>
                    <div className="w-px h-6 bg-border mx-1" />
                    <button
                      type="button"
                      onClick={() => formatText('insertUnorderedList', undefined, true)}
                      className="p-2 hover:bg-accent rounded-md transition-colors"
                      title="Liste à puces"
                    >
                      <List className="h-4 w-4" />
                    </button>
                    <button
                      type="button"
                      onClick={() => formatText('insertOrderedList', undefined, true)}
                      className="p-2 hover:bg-accent rounded-md transition-colors"
                      title="Liste numérotée"
                    >
                      <ListOrdered className="h-4 w-4" />
                    </button>
                    <div className="w-px h-6 bg-border mx-1" />
                    <button
                      type="button"
                      onClick={() => insertLink(true)}
                      className="p-2 hover:bg-accent rounded-md transition-colors"
                      title="Insérer un lien"
                    >
                      <LinkIcon className="h-4 w-4" />
                    </button>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <button
                          type="button"
                          className="p-2 hover:bg-accent rounded-md transition-colors"
                          title="Taille du texte"
                        >
                          <Type className="h-4 w-4" />
                        </button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="start">
                        <DropdownMenuItem onClick={() => formatText('fontSize', '1', true)}>
                          <span className="text-xs">Petit</span>
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => formatText('fontSize', '3', true)}>
                          <span className="text-sm">Normal</span>
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => formatText('fontSize', '5', true)}>
                          <span className="text-base">Grand</span>
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => formatText('fontSize', '7', true)}>
                          <span className="text-lg">Très grand</span>
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>

                  <div
                    ref={replyBodyRef}
                    contentEditable={!isGenerating}
                    suppressContentEditableWarning
                    className="w-full min-h-[160px] sm:min-h-[200px] p-4 pr-14 text-sm leading-relaxed outline-none text-foreground prose prose-sm dark:prose-invert max-w-none [&_a]:text-primary [&_a]:underline"
                    data-placeholder="Rédigez ou collez votre réponse. L'IA génère du HTML prêt pour Gmail."
                    onInput={(e) => {
                      isUserTypingReply.current = true;
                      setReplyBody(e.currentTarget.innerHTML);
                      setTimeout(() => { isUserTypingReply.current = false; }, 100);
                    }}
                    onFocus={() => { isUserTypingReply.current = true; }}
                    onBlur={() => { isUserTypingReply.current = false; }}
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
          <div className="w-full max-w-2xl lg:max-w-4xl xl:max-w-5xl mx-auto px-4 sm:px-6 py-6 animate-fade-in">
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

              {/* Body - single HTML block, directly copyable (Gmail-ready) */}
              <div className="relative border-b border-border/50">
                {/* Formatting Toolbar */}
                <div className="flex items-center gap-1 px-2 py-2 border-b border-border/30 bg-muted/20">
                  <button
                    type="button"
                    onClick={() => formatText('bold')}
                    className="p-2 hover:bg-accent rounded-md transition-colors"
                    title="Gras (Ctrl+B)"
                  >
                    <Bold className="h-4 w-4" />
                  </button>
                  <button
                    type="button"
                    onClick={() => formatText('italic')}
                    className="p-2 hover:bg-accent rounded-md transition-colors"
                    title="Italique (Ctrl+I)"
                  >
                    <Italic className="h-4 w-4" />
                  </button>
                  <div className="w-px h-6 bg-border mx-1" />
                  <button
                    type="button"
                    onClick={() => formatText('insertUnorderedList')}
                    className="p-2 hover:bg-accent rounded-md transition-colors"
                    title="Liste à puces"
                  >
                    <List className="h-4 w-4" />
                  </button>
                  <button
                    type="button"
                    onClick={() => formatText('insertOrderedList')}
                    className="p-2 hover:bg-accent rounded-md transition-colors"
                    title="Liste numérotée"
                  >
                    <ListOrdered className="h-4 w-4" />
                  </button>
                  <div className="w-px h-6 bg-border mx-1" />
                  <button
                    type="button"
                    onClick={() => insertLink(false)}
                    className="p-2 hover:bg-accent rounded-md transition-colors"
                    title="Insérer un lien"
                  >
                    <LinkIcon className="h-4 w-4" />
                  </button>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <button
                        type="button"
                        className="p-2 hover:bg-accent rounded-md transition-colors"
                        title="Taille du texte"
                      >
                        <Type className="h-4 w-4" />
                      </button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="start">
                      <DropdownMenuItem onClick={() => formatText('fontSize', '1')}>
                        <span className="text-xs">Petit</span>
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => formatText('fontSize', '3')}>
                        <span className="text-sm">Normal</span>
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => formatText('fontSize', '5')}>
                        <span className="text-base">Grand</span>
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => formatText('fontSize', '7')}>
                        <span className="text-lg">Très grand</span>
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>

                <div
                  ref={composeBodyRef}
                  contentEditable={!isGenerating}
                  suppressContentEditableWarning
                  className="w-full min-h-[220px] lg:min-h-[280px] p-4 pr-14 text-sm leading-relaxed outline-none text-foreground prose prose-sm dark:prose-invert max-w-none [&_a]:text-primary [&_a]:underline"
                  data-placeholder="Rédigez ou collez votre email ici. L'IA génère du HTML prêt pour Gmail."
                  onInput={(e) => {
                    isUserTypingCompose.current = true;
                    setComposeBody(e.currentTarget.innerHTML);
                    setTimeout(() => { isUserTypingCompose.current = false; }, 100);
                  }}
                  onFocus={() => { isUserTypingCompose.current = true; }}
                  onBlur={() => { isUserTypingCompose.current = false; }}
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

              {/* Send status */}
              <SendStatusBanner />

              {/* Actions bar */}
              <div className="px-4 py-3 border-t border-border flex items-center gap-2 bg-muted/20 flex-wrap">
                <div className="flex items-center gap-0">
                  <Button
                    variant="premium"
                    size="sm"
                    className="gap-1.5 rounded-r-none"
                    disabled={!extractRecipientEmail(composeTo) || !composeBody.trim() || isGenerating || sendStatus === "sending"}
                    onClick={handleSendCompose}
                  >
                    {sendStatus === "sending" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
                    Envoyer
                  </Button>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="premium"
                        size="sm"
                        className="px-2 rounded-l-none border-l border-white/20"
                        disabled={!extractRecipientEmail(composeTo) || !composeBody.trim() || isGenerating || sendStatus === "sending"}
                      >
                        <ChevronRight className="h-3.5 w-3.5 rotate-90" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => setShowSchedulePicker(true)}>
                        <Calendar className="h-4 w-4 mr-2" />
                        Programmer l'envoi
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={
                    (!composeBody.trim() && !composeTo.trim() && !composeSubject.trim()) ||
                    isGenerating ||
                    !selectedAccountId ||
                    saveDraftMutation.isPending
                  }
                  onClick={() => {
                    const recipientEmail = extractRecipientEmail(composeTo);
                    const toRecipients = recipientEmail
                      ? [{ name: "", email: recipientEmail }]
                      : [];
                    saveDraftMutation.mutate({
                      to_recipients: toRecipients,
                      subject: composeSubject,
                      body_html: composeBody,
                      instruction: composeInstruction,
                      draft_id: currentDraftId || undefined,
                    });
                  }}
                >
                  {saveDraftMutation.isPending ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    "Brouillon"
                  )}
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
                <Button variant="ghost" size="sm" onClick={handleLeaveCompose}>
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
      {/* End of flex-1 overflow-auto */}
      </div>
      {/* End of main content flex-col */}

      {/* AI Assistant Sidebar - Desktop (lg+) */}
      {(composing || replying) && (
        <EmailAssistantSidebar
          className="w-80 hidden lg:flex border-l border-border"
          onDraftUpdate={handleDraftUpdate}
        />
      )}

      {/* Mobile Assistant Button + Sheet */}
      {(composing || replying) && (
        <div className="lg:hidden">
          <Sheet open={isMobileSidebarOpen} onOpenChange={setIsMobileSidebarOpen}>
            <SheetTrigger asChild>
              <Button
                size="icon"
                variant="premium"
                className="fixed bottom-6 right-6 h-14 w-14 rounded-full shadow-xl z-50"
              >
                <MessageSquare className="h-6 w-6" />
              </Button>
            </SheetTrigger>
            <SheetContent side="right" className="w-full sm:w-96 p-0">
              <EmailAssistantSidebar
                className="h-full flex"
                onDraftUpdate={handleDraftUpdate}
              />
            </SheetContent>
          </Sheet>
        </div>
      )}
    </div>
    {/* End of flex h-full container */}

    <AddToFolderDialog
      open={!!addToFolderTarget}
      onOpenChange={(open) => !open && setAddToFolderTarget(null)}
      itemType="email_thread"
      itemId={addToFolderTarget?.threadKey ?? ""}
      itemTitle={addToFolderTarget?.subject}
      onSuccess={() => queryClient.invalidateQueries({ queryKey: ["folders"] })}
    />

    {/* Schedule Email Dialog */}
    <Dialog open={showSchedulePicker} onOpenChange={setShowSchedulePicker}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Programmer l'envoi</DialogTitle>
          <DialogDescription>
            Choisissez quand vous souhaitez envoyer cet email
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="schedule-datetime">Date et heure</Label>
            <Input
              id="schedule-datetime"
              type="datetime-local"
              value={scheduleDate || ""}
              onChange={(e) => setScheduleDate(e.target.value)}
              min={new Date().toISOString().slice(0, 16)}
            />
          </div>
          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              onClick={() => {
                setShowSchedulePicker(false);
                setScheduleDate(null);
              }}
            >
              Annuler
            </Button>
            <Button
              variant="premium"
              disabled={!scheduleDate || !selectedAccountId || scheduleEmailMutation.isPending}
              onClick={() => {
                if (!scheduleDate || !selectedAccountId) return;

                const recipientEmail = extractRecipientEmail(composeTo);
                if (!recipientEmail || !composeBody.trim()) {
                  toast({
                    variant: "destructive",
                    title: "Erreur",
                    description: "Veuillez remplir le destinataire et le corps de l'email",
                  });
                  return;
                }

                scheduleEmailMutation.mutate({
                  mail_account_id: selectedAccountId,
                  mode: "new",
                  to_recipients: [{ name: "", email: recipientEmail }],
                  subject: composeSubject || "(sans objet)",
                  body_html: composeBody,
                  scheduled_at: new Date(scheduleDate).toISOString(),
                });

                setShowSchedulePicker(false);
                setScheduleDate(null);
              }}
            >
              {scheduleEmailMutation.isPending ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Calendar className="h-4 w-4 mr-2" />
              )}
              Programmer
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>

    {/* Insert Link Dialog */}
    <Dialog open={showLinkDialog} onOpenChange={setShowLinkDialog}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Insérer un lien</DialogTitle>
          <DialogDescription>
            Ajoutez un lien hypertexte à votre texte
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="link-text">Texte du lien</Label>
            <Input
              id="link-text"
              placeholder="Texte à afficher"
              value={linkText}
              onChange={(e) => setLinkText(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="link-url">URL</Label>
            <Input
              id="link-url"
              type="url"
              placeholder="https://exemple.com"
              value={linkUrl}
              onChange={(e) => setLinkUrl(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && linkUrl) {
                  applyLink();
                }
              }}
            />
          </div>
          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              onClick={() => {
                setShowLinkDialog(false);
                setLinkUrl("");
                setLinkText("");
              }}
            >
              Annuler
            </Button>
            <Button
              variant="premium"
              disabled={!linkUrl}
              onClick={applyLink}
            >
              <LinkIcon className="h-4 w-4 mr-2" />
              Insérer
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  </>
  );
};

/**
 * EmailComposer with AI Assistant Provider
 */
export const EmailComposer = () => {
  return (
    <EmailAssistantProvider>
      <EmailComposerContent />
    </EmailAssistantProvider>
  );
};

export default EmailComposer;
