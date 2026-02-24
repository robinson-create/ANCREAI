import { useEffect, useCallback, useState, useRef } from "react"
import { useParams, useNavigate, useLocation } from "react-router-dom"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import {
  ArrowLeft,
  Download,
  Loader2,
  Save,
  AlertCircle,
  Eye,
  PenLine,
  Check,
  Send,
  Archive,
  ArchiveRestore,
  MessageSquare,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { useToast } from "@/hooks/use-toast"
import { useDocumentStore } from "@/hooks/use-document-store"
import { useDocumentGeneration } from "@/contexts/document-generation-context"
import { useAutosave } from "@/hooks/use-autosave"
import { workspaceDocumentsApi } from "@/api/workspace-documents"
import { assistantsApi } from "@/api/assistants"
import { BlockRenderer } from "@/components/documents/BlockRenderer"
import { DocumentCopilotActions } from "@/components/documents/DocumentCopilotActions"
import { DocumentPreview } from "@/components/documents/DocumentPreview"
import { AnchorSpinner } from "@/components/documents/AnchorSpinner"
import { DocumentAssistantProvider, useDocumentAssistant } from "@/contexts/document-assistant-stream"
import { DocumentAssistantSidebar } from "@/components/documents/document-assistant-sidebar"
import type { DocBlock, DocBlockKind, DocModel } from "@/types"
import { markdownToProseMirrorDoc, splitMarkdownIntoSections } from "@/lib/markdown-to-prosemirror"

const STATUS_LABELS: Record<string, string> = {
  draft: "Brouillon",
  validated: "Validé",
  sent: "Envoyé",
  archived: "Archivé",
}

const STATUS_VARIANTS: Record<string, "default" | "secondary" | "outline" | "destructive"> = {
  draft: "outline",
  validated: "default",
  sent: "secondary",
  archived: "destructive",
}

const DEFAULT_DOC_MODEL: DocModel = {
  version: 1,
  meta: { tags: [], custom: {} },
  blocks: [],
  variables: {},
  sources: [],
}

function generateId() {
  return crypto.randomUUID()
}

function DocumentEditorContent() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const queryClient = useQueryClient()
  const { toast } = useToast()

  // Extract initial prompt from navigation state (from dashboard)
  useState(() => {
    const p = (location.state as { prompt?: string } | null)?.prompt
    if (p) window.history.replaceState({}, "")
    return p
  })

  const { docModel, setDocModel, updateBlock, addBlock, removeBlock, reset } =
    useDocumentStore()
  const { save, isSaving, lastSaved } = useAutosave(id || "")

  const [title, setTitle] = useState("")
  const [isExporting, setIsExporting] = useState(false)
  const [isPreview, setIsPreview] = useState(false)
  const [isGeneratingLocal] = useState(false)
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false)
  const docGen = useDocumentGeneration()
  const isGeneratingFromContext = id ? docGen?.generatingDocIds.has(id) ?? false : false
  const isGenerating = isGeneratingFromContext || isGeneratingLocal

  // Document assistant context (must be called before any early returns)
  const { setSelectedAssistantId } = useDocumentAssistant();
  const [localAssistantId, setLocalAssistantId] = useState<string | null>(null);

  // Fetch assistants list for the sidebar
  const { data: assistants = [] } = useQuery({
    queryKey: ["assistants"],
    queryFn: assistantsApi.list,
    staleTime: 30_000,
  });

  // Auto-select first assistant so the chat input is enabled
  useEffect(() => {
    const first = assistants[0];
    if (first && !localAssistantId) {
      setLocalAssistantId(first.id);
    }
  }, [assistants, localAssistantId]);

  // Track whether current docModel comes from an API load (skip autosave)
  const isLoadingFromApi = useRef(true)

  // Reset store when document ID changes (prevents stale content from previous doc)
  useEffect(() => {
    isLoadingFromApi.current = true
    reset()
  }, [id, reset])

  // Fetch document
  const {
    data: doc,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["workspace-document", id],
    queryFn: () => workspaceDocumentsApi.get(id!),
    enabled: !!id,
  })

  // Initialize store from fetched document
  useEffect(() => {
    if (doc) {
      isLoadingFromApi.current = true
      const content = doc.content_json || DEFAULT_DOC_MODEL
      // Ensure content has all required fields
      const normalized: DocModel = {
        version: content.version ?? 1,
        meta: content.meta ?? { tags: [], custom: {} },
        blocks: content.blocks ?? [],
        variables: content.variables ?? {},
        sources: content.sources ?? [],
      }
      setDocModel(normalized)
      setTitle(doc.title)
    }
  }, [doc, setDocModel])

  // Sync assistant with sidebar
  useEffect(() => {
    if (localAssistantId) {
      setSelectedAssistantId(localAssistantId);
    }
  }, [localAssistantId, setSelectedAssistantId]);

  // Autosave on docModel changes — skip saves triggered by API loads
  useEffect(() => {
    if (docModel && id) {
      if (isLoadingFromApi.current) {
        isLoadingFromApi.current = false
        return
      }
      save(docModel)
    }
  }, [docModel]) // eslint-disable-line react-hooks/exhaustive-deps

  // Save title on blur
  const handleTitleBlur = useCallback(async () => {
    if (id && title !== doc?.title) {
      await workspaceDocumentsApi.update(id, { title })
      queryClient.invalidateQueries({ queryKey: ["workspace-document", id] })
    }
  }, [id, title, doc?.title, queryClient])

  // Block change handler
  const handleBlockChange = useCallback(
    (blockId: string, patch: Partial<DocBlock>) => {
      updateBlock(blockId, patch)
    },
    [updateBlock]
  )

  // Add new block
  const handleAddBlock = useCallback(
    (type: DocBlock["type"]) => {
      const newBlock: DocBlock = {
        type,
        id: generateId(),
        label: "",
      }

      if (type === "rich_text" || type === "clause" || type === "terms") {
        newBlock.content = {
          type: "doc",
          content: [{ type: "paragraph" }],
        }
      }
      if (type === "line_items") {
        newBlock.items = []
        newBlock.columns = [
          "description",
          "quantity",
          "unit",
          "unit_price",
          "tax_rate",
          "total",
        ]
        newBlock.currency = "EUR"
      }
      if (type === "signature") {
        newBlock.parties = [
          { name: "", role: "Emetteur" },
          { name: "", role: "Destinataire" },
        ]
      }
      if (type === "variables") {
        newBlock.variables = {}
      }

      addBlock(newBlock)
    },
    [addBlock]
  )

  // Export PDF
  const handleExportPdf = useCallback(async () => {
    if (!id) return
    setIsExporting(true)
    try {
      const { url } = await workspaceDocumentsApi.exportPdf(id)
      window.open(url, "_blank")
      toast({ title: "PDF exporté", description: "Le PDF a été généré avec succès." })
    } catch {
      toast({
        title: "Erreur",
        description: "Impossible de générer le PDF.",
        variant: "destructive",
      })
    } finally {
      setIsExporting(false)
    }
  }, [id, toast])

  // Flush current content to the backend before status changes / navigation
  const flushContent = useCallback(async () => {
    if (!id || !docModel || !docModel.blocks.length) return
    try {
      await workspaceDocumentsApi.patchContent(id, docModel)
    } catch (err) {
      console.error("[doc-editor] Failed to flush content:", err)
    }
  }, [id, docModel])

  // Change document status
  const handleStatusChange = useCallback(async (newStatus: string) => {
    if (!id) return
    try {
      // Persist current content before changing status to avoid data loss
      await flushContent()
      await workspaceDocumentsApi.update(id, { status: newStatus })
      queryClient.invalidateQueries({ queryKey: ["workspace-document", id] })
      queryClient.invalidateQueries({ queryKey: ["workspace-documents"] })
      toast({
        title: "Statut mis à jour",
        description: `Le document est maintenant "${STATUS_LABELS[newStatus] || newStatus}".`,
      })
    } catch {
      toast({
        title: "Erreur",
        description: "Impossible de mettre à jour le statut.",
        variant: "destructive",
      })
    }
  }, [id, queryClient, toast, flushContent])

  // Send document to email composer
  const handleSendToEmail = useCallback(async () => {
    if (!id) return
    setIsExporting(true)
    try {
      // Persist current content before exporting to avoid empty PDFs
      await flushContent()
      const { url } = await workspaceDocumentsApi.exportPdf(id)
      // Mark as sent
      await workspaceDocumentsApi.update(id, { status: "sent" })
      queryClient.invalidateQueries({ queryKey: ["workspace-document", id] })
      queryClient.invalidateQueries({ queryKey: ["workspace-documents"] })
      // Navigate to email composer with pre-filled data
      navigate("/app/email", {
        state: {
          fromDocument: {
            id,
            title,
            pdfUrl: url,
          },
        },
      })
    } catch {
      toast({
        title: "Erreur",
        description: "Impossible de générer le PDF pour l'envoi.",
        variant: "destructive",
      })
    } finally {
      setIsExporting(false)
    }
  }, [id, title, navigate, queryClient, toast, flushContent])

  // Get assistant collection IDs for CopilotKit
  const collectionIds: string[] = [] // Will be populated from assistant if linked

  if (isLoading) {
    return (
      <div className="container py-8 space-y-4">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-[400px]" />
      </div>
    )
  }

  if (error || !doc) {
    return (
      <div className="container py-8">
        <div className="flex items-center gap-2 text-destructive">
          <AlertCircle className="h-4 w-4" />
          <span>Document introuvable.</span>
        </div>
        <Button
          variant="ghost"
          className="mt-4"
          onClick={() => navigate("/app/documents")}
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          Retour aux documents
        </Button>
      </div>
    )
  }

  const isReadOnly = doc.status === "sent" || doc.status === "archived"

  return (
    <div className="flex h-full">
      {/* Main content */}
      <div className="flex flex-col flex-1 min-w-0">
      {/* CopilotKit actions (invisible — registers hooks) */}
      <DocumentCopilotActions
        docId={id!}
        title={title}
        docType={doc.doc_type}
        collectionIds={collectionIds}
      />

      {/* Top bar */}
      <div className="flex items-center gap-3 px-4 sm:px-6 py-3 border-b border-border bg-surface-elevated shrink-0">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate("/app/documents")}
        >
          <ArrowLeft className="h-4 w-4" />
        </Button>

        <Input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onBlur={handleTitleBlur}
          readOnly={isReadOnly}
          className={`text-lg font-semibold border-0 shadow-none bg-transparent h-auto py-1 px-2 focus-visible:ring-1 max-w-md ${isReadOnly ? "cursor-default" : ""}`}
          placeholder="Sans titre"
        />

        <Badge variant={STATUS_VARIANTS[doc.status] || "outline"}>
          {STATUS_LABELS[doc.status] || doc.status}
        </Badge>

        <div className="flex-1" />

        {/* ── Status-dependent actions ── */}

        {doc.status === "draft" && (
          <>
            {/* Save indicator */}
            <div className="flex items-center gap-1 text-xs text-muted-foreground">
              {isSaving ? (
                <>
                  <Loader2 className="h-3 w-3 animate-spin" />
                  <span>Enregistrement...</span>
                </>
              ) : lastSaved ? (
                <>
                  <Save className="h-3 w-3" />
                  <span>Enregistré</span>
                </>
              ) : null}
            </div>

            {/* Preview toggle */}
            <Button
              variant={isPreview ? "default" : "outline"}
              size="sm"
              onClick={() => setIsPreview((v) => !v)}
              className="gap-1.5"
            >
              {isPreview ? (
                <>
                  <PenLine className="h-3.5 w-3.5" />
                  <span className="hidden sm:inline">Éditer</span>
                </>
              ) : (
                <>
                  <Eye className="h-3.5 w-3.5" />
                  <span className="hidden sm:inline">Aperçu</span>
                </>
              )}
            </Button>

            {/* Download PDF (icon only) */}
            <Button
              variant="outline"
              size="icon"
              onClick={handleExportPdf}
              disabled={isExporting}
              className="h-8 w-8"
              title="Télécharger le PDF"
            >
              {isExporting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
            </Button>

            {/* Valider */}
            <Button
              size="sm"
              onClick={() => handleStatusChange("validated")}
              className="gap-1.5"
            >
              <Check className="h-3.5 w-3.5" />
              <span>Valider</span>
            </Button>
          </>
        )}

        {doc.status === "validated" && (
          <>
            {/* Modifier (back to draft) */}
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleStatusChange("draft")}
              className="gap-1.5"
            >
              <PenLine className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Modifier</span>
            </Button>

            {/* Download PDF (icon only) */}
            <Button
              variant="outline"
              size="icon"
              onClick={handleExportPdf}
              disabled={isExporting}
              className="h-8 w-8"
              title="Télécharger le PDF"
            >
              {isExporting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
            </Button>

            {/* Archiver */}
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleStatusChange("archived")}
              className="gap-1.5"
            >
              <Archive className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Archiver</span>
            </Button>

            {/* Envoyer */}
            <Button
              size="sm"
              onClick={handleSendToEmail}
              disabled={isExporting}
              className="gap-1.5"
            >
              {isExporting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
              <span>Envoyer</span>
            </Button>
          </>
        )}

        {doc.status === "sent" && (
          <>
            {/* Download PDF */}
            <Button
              variant="outline"
              size="icon"
              onClick={handleExportPdf}
              disabled={isExporting}
              className="h-8 w-8"
              title="Télécharger le PDF"
            >
              {isExporting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
            </Button>

            {/* Archiver */}
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleStatusChange("archived")}
              className="gap-1.5"
            >
              <Archive className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Archiver</span>
            </Button>

            {/* Renvoyer */}
            <Button
              size="sm"
              onClick={handleSendToEmail}
              disabled={isExporting}
              className="gap-1.5"
            >
              {isExporting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
              <span>Renvoyer</span>
            </Button>
          </>
        )}

        {doc.status === "archived" && (
          <>
            {/* Download PDF */}
            <Button
              variant="outline"
              size="icon"
              onClick={handleExportPdf}
              disabled={isExporting}
              className="h-8 w-8"
              title="Télécharger le PDF"
            >
              {isExporting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
            </Button>

            {/* Désarchiver */}
            <Button
              size="sm"
              onClick={() => handleStatusChange("draft")}
              className="gap-1.5"
            >
              <ArchiveRestore className="h-3.5 w-3.5" />
              <span>Désarchiver</span>
            </Button>
          </>
        )}
      </div>

      {/* Scrollable content area */}
      <div className="flex-1 overflow-auto bg-surface relative">
        {/* Anchor spinner overlay during AI generation */}
        <AnchorSpinner active={isGenerating} />

        {isPreview || isReadOnly ? (
          /* ── Preview / read-only mode ── */
          <div className="px-4 sm:px-6 py-8">
            <DocumentPreview
              title={title}
              docType={doc.doc_type}
              docModel={docModel}
            />
          </div>
        ) : (
          /* ── Edit mode ── */
          <div className="max-w-4xl mx-auto px-4 sm:px-6 py-6 space-y-4 min-h-full flex flex-col">
            {/* Blocks */}
            <div className="space-y-4 flex-1">
              {docModel?.blocks.map((block) => (
                <BlockRenderer
                  key={block.id}
                  block={block}
                  onChange={(patch) => handleBlockChange(block.id, patch)}
                  onRemove={() => removeBlock(block.id)}
                />
              ))}

              {/* Sources (if any) */}
              {docModel?.sources && docModel.sources.length > 0 && (
                <div className="border-t pt-4 mt-4">
                  <h3 className="text-sm font-semibold text-muted-foreground mb-2">
                    Sources RAG
                  </h3>
                  <ul className="space-y-1 text-sm text-muted-foreground">
                    {docModel.sources.map((src, i) => (
                      <li key={i}>
                        {src.document_filename}
                        {src.page_number && `, p. ${src.page_number}`}
                        {src.excerpt && (
                          <span className="text-xs ml-2 italic">
                            — {src.excerpt.slice(0, 100)}...
                          </span>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
      {/* End of main content flex-col */}
      </div>

      {/* Document Assistant Sidebar - Desktop (lg+) */}
      {!isPreview && !isReadOnly && (
        <DocumentAssistantSidebar
          className="w-80 hidden lg:flex flex-col border-l border-border"
          onContentUpdate={(update) => {
            if (update.blockId) {
              // Update existing block with parsed markdown
              const block = docModel?.blocks.find(b => b.id === update.blockId);
              if (block && (block.type === "rich_text" || block.type === "clause" || block.type === "terms")) {
                handleBlockChange(update.blockId, {
                  content: markdownToProseMirrorDoc(update.content),
                });
              }
            } else {
              // Split markdown into sections → one block per section
              const sections = splitMarkdownIntoSections(update.content);
              for (const section of sections) {
                addBlock({
                  type: "rich_text",
                  id: generateId(),
                  label: section.label,
                  content: section.doc,
                });
              }
            }
          }}
          onAddBlock={(type: DocBlockKind) => handleAddBlock(type)}
        />
      )}

      {/* Mobile Assistant Button + Sheet */}
      {!isPreview && !isReadOnly && (
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
              <DocumentAssistantSidebar
                className="h-full flex flex-col"
                onContentUpdate={(update) => {
                  if (update.blockId) {
                    // Update existing block with parsed markdown
                    const block = docModel?.blocks.find(b => b.id === update.blockId);
                    if (block && (block.type === "rich_text" || block.type === "clause" || block.type === "terms")) {
                      handleBlockChange(update.blockId, {
                        content: markdownToProseMirrorDoc(update.content),
                      });
                    }
                  } else {
                    // Split markdown into sections → one block per section
                    const sections = splitMarkdownIntoSections(update.content);
                    for (const section of sections) {
                      addBlock({
                        type: "rich_text",
                        id: generateId(),
                        label: section.label,
                        content: section.doc,
                      });
                    }
                  }
                  setIsMobileSidebarOpen(false);
                }}
                onAddBlock={(type: DocBlockKind) => {
                  handleAddBlock(type);
                  setIsMobileSidebarOpen(false);
                }}
              />
            </SheetContent>
          </Sheet>
        </div>
      )}
    </div>
  )
}

/**
 * DocumentEditorPage with Assistant Provider
 */
export function DocumentEditorPage() {
  const { id } = useParams<{ id: string }>();

  return (
    <DocumentAssistantProvider documentId={id}>
      <DocumentEditorContent />
    </DocumentAssistantProvider>
  );
}
