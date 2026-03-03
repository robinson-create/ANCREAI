import { useState, useRef, useEffect, useCallback, useMemo } from "react"
import { useParams, useNavigate } from "react-router-dom"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  User,
  Loader2,
  ArrowLeft,
  Plus,
  FileText,
  ChevronDown,
  ChevronUp,
  Send,
  Mic,
  Square,
  Copy,
  Check,
  Anchor,
  Pencil,
  X,
  Trash2,
  Upload,
  MessageSquare,
  Presentation,
  Mail,
  Search,
  MoreVertical,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { dossiersApi } from "@/api/dossiers"
import type {
  Block,
  Citation,
  Message,
  DossierDocument,
} from "@/types"
import { cn } from "@/lib/utils"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { BlockRenderer } from "@/components/blocks/BlockRenderer"
import { createDictationAdapter } from "@/lib/dictation"
import { useToast } from "@/hooks/use-toast"

import {
  AssistantRuntimeProvider,
  useExternalStoreRuntime,
  useComposerRuntime,
  useComposer,
  ComposerPrimitive,
} from "@assistant-ui/react"
import type { ThreadMessageLike, AppendMessage } from "@assistant-ui/react"

// ─── Types ───────────────────────────────────────────────────

interface LocalMessage extends Message {
  isStreaming?: boolean
}

interface UnifiedItem {
  id: string
  type: "conversation" | "document" | "presentation" | "email" | "upload"
  title: string
  date: string
  status?: string
  messageCount?: number
  fileSize?: number
  linkedItemId?: string // for DossierItem deletion
  sourceItemId?: string // original item_id to navigate to
}

const ELEMENT_TABS = [
  { value: "all", label: "Tout" },
  { value: "conversation", label: "Conversations" },
  { value: "upload", label: "Documents" },
  { value: "document", label: "Générés" },
  { value: "presentation", label: "Présentations" },
  { value: "email", label: "Emails" },
] as const

type ElementTab = (typeof ELEMENT_TABS)[number]["value"]

// ─── Helpers ─────────────────────────────────────────────────

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("fr-FR", {
    day: "numeric",
    month: "long",
    year: "numeric",
  })
}

function itemTypeIcon(type: UnifiedItem["type"]) {
  switch (type) {
    case "conversation":
      return <MessageSquare className="h-4 w-4 text-violet-500" />
    case "document":
      return <FileText className="h-4 w-4 text-blue-500" />
    case "upload":
      return <Upload className="h-4 w-4 text-sky-500" />
    case "presentation":
      return <Presentation className="h-4 w-4 text-orange-500" />
    case "email":
      return <Mail className="h-4 w-4 text-emerald-500" />
  }
}

function itemTypeBg(type: UnifiedItem["type"]) {
  switch (type) {
    case "conversation":
      return "bg-violet-500/10"
    case "document":
      return "bg-blue-500/10"
    case "upload":
      return "bg-sky-500/10"
    case "presentation":
      return "bg-orange-500/10"
    case "email":
      return "bg-emerald-500/10"
  }
}

function itemTypeBadge(type: UnifiedItem["type"]) {
  switch (type) {
    case "conversation":
      return "CONVERSATION"
    case "document":
      return "DOCUMENT"
    case "upload":
      return "UPLOAD"
    case "presentation":
      return "PRÉSENTATION"
    case "email":
      return "EMAIL"
  }
}

function itemTypeBadgeClass(type: UnifiedItem["type"]) {
  switch (type) {
    case "conversation":
      return "bg-violet-100 text-violet-700 dark:bg-violet-500/20 dark:text-violet-300"
    case "document":
      return "bg-blue-100 text-blue-700 dark:bg-blue-500/20 dark:text-blue-300"
    case "upload":
      return "bg-sky-100 text-sky-700 dark:bg-sky-500/20 dark:text-sky-300"
    case "presentation":
      return "bg-orange-100 text-orange-700 dark:bg-orange-500/20 dark:text-orange-300"
    case "email":
      return "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300"
  }
}

function computeSyncStatus(
  docs: DossierDocument[]
): "synced" | "processing" | "error" | null {
  if (docs.length === 0) return null
  if (docs.some((d) => d.status === "processing" || d.status === "pending"))
    return "processing"
  if (docs.some((d) => d.status === "failed")) return "error"
  if (docs.every((d) => d.status === "ready")) return "synced"
  return null
}

