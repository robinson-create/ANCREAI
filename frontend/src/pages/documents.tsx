import { useState, useEffect, useRef, useMemo } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { useNavigate, useLocation, useSearchParams } from "react-router-dom"
import {
  Plus,
  FileEdit,
  FileText,
  Loader2,
  AlertCircle,
  Copy,
  Archive,
  Trash2,
  MoreVertical,
  Construction,
  FolderPlus,
  ArrowRight,
  Presentation,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useToast } from "@/hooks/use-toast"
import { workspaceDocumentsApi } from "@/api/workspace-documents"
import { presentationsApi } from "@/api/presentations"
import { contactsApi } from "@/api/contacts"
import { useDocumentGeneration } from "@/contexts/document-generation-context"
import { AddToFolderDialog } from "@/components/folders/AddToFolderDialog"
import type { WorkspaceDocumentListItem, PresentationListItem } from "@/types"

// ── Constants ──

const DOC_TYPES = [
  { value: "generic", label: "Generique" },
  { value: "quote", label: "Devis" },
  { value: "invoice", label: "Facture" },
  { value: "contract", label: "Contrat" },
  { value: "nda", label: "NDA" },
  { value: "email", label: "Email" },
  { value: "procedure", label: "Procedure" },
]

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

const PRES_STATUS_LABELS: Record<string, string> = {
  draft: "Brouillon",
  generating_outline: "Génération...",
  outline_ready: "Plan prêt",
  generating_slides: "Génération...",
  ready: "Prêt",
  exporting: "Export...",
  error: "Erreur",
}

const PRES_STATUS_VARIANTS: Record<string, "default" | "secondary" | "outline" | "destructive"> = {
  draft: "outline",
  generating_outline: "secondary",
  outline_ready: "secondary",
  generating_slides: "secondary",
  ready: "default",
  exporting: "secondary",
  error: "destructive",
}

// ── Helpers ──

function detectDocType(text: string): string {
  const lower = text.toLowerCase()
  if (lower.includes("devis")) return "quote"
  if (lower.includes("facture")) return "invoice"
  if (lower.includes("contrat")) return "contract"
  if (lower.includes("nda")) return "nda"
  if (lower.includes("rapport") || lower.includes("compte-rendu") || lower.includes("compte rendu")) return "report"
  if (lower.includes("note")) return "note"
  if (lower.includes("procedure") || lower.includes("procédure")) return "procedure"
  return "generic"
}

// ── Unified item type ──

type UnifiedDocItem = {
  id: string
  kind: "document" | "presentation"
  title: string
  status: string
  statusLabel: string
  statusVariant: "default" | "secondary" | "outline" | "destructive"
  typeBadge: string
  version: number
  created_at: string
  updated_at: string
  // original doc fields
  doc_type?: string
}

// ── Component ──

