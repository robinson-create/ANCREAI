import { useState, useRef, useEffect, useCallback, useMemo } from "react"
import { useParams, useNavigate } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import {
  Bot,
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
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { assistantsApi } from "@/api/assistants"
import { chatApi } from "@/api/chat"
import type { Block, Citation, Message } from "@/types"
import { cn } from "@/lib/utils"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { BlockRenderer } from "@/components/blocks/BlockRenderer"
import { createDictationAdapter } from "@/lib/dictation"

import {
  AssistantRuntimeProvider,
  useExternalStoreRuntime,
  useComposerRuntime,
  useComposer,
  ComposerPrimitive,
} from "@assistant-ui/react"
import type { ThreadMessageLike, AppendMessage } from "@assistant-ui/react"

interface LocalMessage extends Message {
  isStreaming?: boolean
}

/** Single toggle button for dictation — Gemini-style. */
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

export function ChatPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

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

  const { data: assistant, isLoading: isLoadingAssistant } = useQuery({
    queryKey: ["assistant", id],
    queryFn: () => assistantsApi.get(id!),
    enabled: !!id,
  })

  const { data: conversations, refetch: refetchConversations } = useQuery({
    queryKey: ["conversations", id],
    queryFn: () => chatApi.listConversations(id!),
    enabled: !!id,
  })

  const scrollToBottom = useCallback(() => {
    const el = scrollContainerRef.current
    if (el) {
      el.scrollTop = el.scrollHeight
    }
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages, scrollToBottom])

  const onNew = useCallback(
    async (message: AppendMessage) => {
      if (!id) return

      const textPart = message.content.find((p) => p.type === "text")
      if (!textPart || textPart.type !== "text") return
      const userText = textPart.text

      isNewConversationRef.current = !conversationIdRef.current

      const userMsg: LocalMessage = {
        id: Date.now().toString(),
        role: "user",
        content: userText,
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

      abortFnRef.current = chatApi.stream(
        id,
        {
          message: userText,
          conversation_id: conversationIdRef.current || undefined,
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
                ? { ...msg, isStreaming: false, citations: response.citations }
                : msg
            )
          )
          setIsRunning(false)
          refetchConversations()
        },
        (error) => {
          console.error("Chat error:", error)
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

  const handleNewConversation = () => {
    setMessages([])
    setConversationId(null)
    conversationIdRef.current = null
    if (abortFnRef.current) {
      abortFnRef.current()
    }
  }

  const loadConversation = async (convId: string) => {
    if (!id) return

    try {
      const history = await chatApi.getConversation(id, convId)
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
    } catch (error) {
      console.error("Failed to load conversation:", error)
    }
  }

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

    // Keep messages up to (not including) the edited user message
    const kept = messages.slice(0, msgIndex)
    setMessages(kept)
    setEditingMessageId(null)
    setEditContent("")

    // Re-send with edited text via the runtime
    const assistantMessageId = (Date.now() + 1).toString()
    const userMsg: LocalMessage = {
      id: Date.now().toString(),
      role: "user",
      content: editContent.trim(),
      created_at: new Date().toISOString(),
    }
    const assistantMsg: LocalMessage = {
      id: assistantMessageId,
      role: "assistant",
      content: "",
      isStreaming: true,
      created_at: new Date().toISOString(),
    }

    setMessages((prev) => [...prev, userMsg, assistantMsg])
    setIsRunning(true)

    abortFnRef.current = chatApi.stream(
      id,
      {
        message: editContent.trim(),
        conversation_id: conversationIdRef.current || undefined,
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
              ? { ...msg, isStreaming: false, citations: response.citations }
              : msg
          )
        )
        setIsRunning(false)
        refetchConversations()
      },
      (error) => {
        console.error("Chat error:", error)
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
        setConversationId(newConversationId)
        conversationIdRef.current = newConversationId
        refetchConversations()
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
  }, [editingMessageId, editContent, id, messages, refetchConversations])

  if (isLoadingAssistant) {
    return (
      <div className="flex h-[calc(100vh-4rem)] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  if (!assistant) {
    return (
      <div className="container py-8">
        <Card>
          <CardHeader>
            <CardTitle>Assistant non trouvé</CardTitle>
            <CardDescription>
              L'assistant demandé n'existe pas ou a été supprimé.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={() => navigate("/app/assistants")}>
              <ArrowLeft className="mr-2 h-4 w-4" />
              Retour aux assistants
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <div className="flex h-[calc(100vh-4rem)]">
        {/* Sidebar */}
        <div className="hidden w-64 flex-shrink-0 border-r bg-muted/30 md:block">
          <div className="flex h-full flex-col">
            <div className="p-4">
              <Button
                variant="outline"
                className="w-full justify-start"
                onClick={handleNewConversation}
              >
                <Plus className="mr-2 h-4 w-4" />
                Nouvelle conversation
              </Button>
            </div>
            <Separator />
            <ScrollArea className="flex-1 p-4">
              <div className="space-y-2">
                <p className="text-xs font-medium text-muted-foreground">
                  HISTORIQUE
                </p>
                {conversations && conversations.length > 0 ? (
                  <div className="space-y-1">
                    {conversations.map((conv) => (
                      <button
                        key={conv.id}
                        onClick={() => loadConversation(conv.id)}
                        className={cn(
                          "w-full rounded-md p-2 text-left text-sm transition-colors hover:bg-muted",
                          conversationId === conv.id && "bg-muted"
                        )}
                      >
                        <p className="truncate font-medium">{conv.title}</p>
                        <p className="text-xs text-muted-foreground">
                          {new Date(conv.last_message_at).toLocaleDateString()}
                        </p>
                      </button>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    Aucune conversation
                  </p>
                )}
              </div>
            </ScrollArea>
            <Separator />
            <div className="p-4">
              <p className="text-xs font-medium text-muted-foreground mb-2">
                DOCUMENTS
              </p>
              {assistant.collection_ids.length > 0 ? (
                <Badge variant="secondary">
                  <FileText className="mr-1 h-3 w-3" />
                  {assistant.collection_ids.length} collection(s)
                </Badge>
              ) : (
                <p className="text-sm text-muted-foreground">Aucun document</p>
              )}
            </div>
          </div>
        </div>

        {/* Main chat area */}
        <div className="flex flex-1 flex-col">
          {/* Chat header */}
          <div className="flex items-center justify-between border-b px-4 py-3">
            <div className="flex items-center gap-3">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => navigate("/app/assistants")}
              >
                <ArrowLeft className="h-4 w-4" />
              </Button>
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10">
                  <Bot className="h-4 w-4 text-primary" />
                </div>
                <div>
                  <p className="font-medium">{assistant.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {assistant.model}
                  </p>
                </div>
              </div>
            </div>
            <Button variant="ghost" size="sm" onClick={handleNewConversation}>
              <Plus className="mr-2 h-4 w-4" />
              Nouvelle conversation
            </Button>
          </div>

          {/* Messages */}
          <div ref={scrollContainerRef} className="flex-1 overflow-y-auto p-4">
            <div className="mx-auto max-w-3xl space-y-6">
              {messages.length === 0 && (
                <div className="flex flex-col items-center justify-center py-16 text-center">
                  <Bot className="h-12 w-12 text-muted-foreground" />
                  <h3 className="mt-4 text-lg font-semibold">
                    Commencer une conversation
                  </h3>
                  <p className="mt-2 max-w-sm text-muted-foreground">
                    Posez votre première question à {assistant.name}.
                  </p>
                </div>
              )}

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
                      ) : editingMessageId === message.id ? (
                        <div className="space-y-2">
                          <textarea
                            value={editContent}
                            onChange={(e) => setEditContent(e.target.value)}
                            className="w-full rounded-md border bg-background p-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
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

                  {/* Action buttons (copy + edit) */}
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

          {/* Composer - assistant-ui */}
          <div className="border-t p-4">
            <div className="mx-auto max-w-3xl">
              <ComposerPrimitive.Root className="relative flex items-end rounded-md border bg-background">
                <ComposerPrimitive.Input
                  placeholder="Écrivez ou dictez votre message..."
                  className="min-h-[60px] flex-1 resize-none border-0 bg-transparent p-3 pr-20 text-sm focus:outline-none focus:ring-0"
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
                    <ComposerPrimitive.Send className="inline-flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50">
                      <Send className="h-4 w-4" />
                    </ComposerPrimitive.Send>
                  )}
                </div>
              </ComposerPrimitive.Root>
              <p className="mt-2 text-center text-xs text-muted-foreground">
                Entrée pour envoyer, Maj+Entrée pour saut de ligne
              </p>
            </div>
          </div>
        </div>
      </div>
    </AssistantRuntimeProvider>
  )
}