// ─── DictationToggle ────────────────────────────────────────

function DictationToggle() {
  const composerRuntime = useComposerRuntime()
  const isDictating = useComposer((s) => s.dictation != null)

  const handleClick = () => {
    if (isDictating) {
      composerRuntime.stopDictation()
    } else {
      composerRuntime.startDictation()
    }
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      className={cn(
        "inline-flex h-8 w-8 items-center justify-center rounded-md transition-colors",
        isDictating
          ? "bg-destructive text-destructive-foreground hover:bg-destructive/90"
          : "text-muted-foreground hover:bg-muted hover:text-foreground"
      )}
    >
      {isDictating ? (
        <Square className="h-3.5 w-3.5 fill-current" />
      ) : (
        <Mic className="h-4 w-4" />
      )}
    </button>
  )
}

// ─── Main Page ──────────────────────────────────────────────

export function DossierPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { toast } = useToast()

  // ── View state ──
  const [view, setView] = useState<"dashboard" | "chat">("dashboard")
  const [dashboardInput, setDashboardInput] = useState("")
  const [activeTab, setActiveTab] = useState<ElementTab>("all")
  const [itemSearch, setItemSearch] = useState("")

  // ── Chat state ──
  const [messages, setMessages] = useState<LocalMessage[]>([])
  const [isRunning, setIsRunning] = useState(false)
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [expandedCitations, setExpandedCitations] = useState<Set<string>>(
    new Set()
  )
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null)
  const [editingMessageId, setEditingMessageId] = useState<string | null>(null)
  const [editContent, setEditContent] = useState("")

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const abortFnRef = useRef<(() => void) | null>(null)
  const isNewConversationRef = useRef(false)
  const conversationIdRef = useRef(conversationId)
  conversationIdRef.current = conversationId
  const fileInputRef = useRef<HTMLInputElement>(null)

  // ── Queries ──

  const { data: dossier, isLoading: isLoadingDossier } = useQuery({
    queryKey: ["dossier", id],
    queryFn: () => dossiersApi.get(id!),
    enabled: !!id,
  })

  const { data: documents = [] } = useQuery({
    queryKey: ["dossier-documents", id],
    queryFn: () => dossiersApi.listDocuments(id!),
    enabled: !!id,
    refetchInterval: (query) => {
      const docs = query.state.data
      if (
        docs?.some(
          (d) => d.status === "processing" || d.status === "pending"
        )
      ) {
        return 5000
      }
      return false
    },
  })

  const { data: conversations = [], refetch: refetchConversations } = useQuery({
    queryKey: ["dossier-conversations", id],
    queryFn: () => dossiersApi.listConversations(id!),
    enabled: !!id,
  })

  const { data: linkedItems = [] } = useQuery({
    queryKey: ["dossier-items", id],
    queryFn: () => dossiersApi.listItems(id!),
    enabled: !!id,
  })

  // ── Mutations ──

  const uploadMutation = useMutation({
    mutationFn: (file: File) => dossiersApi.uploadDocument(id!, file),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["dossier-documents", id] })
      queryClient.invalidateQueries({ queryKey: ["dossier", id] })
      toast({ title: "Document importé", description: data.filename })
    },
    onError: () => {
      toast({
        variant: "destructive",
        title: "Erreur",
        description: "Impossible d'importer le document.",
      })
    },
  })

  const deleteDocMutation = useMutation({
    mutationFn: (docId: string) => dossiersApi.deleteDocument(id!, docId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["dossier-documents", id] })
      queryClient.invalidateQueries({ queryKey: ["dossier", id] })
      toast({ title: "Document supprimé" })
    },
  })

  const removeItemMutation = useMutation({
    mutationFn: (itemId: string) => dossiersApi.removeItem(id!, itemId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["dossier-items", id] })
      toast({ title: "Élément retiré" })
    },
  })

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files) return
    Array.from(files).forEach((file) => uploadMutation.mutate(file))
    e.target.value = ""
  }

  // ── Unified items ──

  const unifiedItems = useMemo(() => {
    const items: UnifiedItem[] = []
    documents.forEach((doc) => {
      items.push({
        id: doc.id,
        type: "upload",
        title: doc.filename,
        date: doc.created_at,
        status: doc.status,
        fileSize: doc.file_size,
      })
    })
    conversations.forEach((conv) => {
      items.push({
        id: conv.id,
        type: "conversation",
        title: conv.title,
        date: conv.updated_at,
        messageCount: conv.message_count,
      })
    })
    linkedItems.forEach((item) => {
      const normalizedType = item.item_type === "email_thread" ? "email" : item.item_type
      items.push({
        id: `linked-${item.id}`,
        type: normalizedType as UnifiedItem["type"],
        title: item.title,
        date: item.added_at,
        linkedItemId: item.id,
        sourceItemId: item.item_id,
      })
    })
    items.sort(
      (a, b) => new Date(b.date).getTime() - new Date(a.date).getTime()
    )
    return items
  }, [documents, conversations, linkedItems])

  const filteredItems = useMemo(() => {
    let filtered = unifiedItems
    if (activeTab !== "all") {
      filtered = filtered.filter((i) => i.type === activeTab)
    }
    if (itemSearch.trim()) {
      const q = itemSearch.toLowerCase()
      filtered = filtered.filter((i) => i.title.toLowerCase().includes(q))
    }
    return filtered
  }, [unifiedItems, activeTab, itemSearch])

  const recentItems = useMemo(() => unifiedItems.slice(0, 6), [unifiedItems])

  // ── Scroll ──

  const scrollToBottom = useCallback(() => {
    const el = scrollContainerRef.current
    if (el) {
      el.scrollTop = el.scrollHeight
    }
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages, scrollToBottom])

  // ── Streaming chat ──

  const startStreaming = useCallback(
    (text: string, existingConversationId?: string | null) => {
      if (!id) return

      isNewConversationRef.current = !existingConversationId

      const userMsg: LocalMessage = {
        id: Date.now().toString(),
        role: "user",
        content: text,
        created_at: new Date().toISOString(),
      }

      const assistantMessageId = (Date.now() + 1).toString()
      const assistantMsg: LocalMessage = {
        id: assistantMessageId,
        role: "assistant",
        content: "",
        isStreaming: true,
        created_at: new Date().toISOString(),
      }

      setMessages((prev) => [...prev, userMsg, assistantMsg])
      setIsRunning(true)

      abortFnRef.current = dossiersApi.stream(
        id,
        {
          message: text,
          conversation_id: existingConversationId || undefined,
        },
        (token) => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId
                ? { ...msg, content: msg.content + token }
                : msg
            )
          )
        },
        (response) => {
          setConversationId(response.conversationId)
          conversationIdRef.current = response.conversationId
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId
                ? {
                    ...msg,
                    isStreaming: false,
                    citations: response.citations,
                  }
                : msg
            )
          )
          setIsRunning(false)
          refetchConversations()
        },
        (error) => {
          console.error("Dossier chat error:", error)
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId
                ? {
                    ...msg,
                    content:
                      "Désolé, une erreur s'est produite. Veuillez réessayer.",
                    isStreaming: false,
                  }
                : msg
            )
          )
          setIsRunning(false)
        },
        (newConversationId) => {
          if (isNewConversationRef.current) {
            setConversationId(newConversationId)
            conversationIdRef.current = newConversationId
            refetchConversations()
          }
        },
        (block: Block) => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId
                ? { ...msg, blocks: [...(msg.blocks || []), block] }
                : msg
            )
          )
        }
      )
    },
    [id, refetchConversations]
  )

  const onNew = useCallback(
    async (message: AppendMessage) => {
      const textPart = message.content.find((p) => p.type === "text")
      if (!textPart || textPart.type !== "text") return
      startStreaming(textPart.text, conversationIdRef.current)
    },
    [startStreaming]
  )

  const onCancel = useCallback(async () => {
    if (abortFnRef.current) {
      abortFnRef.current()
      abortFnRef.current = null
    }
    setMessages((prev) =>
      prev.map((msg) =>
        msg.isStreaming ? { ...msg, isStreaming: false } : msg
      )
    )
    setIsRunning(false)
  }, [])

  const convertMessage = useCallback(
    (message: LocalMessage): ThreadMessageLike => ({
      role: message.role,
      content: [{ type: "text", text: message.content }],
      id: message.id,
      createdAt: new Date(message.created_at),
      ...(message.role === "assistant" && {
        status: message.isStreaming
          ? { type: "running" as const }
          : { type: "complete" as const, reason: "stop" as const },
      }),
    }),
    []
  )

  const dictationAdapter = useMemo(
    () => createDictationAdapter({ language: "fr" }),
    []
  )

  const runtime = useExternalStoreRuntime({
    messages,
    isRunning,
    onNew,
    onCancel,
    convertMessage,
    adapters: {
      dictation: dictationAdapter,
    },
  })

  // ── Dashboard actions ──

  const sendFromDashboard = useCallback(
    (text: string) => {
      if (!text.trim()) return
      setMessages([])
      setConversationId(null)
      conversationIdRef.current = null
      setDashboardInput("")
      setView("chat")
      startStreaming(text.trim())
    },
    [startStreaming]
  )

  const openConversation = useCallback(
    async (convId: string) => {
      if (!id) return
      try {
        const history = await dossiersApi.getConversation(id, convId)
        setMessages(
          history.map((msg) => ({
            id: msg.id,
            role: msg.role as "user" | "assistant" | "system",
            content: msg.content,
            citations: msg.citations,
            blocks: msg.blocks,
            created_at: msg.created_at,
          }))
        )
        setConversationId(convId)
        conversationIdRef.current = convId
        setView("chat")
      } catch (error) {
        console.error("Failed to load conversation:", error)
      }
    },
    [id]
  )

  const handleNewConversation = useCallback(() => {
    setMessages([])
    setConversationId(null)
    conversationIdRef.current = null
    if (abortFnRef.current) {
      abortFnRef.current()
    }
    setView("chat")
  }, [])

  const handleBackToDashboard = useCallback(() => {
    if (abortFnRef.current) {
      abortFnRef.current()
    }
    setIsRunning(false)
    setView("dashboard")
  }, [])

  // ── Message helpers ──

  const toggleCitations = (messageId: string) => {
    setExpandedCitations((prev) => {
      const next = new Set(prev)
      if (next.has(messageId)) {
        next.delete(messageId)
      } else {
        next.add(messageId)
      }
      return next
    })
  }

  const handleCopy = useCallback(
    (messageId: string, content: string) => {
      navigator.clipboard.writeText(content)
      setCopiedMessageId(messageId)
      setTimeout(() => setCopiedMessageId(null), 2000)
    },
    []
  )

  const lastUserMessageId = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      const msg = messages[i]
      if (msg?.role === "user") return msg.id
    }
    return null
  }, [messages])

  const handleStartEdit = useCallback(
    (messageId: string, content: string) => {
      setEditingMessageId(messageId)
      setEditContent(content)
    },
    []
  )

  const handleCancelEdit = useCallback(() => {
    setEditingMessageId(null)
    setEditContent("")
  }, [])

  const handleConfirmEdit = useCallback(() => {
    if (!editingMessageId || !editContent.trim() || !id) return

    const msgIndex = messages.findIndex((m) => m.id === editingMessageId)
    if (msgIndex === -1) return

    const kept = messages.slice(0, msgIndex)
    setMessages(kept)
    setEditingMessageId(null)
    setEditContent("")

    startStreaming(editContent.trim(), conversationIdRef.current)
  }, [editingMessageId, editContent, id, messages, startStreaming])

  // ── Item click handler ──

  const handleItemClick = useCallback(
    (item: UnifiedItem) => {
      if (item.type === "conversation") {
        openConversation(item.id)
      } else if (item.linkedItemId && item.sourceItemId) {
        // Linked items — navigate to their source
        const srcId = item.sourceItemId
        if (item.type === "presentation") navigate(`/app/presentations/${srcId}`)
        else if (item.type === "document") navigate(`/app/documents/${srcId}`)
        else if (item.type === "email") navigate(`/app/email?thread=${srcId}`)
        else if (item.type === "upload") navigate(`/app/uploads/${srcId}`)
      }
    },
    [openConversation, navigate]
  )

  const handleItemDelete = useCallback(
    (item: UnifiedItem) => {
      if (item.linkedItemId) {
        removeItemMutation.mutate(item.linkedItemId)
      } else if (item.type === "upload") {
        deleteDocMutation.mutate(item.id)
      }
    },
    [deleteDocMutation, removeItemMutation]
  )

  // ── Loading / error states ──

  if (isLoadingDossier) {
    return (
      <div className="flex h-[calc(100vh-4rem)] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  if (!dossier) {
    return (
      <div className="flex h-[calc(100vh-4rem)] flex-col items-center justify-center gap-4">
        <p className="text-muted-foreground">Dossier non trouvé</p>
        <Button variant="outline" onClick={() => navigate("/app/folders")}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Retour aux dossiers
        </Button>
      </div>
    )
  }

  const syncStatus = computeSyncStatus(documents)

  // ═══════════════════════════════════════════════════════════
  // CHAT VIEW
  // ═══════════════════════════════════════════════════════════

  if (view === "chat") {
    return (
      <AssistantRuntimeProvider runtime={runtime}>
        <div className="flex flex-1 flex-col h-[calc(100vh-4rem)]">
          {/* Header */}
          <div className="flex items-center justify-between border-b px-4 py-3">
            <div className="flex items-center gap-3">
              <Button
                variant="ghost"
                size="icon"
                onClick={handleBackToDashboard}
              >
                <ArrowLeft className="h-4 w-4" />
              </Button>
              <div className="flex items-center gap-2">
                {dossier.color && (
                  <div
                    className="h-3 w-3 rounded-full"
                    style={{ backgroundColor: dossier.color }}
                  />
                )}
                <p className="font-medium font-body">{dossier.name}</p>
              </div>
              {syncStatus === "synced" && (
                <Badge variant="secondary" className="gap-1.5 text-xs">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                  Synchronisé
                </Badge>
              )}
              {syncStatus === "processing" && (
                <Badge variant="secondary" className="gap-1.5 text-xs">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  Traitement
                </Badge>
              )}
              {syncStatus === "error" && (
                <Badge variant="destructive" className="gap-1.5 text-xs">
                  Erreur
                </Badge>
              )}
            </div>
          </div>

          {/* Messages */}
          <div
            ref={scrollContainerRef}
            className="flex-1 overflow-y-auto p-4"
          >
            <div className="mx-auto max-w-3xl space-y-6">
              {messages.length === 0 && (
                <div className="flex flex-col items-center justify-center py-16 text-center">
                  <FileText className="h-12 w-12 text-muted-foreground" />
                  <h3 className="mt-4 text-lg font-semibold font-heading">
                    Discutez avec votre dossier
                  </h3>
                  <p className="mt-2 max-w-sm text-muted-foreground font-body">
                    Posez des questions sur les documents de{" "}
                    <strong>{dossier.name}</strong>.
                    {documents.length === 0 &&
                      " Commencez par importer un document."}
                  </p>
                </div>
              )}

              {messages.map((message) => (
                <div
                  key={message.id}
                  className={cn(
                    "group flex gap-3",
                    message.role === "user" ? "flex-row-reverse" : "flex-row"
                  )}
                >
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
                  <div
                    className={cn(
                      "max-w-[80%] min-w-0 space-y-2",
                      message.role === "user" ? "text-right" : ""
                    )}
                  >
                    <div
                      className={cn(
                        message.role === "user"
                          ? "inline-block rounded-2xl bg-primary text-primary-foreground px-4 py-2.5 text-sm whitespace-pre-wrap text-left"
                          : "prose prose-sm max-w-none break-words dark:prose-invert"
                      )}
                    >
                      {message.role === "assistant" ? (
                        <>
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {message.content}
                          </ReactMarkdown>
                          {message.isStreaming && !message.content && (
                            <span className="inline-block h-4 w-1.5 animate-pulse rounded-sm bg-primary" />
                          )}
                        </>
                      ) : editingMessageId === message.id ? (
                        <div className="space-y-2">
                          <textarea
                            value={editContent}
                            onChange={(e) => setEditContent(e.target.value)}
                            className="w-full rounded-md border bg-background p-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                            rows={3}
                            autoFocus
                            onKeyDown={(e) => {
                              if (e.key === "Enter" && !e.shiftKey) {
                                e.preventDefault()
                                handleConfirmEdit()
                              }
                              if (e.key === "Escape") {
                                handleCancelEdit()
                              }
                            }}
                          />
                          <div className="flex gap-2">
                            <Button
                              size="sm"
                              onClick={handleConfirmEdit}
                              disabled={!editContent.trim()}
                            >
                              <Send className="mr-1 h-3 w-3" />
                              Renvoyer
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={handleCancelEdit}
                            >
                              <X className="mr-1 h-3 w-3" />
                              Annuler
                            </Button>
                          </div>
                        </div>
                      ) : (
                        <span>{message.content}</span>
                      )}
                    </div>

                    {/* Blocks */}
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
                          {message.citations.length} source(s)
                        </Button>
                        {expandedCitations.has(message.id) && (
                          <div className="mt-2 space-y-2">
                            {message.citations.map(
                              (citation: Citation, idx: number) => (
                                <div
                                  key={idx}
                                  className="rounded-md border bg-muted/50 p-3 text-sm"
                                >
                                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                    <FileText className="h-3 w-3" />
                                    {citation.document_filename}
                                    {citation.page_number && (
                                      <span>
                                        - Page {citation.page_number}
                                      </span>
                                    )}
                                  </div>
                                  <p className="mt-1 text-xs italic">
                                    "{citation.excerpt}"
                                  </p>
                                </div>
                              )
                            )}
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Action buttons */}
                  {editingMessageId !== message.id && (
                    <div className="flex shrink-0 items-start gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                      <button
                        type="button"
                        onClick={() =>
                          handleCopy(message.id, message.content)
                        }
                        className="inline-flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
                        title="Copier"
                      >
                        {copiedMessageId === message.id ? (
                          <Check className="h-3.5 w-3.5 text-green-500" />
                        ) : (
                          <Copy className="h-3.5 w-3.5" />
                        )}
                      </button>
                      {message.role === "user" &&
                        message.id === lastUserMessageId &&
                        !isRunning && (
                          <button
                            type="button"
                            onClick={() =>
                              handleStartEdit(message.id, message.content)
                            }
                            className="inline-flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
                            title="Modifier et renvoyer"
                          >
                            <Pencil className="h-3.5 w-3.5" />
                          </button>
                        )}
                    </div>
                  )}
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
          </div>

          {/* Composer */}
          <div className="border-t p-4">
            <div className="mx-auto max-w-3xl">
              <ComposerPrimitive.Root className="relative flex items-end rounded-xl border bg-card shadow-sm">
                <ComposerPrimitive.Input
                  placeholder="Posez une question sur vos documents..."
                  className="min-h-[60px] flex-1 resize-none border-0 bg-transparent p-3 pr-20 text-sm focus:outline-none focus:ring-0 font-body"
                  autoFocus
                />
                <div className="absolute bottom-2 right-2 flex items-center gap-1">
                  <DictationToggle />
                  {isRunning ? (
                    <button
                      type="button"
                      onClick={onCancel}
                      className="inline-flex h-8 w-8 items-center justify-center rounded-md bg-destructive text-destructive-foreground hover:bg-destructive/90"
                      title="Arrêter la génération"
                    >
                      <Square className="h-3.5 w-3.5 fill-current" />
                    </button>
                  ) : (
                    <ComposerPrimitive.Send className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-foreground text-background hover:bg-foreground/90 disabled:opacity-50">
                      <Send className="h-4 w-4" />
                    </ComposerPrimitive.Send>
                  )}
                </div>
              </ComposerPrimitive.Root>
            </div>
          </div>
        </div>
      </AssistantRuntimeProvider>
    )
  }

  // ═══════════════════════════════════════════════════════════
  // DASHBOARD VIEW
  // ═══════════════════════════════════════════════════════════

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] overflow-auto">
      <input
        ref={fileInputRef}
        type="file"
        className="hidden"
        multiple
        accept=".pdf,.docx,.doc,.xlsx,.xls,.pptx,.ppt,.txt,.csv,.md"
        onChange={handleFileSelect}
      />

      <div className="max-w-4xl w-full mx-auto px-6 pt-8 pb-6 space-y-8">
        {/* ── Header ── */}
        <div>
          <div className="flex items-center gap-3 mb-1">
            <button
              onClick={() => navigate("/app/folders")}
              className="h-8 w-8 rounded-full flex items-center justify-center hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
            >
              <ArrowLeft className="h-4 w-4" />
            </button>
            <div className="flex items-center gap-2">
              {dossier.color && (
                <div
                  className="h-3 w-3 rounded-full"
                  style={{ backgroundColor: dossier.color }}
                />
              )}
              {syncStatus === "processing" && (
                <Badge variant="secondary" className="gap-1.5 text-[10px] px-2 py-0">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  Traitement
                </Badge>
              )}
              {syncStatus === "error" && (
                <Badge variant="destructive" className="gap-1.5 text-[10px] px-2 py-0">
                  Erreur
                </Badge>
              )}
            </div>
          </div>
          <h1 className="font-heading text-3xl md:text-4xl font-bold text-foreground tracking-tight uppercase">
            {dossier.name}
          </h1>
          <p className="text-sm text-muted-foreground font-body mt-1">
            Posez une question ou parcourez vos éléments
          </p>
        </div>

        {/* ── Composer input ── */}
        <div className="relative">
          <textarea
            value={dashboardInput}
            onChange={(e) => setDashboardInput(e.target.value)}
            placeholder="Posez une question sur vos documents..."
            rows={3}
            className="w-full resize-none rounded-xl border border-border bg-card p-4 pr-14 text-sm font-body placeholder:text-muted-foreground/60 focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/40 transition-all shadow-sm"
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault()
                sendFromDashboard(dashboardInput)
              }
            }}
          />
          <button
            onClick={() => sendFromDashboard(dashboardInput)}
            disabled={!dashboardInput.trim()}
            className="absolute bottom-3 right-3 h-9 w-9 rounded-full bg-foreground text-background flex items-center justify-center hover:bg-foreground/90 disabled:opacity-30 transition-all"
          >
            <Send className="h-4 w-4" />
          </button>
        </div>

        {/* ── Recent files ── */}
        {recentItems.length > 0 && (
          <div>
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-2">
                <h2 className="text-base font-semibold text-foreground font-heading">
                  Fichiers récents
                </h2>
                <span className="text-xs text-muted-foreground bg-muted px-1.5 py-0.5 rounded-md font-body">
                  {unifiedItems.length}
                </span>
              </div>
            </div>
            <p className="text-xs text-muted-foreground font-body mb-3">
              Continuez là où vous en étiez.
            </p>

            <div className="flex gap-3 overflow-x-auto pb-2 -mx-1 px-1">
              {recentItems.map((item) => (
                <button
                  key={`${item.type}-${item.id}`}
                  onClick={() => handleItemClick(item)}
                  className="flex flex-col shrink-0 w-[140px] rounded-xl border border-border bg-card hover:shadow-md hover:border-primary/20 transition-all overflow-hidden cursor-pointer"
                >
                  <div
                    className={cn(
                      "h-20 flex items-center justify-center",
                      itemTypeBg(item.type)
                    )}
                  >
                    {item.type === "conversation" ? (
                      <MessageSquare className="h-8 w-8 text-violet-400" />
                    ) : item.type === "upload" ? (
                      <Upload className="h-8 w-8 text-sky-400" />
                    ) : item.type === "document" ? (
                      <FileText className="h-8 w-8 text-blue-400" />
                    ) : item.type === "presentation" ? (
                      <Presentation className="h-8 w-8 text-orange-400" />
                    ) : (
                      <Mail className="h-8 w-8 text-emerald-400" />
                    )}
                  </div>
                  <div className="p-2.5">
                    <p className="text-xs font-medium text-foreground truncate font-body">
                      {item.title}
                    </p>
                    <p className="text-[10px] text-muted-foreground font-body mt-0.5">
                      {formatDate(item.date)}
                    </p>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* ── Tabs ── */}
        <div className="flex items-center gap-1.5 flex-wrap">
          {ELEMENT_TABS.map((tab) => (
            <button
              key={tab.value}
              onClick={() => setActiveTab(tab.value)}
              className={cn(
                "px-4 py-1.5 rounded-full text-xs font-medium font-body transition-all border",
                activeTab === tab.value
                  ? "bg-foreground text-background border-foreground"
                  : "bg-card text-foreground border-border hover:bg-muted"
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* ── Items list ── */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-foreground font-heading">
              Éléments du dossier
            </h2>
            <div className="flex items-center gap-2">
              <div className="relative">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                <input
                  value={itemSearch}
                  onChange={(e) => setItemSearch(e.target.value)}
                  placeholder="Search"
                  className="h-8 w-40 pl-8 pr-3 text-xs font-body bg-card border border-border rounded-lg outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/40 text-foreground placeholder:text-muted-foreground/60 transition-all"
                />
              </div>

              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" size="sm" className="gap-1.5 text-xs h-8">
                    <Plus className="h-3.5 w-3.5" />
                    Ajouter
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem
                    onClick={() => fileInputRef.current?.click()}
                  >
                    <Upload className="mr-2 h-4 w-4" />
                    Importer un document
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={handleNewConversation}>
                    <MessageSquare className="mr-2 h-4 w-4" />
                    Nouvelle conversation
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>

          {filteredItems.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-sm text-muted-foreground font-body">
                {itemSearch || activeTab !== "all"
                  ? "Aucun élément trouvé."
                  : "Ce dossier est vide. Commencez par importer un document."}
              </p>
              {!itemSearch && activeTab === "all" && (
                <Button
                  variant="outline"
                  size="sm"
                  className="mt-3 gap-2"
                  onClick={() => fileInputRef.current?.click()}
                >
                  <Upload className="h-4 w-4" />
                  Importer un document
                </Button>
              )}
            </div>
          ) : (
            <div className="border border-border rounded-xl overflow-hidden divide-y divide-border">
              {filteredItems.map((item) => (
                <div
                  key={`${item.type}-${item.id}`}
                  className="group flex items-center gap-3 px-4 py-3 bg-card hover:bg-muted/30 transition-colors cursor-pointer"
                  onClick={() => handleItemClick(item)}
                >
                  {/* Icon */}
                  <div
                    className={cn(
                      "h-8 w-8 rounded-lg flex items-center justify-center shrink-0",
                      itemTypeBg(item.type)
                    )}
                  >
                    {itemTypeIcon(item.type)}
                  </div>

                  {/* Title */}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-foreground truncate font-body">
                      {item.title}
                    </p>
                  </div>

                  {/* Type badge */}
                  <span
                    className={cn(
                      "hidden sm:inline-flex text-[10px] font-semibold px-2 py-0.5 rounded-md shrink-0",
                      itemTypeBadgeClass(item.type)
                    )}
                  >
                    {itemTypeBadge(item.type)}
                  </span>

                  {/* Status for uploaded documents */}
                  {item.type === "upload" && item.status && (
                    <>
                      {(item.status === "processing" ||
                        item.status === "pending") && (
                        <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground shrink-0" />
                      )}
                      {item.status === "ready" && (
                        <div className="h-2 w-2 rounded-full bg-emerald-500 shrink-0" />
                      )}
                      {item.status === "failed" && (
                        <div className="h-2 w-2 rounded-full bg-destructive shrink-0" />
                      )}
                    </>
                  )}

                  {/* Date */}
                  <span className="text-xs text-muted-foreground shrink-0 hidden md:block font-body">
                    {formatDate(item.date)}
                  </span>

                  {/* Actions */}
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <button
                        onClick={(e) => e.stopPropagation()}
                        className="h-7 w-7 rounded-md flex items-center justify-center text-muted-foreground hover:bg-muted hover:text-foreground opacity-0 group-hover:opacity-100 transition-all shrink-0"
                      >
                        <MoreVertical className="h-4 w-4" />
                      </button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      {item.type === "conversation" && (
                        <DropdownMenuItem
                          onClick={(e) => {
                            e.stopPropagation()
                            openConversation(item.id)
                          }}
                        >
                          <MessageSquare className="mr-2 h-4 w-4" />
                          Ouvrir
                        </DropdownMenuItem>
                      )}
                      {item.linkedItemId && (
                        <DropdownMenuItem
                          onClick={(e) => {
                            e.stopPropagation()
                            handleItemClick(item)
                          }}
                        >
                          <FileText className="mr-2 h-4 w-4" />
                          Ouvrir
                        </DropdownMenuItem>
                      )}
                      {(item.type === "upload" || item.linkedItemId) && (
                        <DropdownMenuItem
                          onClick={(e) => {
                            e.stopPropagation()
                            handleItemDelete(item)
                          }}
                          className="text-destructive"
                        >
                          <Trash2 className="mr-2 h-4 w-4" />
                          {item.linkedItemId ? "Retirer" : "Supprimer"}
                        </DropdownMenuItem>
                      )}
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