export function DocumentsPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams, setSearchParams] = useSearchParams()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const docGen = useDocumentGeneration()

  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [newTitle, setNewTitle] = useState("")
  const [newDocType, setNewDocType] = useState("generic")
  const [kindFilter, setKindFilter] = useState<"all" | "document" | "presentation">("all")
  const [prompt, setPrompt] = useState("")
  const [isCreatingFromPrompt, setIsCreatingFromPrompt] = useState(false)
  const [createMode, setCreateMode] = useState<"document" | "presentation">("document")
  const [slideCount, setSlideCount] = useState(5)
  const [presLanguage, setPresLanguage] = useState("fr")
  const promptHandled = useRef(false)
  const contactPrefillHandled = useRef(false)

  // ── Queries ──

  const { data: documents, isLoading: docsLoading, error: docsError } = useQuery({
    queryKey: ["workspace-documents"],
    queryFn: () => workspaceDocumentsApi.list(),
  })

  const { data: presentations, isLoading: presLoading, error: presError } = useQuery({
    queryKey: ["presentations"],
    queryFn: () => presentationsApi.list(),
  })

  const isLoading = docsLoading || presLoading
  const error = docsError || presError

  // ── Unified items ──

  const unifiedItems = useMemo(() => {
    const docItems: UnifiedDocItem[] = (documents ?? []).map((doc: WorkspaceDocumentListItem) => ({
      id: doc.id,
      kind: "document" as const,
      title: doc.title,
      status: doc.status,
      statusLabel: STATUS_LABELS[doc.status] || doc.status,
      statusVariant: STATUS_VARIANTS[doc.status] || "outline",
      typeBadge: DOC_TYPES.find((t) => t.value === doc.doc_type)?.label || doc.doc_type,
      version: doc.version,
      created_at: doc.created_at,
      updated_at: doc.updated_at,
      doc_type: doc.doc_type,
    }))

    const presItems: UnifiedDocItem[] = (presentations ?? []).map((p: PresentationListItem) => ({
      id: p.id,
      kind: "presentation" as const,
      title: p.title,
      status: p.status,
      statusLabel: PRES_STATUS_LABELS[p.status] || p.status,
      statusVariant: PRES_STATUS_VARIANTS[p.status] || "outline",
      typeBadge: "Présentation",
      version: p.version,
      created_at: p.created_at,
      updated_at: p.updated_at,
    }))

    return [...docItems, ...presItems].sort(
      (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
    )
  }, [documents, presentations])

  const filteredItems = useMemo(() => {
    if (kindFilter === "all") return unifiedItems
    return unifiedItems.filter((i) => i.kind === kindFilter)
  }, [unifiedItems, kindFilter])

  // ── Delete state ──

  const [deleteTarget, setDeleteTarget] = useState<{ id: string; kind: "document" | "presentation" } | null>(null)
  const [addToFolderTarget, setAddToFolderTarget] = useState<{ id: string; title: string } | null>(null)

  // ── Document mutations ──

  const deleteDocMutation = useMutation({
    mutationFn: (docId: string) => workspaceDocumentsApi.delete(docId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workspace-documents"] })
      toast({ title: "Document supprimé" })
    },
    onError: () => {
      toast({ title: "Erreur", description: "Impossible de supprimer le document.", variant: "destructive" })
    },
  })

  const duplicateDocMutation = useMutation({
    mutationFn: (docId: string) => workspaceDocumentsApi.duplicate(docId),
    onSuccess: (doc) => {
      queryClient.invalidateQueries({ queryKey: ["workspace-documents"] })
      toast({ title: "Document dupliqué", description: `"${doc.title}" a été créé.` })
    },
    onError: () => {
      toast({ title: "Erreur", description: "Impossible de dupliquer le document.", variant: "destructive" })
    },
  })

  const archiveMutation = useMutation({
    mutationFn: (docId: string) => workspaceDocumentsApi.update(docId, { status: "archived" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workspace-documents"] })
      toast({ title: "Document archivé" })
    },
    onError: () => {
      toast({ title: "Erreur", description: "Impossible d'archiver le document.", variant: "destructive" })
    },
  })

  // ── Presentation mutations ──

  const deletePresMutation = useMutation({
    mutationFn: (id: string) => presentationsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["presentations"] })
      toast({ title: "Présentation supprimée" })
    },
    onError: () => {
      toast({ title: "Erreur", description: "Impossible de supprimer la présentation.", variant: "destructive" })
    },
  })

  const duplicatePresMutation = useMutation({
    mutationFn: (id: string) => presentationsApi.duplicate(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["presentations"] })
      toast({ title: "Présentation dupliquée" })
    },
    onError: () => {
      toast({ title: "Erreur", description: "Impossible de dupliquer la présentation.", variant: "destructive" })
    },
  })

  // ── Chat prompt submit ──

  const handlePromptSubmit = async () => {
    if (isCreatingFromPrompt) return

    // For presentations, prompt is required
    if (createMode === "presentation" && !prompt.trim()) return

    setIsCreatingFromPrompt(true)

    try {
      if (createMode === "presentation") {
        const langMap: Record<string, string> = { fr: "fr-FR", en: "en-US", es: "es-ES", de: "de-DE", it: "it-IT", pt: "pt-BR" }
        const lang = langMap[presLanguage] || "fr-FR"
        const pres = await presentationsApi.create({
          title: "Sans titre",
          prompt: prompt.trim(),
          settings: { slide_count: slideCount, language: lang, style: "professional" },
        })
        // Immediately trigger outline generation so editor skips draft phase
        await presentationsApi.generateOutline(pres.id, {
          prompt: prompt.trim(),
          slide_count: slideCount,
          language: lang,
          style: "professional",
        })
        queryClient.invalidateQueries({ queryKey: ["presentations"] })
        setIsCreateOpen(false)
        navigate(`/app/presentations/${pres.id}`)
      } else {
        const docType = prompt.trim() ? detectDocType(prompt) : newDocType
        const doc = await workspaceDocumentsApi.create({ title: newTitle || "Sans titre", doc_type: docType })
        queryClient.invalidateQueries({ queryKey: ["workspace-documents"] })
        setIsCreateOpen(false)
        navigate(`/app/documents/${doc.id}`, { state: prompt.trim() ? { prompt: prompt.trim() } : undefined })
      }
    } catch {
      toast({ title: "Erreur", description: "Impossible de créer.", variant: "destructive" })
    } finally {
      setIsCreatingFromPrompt(false)
      setPrompt("")
      setNewTitle("")
    }
  }

  // ── Auto-create from dashboard prompt ──

  useEffect(() => {
    const state = location.state as { prompt?: string } | null
    if (state?.prompt && !promptHandled.current) {
      promptHandled.current = true
      const p = state.prompt
      const docType = detectDocType(p)
      window.history.replaceState({}, "")
      workspaceDocumentsApi
        .create({ title: "Sans titre", doc_type: docType })
        .then((doc) => {
          queryClient.invalidateQueries({ queryKey: ["workspace-documents"] })
          navigate(`/app/documents/${doc.id}`, { state: { prompt: p } })
        })
        .catch(() => {
          toast({ title: "Erreur", description: "Impossible de créer le document.", variant: "destructive" })
        })
    }
  }, [location.state, navigate, queryClient, toast])

  // ── Contact prefill ──

  useEffect(() => {
    const contactId = searchParams.get("contact")
    if (contactId && !contactPrefillHandled.current) {
      contactPrefillHandled.current = true
      contactsApi
        .get(contactId)
        .then((contact) => {
          const fullName = `${contact.first_name || ""} ${contact.last_name || ""}`.trim()
          const contactName = fullName || contact.primary_email
          setNewTitle(`Document pour ${contactName}`)
          setNewDocType("generic")
          setIsCreateOpen(true)
          searchParams.delete("contact")
          setSearchParams(searchParams, { replace: true })
          toast({ title: "Nouveau document", description: `Créez un document pour ${contactName}` })
        })
        .catch((err) => {
          console.error("Failed to fetch contact for document prefill:", err)
          toast({ variant: "destructive", title: "Erreur", description: "Impossible de charger le contact." })
        })
    }
  }, [searchParams, setSearchParams, toast])

  // ── Delete handler ──

  const handleDelete = () => {
    if (!deleteTarget) return
    if (deleteTarget.kind === "document") {
      deleteDocMutation.mutate(deleteTarget.id)
    } else {
      deletePresMutation.mutate(deleteTarget.id)
    }
    setDeleteTarget(null)
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between p-6 border-b bg-background">
        <h1 className="font-heading text-2xl font-bold tracking-tight text-foreground">Documents</h1>
        <Button onClick={() => setIsCreateOpen(true)} className="gap-2">
          <Plus className="h-4 w-4" />
          Nouveau document
        </Button>
      </div>

      <div className="flex-1 overflow-auto p-6 space-y-6">

      {/* Kind filter tabs */}
      <Tabs
        value={kindFilter}
        onValueChange={(v) => setKindFilter(v as "all" | "document" | "presentation")}
      >
        <TabsList className="bg-muted">
          <TabsTrigger value="all" className="font-medium font-body">Tous</TabsTrigger>
          <TabsTrigger value="document" className="font-medium font-body">Documents</TabsTrigger>
          <TabsTrigger value="presentation" className="font-medium font-body">Présentations</TabsTrigger>
        </TabsList>
      </Tabs>

      {/* Loading */}
      {isLoading && (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-40 rounded-lg" />
          ))}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 text-destructive">
          <AlertCircle className="h-4 w-4" />
          <span>Erreur lors du chargement des documents.</span>
        </div>
      )}

      {/* Empty state */}
      {!isLoading && !error && filteredItems.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <FileEdit className="h-12 w-12 text-muted-foreground/50 mb-4" />
          <p className="text-lg font-semibold font-heading text-foreground">Aucun document</p>
          <p className="text-sm text-muted-foreground mb-4 font-body">
            Cliquez sur "Nouveau document" pour créer votre premier document ou présentation.
          </p>
        </div>
      )}

      {/* Documents grid */}
      {filteredItems.length > 0 && (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filteredItems.map((item) => {
            const isDocGenerating = item.kind === "document" && (docGen?.generatingDocIds.has(item.id) ?? false)
            const isPresGenerating =
              item.kind === "presentation" &&
              ["generating_outline", "generating_slides", "exporting"].includes(item.status)
            const isGenerating = isDocGenerating || isPresGenerating

            return (
              <Card
                key={`${item.kind}-${item.id}`}
                className="relative group cursor-pointer hover:shadow-lg hover:border-primary/20 transition-all rounded-xl border-border"
                onClick={() => {
                  if (item.kind === "document") {
                    navigate(`/app/documents/${item.id}`)
                  } else {
                    navigate(`/app/presentations/${item.id}`)
                  }
                }}
              >
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between gap-2">
                    {isGenerating ? (
                      <Badge variant="secondary" className="gap-1.5 bg-accent/10 text-accent font-medium">
                        <Loader2 className="h-3 w-3 animate-spin" />
                        {item.kind === "presentation" ? "Génération..." : "En génération"}
                      </Badge>
                    ) : (
                      <Badge variant={item.statusVariant} className="font-medium">
                        {item.statusLabel}
                      </Badge>
                    )}
                    <Badge variant="outline" className="text-[10px] font-medium px-2 py-0.5 gap-1 flex items-center">
                      {item.kind === "presentation" ? (
                        <Presentation className="h-3 w-3" />
                      ) : (
                        <FileText className="h-3 w-3" />
                      )}
                      {item.typeBadge}
                    </Badge>
                  </div>
                  <CardTitle className="font-heading text-lg mt-2 text-foreground">{item.title}</CardTitle>
                  <CardDescription className="font-body text-xs">
                    v{item.version} — Modifié le{" "}
                    {new Date(item.updated_at).toLocaleDateString("fr-FR")}
                  </CardDescription>
                </CardHeader>
                <CardFooter className="text-xs text-muted-foreground font-body">
                  {isGenerating ? (
                    <span className="flex items-center gap-1.5 text-accent">
                      <Construction className="h-3 w-3" />
                      Génération en cours…
                    </span>
                  ) : (
                    <>
                      Créé le{" "}
                      {new Date(item.created_at).toLocaleDateString("fr-FR")}
                    </>
                  )}
                </CardFooter>

                {/* Actions dropdown */}
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 w-7 p-0 absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <MoreVertical className="h-4 w-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" onClick={(e) => e.stopPropagation()}>
                    {item.kind === "document" && (
                      <DropdownMenuItem onClick={() => setAddToFolderTarget({ id: item.id, title: item.title })}>
                        <FolderPlus className="h-4 w-4 mr-2" />
                        Ajouter à un dossier
                      </DropdownMenuItem>
                    )}
                    <DropdownMenuItem
                      onClick={() => {
                        if (item.kind === "document") {
                          duplicateDocMutation.mutate(item.id)
                        } else {
                          duplicatePresMutation.mutate(item.id)
                        }
                      }}
                    >
                      <Copy className="h-4 w-4 mr-2" />
                      Dupliquer
                    </DropdownMenuItem>
                    {item.kind === "document" && item.status !== "archived" && (
                      <DropdownMenuItem onClick={() => archiveMutation.mutate(item.id)}>
                        <Archive className="h-4 w-4 mr-2" />
                        Archiver
                      </DropdownMenuItem>
                    )}
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                      className="text-destructive"
                      onClick={() => setDeleteTarget({ id: item.id, kind: item.kind })}
                    >
                      <Trash2 className="h-4 w-4 mr-2" />
                      Supprimer
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </Card>
            )
          })}
        </div>
      )}

      {/* Create dialog */}
      <Dialog open={isCreateOpen} onOpenChange={(open) => {
        setIsCreateOpen(open)
        if (!open) { setPrompt(""); setCreateMode("document") }
      }}>
        <DialogContent className="sm:max-w-lg p-0 gap-0 overflow-hidden">
          <div className="p-5 space-y-4">
            <DialogHeader className="pb-0">
              <DialogTitle>Nouveau</DialogTitle>
              <DialogDescription>
                Décrivez ce que vous souhaitez créer.
              </DialogDescription>
            </DialogHeader>

            <textarea
              placeholder={
                createMode === "presentation"
                  ? "Décrivez la présentation à créer..."
                  : "Décrivez le document à créer..."
              }
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault()
                  handlePromptSubmit()
                }
              }}
              disabled={isCreatingFromPrompt}
              rows={4}
              className="w-full resize-none rounded-lg border bg-background px-3 py-2.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              autoFocus
            />

            {/* Document-specific: doc type */}
            {createMode === "document" && (
              <div className="space-y-2">
                <Label htmlFor="doc_type" className="text-xs text-muted-foreground">Type de document</Label>
                <Select value={newDocType} onValueChange={setNewDocType}>
                  <SelectTrigger className="h-9">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {DOC_TYPES.map((t) => (
                      <SelectItem key={t.value} value={t.value}>
                        {t.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            {/* Presentation-specific: slide count + language */}
            {createMode === "presentation" && (
              <div className="flex items-center gap-2 flex-wrap">
                <select
                  value={slideCount}
                  onChange={(e) => setSlideCount(Number(e.target.value))}
                  className="inline-flex items-center rounded-full border bg-background px-3 py-1.5 text-xs font-medium text-foreground cursor-pointer focus:outline-none focus:ring-1 focus:ring-primary"
                >
                  {[1, 2, 3, 4, 5, 6, 7, 8, 10, 12].map((n) => (
                    <option key={n} value={n}>
                      {n} slide{n > 1 ? "s" : ""}
                    </option>
                  ))}
                </select>
                <select
                  value={presLanguage}
                  onChange={(e) => setPresLanguage(e.target.value)}
                  className="inline-flex items-center rounded-full border bg-background px-3 py-1.5 text-xs font-medium text-foreground cursor-pointer focus:outline-none focus:ring-1 focus:ring-primary"
                >
                  <option value="fr">Français</option>
                  <option value="en">English</option>
                  <option value="es">Español</option>
                  <option value="de">Deutsch</option>
                  <option value="it">Italiano</option>
                  <option value="pt">Português</option>
                </select>
              </div>
            )}
          </div>

          {/* Footer with toggles + submit */}
          <div className="flex items-center justify-between gap-2 border-t bg-muted/30 px-5 py-3">
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setCreateMode("document")}
                className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                  createMode === "document"
                    ? "bg-foreground text-background"
                    : "bg-background text-muted-foreground hover:bg-muted border"
                }`}
              >
                <FileText className="h-3.5 w-3.5" />
                Document
              </button>
              <button
                type="button"
                onClick={() => setCreateMode("presentation")}
                className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                  createMode === "presentation"
                    ? "bg-foreground text-background"
                    : "bg-background text-muted-foreground hover:bg-muted border"
                }`}
              >
                <Presentation className="h-3.5 w-3.5" />
                Présentation
              </button>
            </div>
            <button
              type="button"
              onClick={handlePromptSubmit}
              disabled={!prompt.trim() || isCreatingFromPrompt}
              className="flex items-center justify-center h-9 w-9 rounded-full bg-foreground text-background disabled:opacity-40 transition-opacity hover:opacity-90 shrink-0"
            >
              {isCreatingFromPrompt ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <ArrowRight className="h-4 w-4" />
              )}
            </button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Delete confirmation */}
      <AlertDialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Supprimer ?</AlertDialogTitle>
            <AlertDialogDescription>
              Cette action est irréversible. {deleteTarget?.kind === "presentation" ? "La présentation" : "Le document"} sera définitivement supprimé.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={handleDelete}
            >
              Supprimer
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AddToFolderDialog
        open={!!addToFolderTarget}
        onOpenChange={(open) => !open && setAddToFolderTarget(null)}
        itemType="document"
        itemId={addToFolderTarget?.id ?? ""}
        itemTitle={addToFolderTarget?.title}
        onSuccess={() => queryClient.invalidateQueries({ queryKey: ["folders"] })}
      />
      </div>
    </div>
  )
}
