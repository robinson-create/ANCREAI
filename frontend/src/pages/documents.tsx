import { useState, useEffect, useRef } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { useNavigate, useLocation, useSearchParams } from "react-router-dom"
import {
  Plus,
  FileEdit,
  Loader2,
  AlertCircle,
  Copy,
  Archive,
  Trash2,
  MoreVertical,
  Construction,
  FolderPlus,
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
  DialogFooter,
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
import { Input } from "@/components/ui/input"
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
import { contactsApi } from "@/api/contacts"
import { useDocumentGeneration } from "@/contexts/document-generation-context"
import { AddToFolderDialog } from "@/components/folders/AddToFolderDialog"
import type { WorkspaceDocumentListItem } from "@/types"

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
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined)
  const promptHandled = useRef(false)
  const contactPrefillHandled = useRef(false)

  const { data: documents, isLoading, error } = useQuery({
    queryKey: ["workspace-documents", statusFilter],
    queryFn: () => workspaceDocumentsApi.list(statusFilter),
  })

  const [deleteTarget, setDeleteTarget] = useState<string | null>(null)
  const [addToFolderTarget, setAddToFolderTarget] = useState<{ id: string; title: string } | null>(null)

  const createMutation = useMutation({
    mutationFn: () =>
      workspaceDocumentsApi.create({
        title: newTitle || "Sans titre",
        doc_type: newDocType,
      }),
    onSuccess: (doc) => {
      queryClient.invalidateQueries({ queryKey: ["workspace-documents"] })
      setIsCreateOpen(false)
      setNewTitle("")
      setNewDocType("generic")
      toast({ title: "Document cree", description: `"${doc.title}" a ete cree.` })
      navigate(`/app/documents/${doc.id}`)
    },
    onError: () => {
      toast({ title: "Erreur", description: "Impossible de creer le document.", variant: "destructive" })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (docId: string) => workspaceDocumentsApi.delete(docId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workspace-documents"] })
      toast({ title: "Document supprimé" })
    },
    onError: () => {
      toast({ title: "Erreur", description: "Impossible de supprimer le document.", variant: "destructive" })
    },
  })

  const duplicateMutation = useMutation({
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

  // Auto-create document from dashboard prompt
  useEffect(() => {
    const state = location.state as { prompt?: string } | null
    if (state?.prompt && !promptHandled.current) {
      promptHandled.current = true
      const prompt = state.prompt
      const docType = detectDocType(prompt)
      window.history.replaceState({}, "")
      workspaceDocumentsApi
        .create({ title: "Sans titre", doc_type: docType })
        .then((doc) => {
          queryClient.invalidateQueries({ queryKey: ["workspace-documents"] })
          navigate(`/app/documents/${doc.id}`, { state: { prompt } })
        })
        .catch(() => {
          toast({ title: "Erreur", description: "Impossible de créer le document.", variant: "destructive" })
        })
    }
  }, [location.state, navigate, queryClient, toast])

  // Contact prefill from URL param
  useEffect(() => {
    const contactId = searchParams.get("contact")
    if (contactId && !contactPrefillHandled.current) {
      contactPrefillHandled.current = true
      contactsApi
        .get(contactId)
        .then((contact) => {
          const fullName = `${contact.first_name || ""} ${contact.last_name || ""}`.trim()
          const contactName = fullName || contact.primary_email

          // Prefill title with contact name
          setNewTitle(`Document pour ${contactName}`)
          setNewDocType("generic")
          setIsCreateOpen(true)

          // Remove contact param
          searchParams.delete("contact")
          setSearchParams(searchParams, { replace: true })

          toast({
            title: "Nouveau document",
            description: `Créez un document pour ${contactName}`,
          })
        })
        .catch((err) => {
          console.error("Failed to fetch contact for document prefill:", err)
          toast({
            variant: "destructive",
            title: "Erreur",
            description: "Impossible de charger le contact.",
          })
        })
    }
  }, [searchParams, setSearchParams, toast])

  return (
    <div className="container py-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">Documents</h1>
        <Button onClick={() => setIsCreateOpen(true)}>
          <Plus className="h-4 w-4 mr-2" />
          Nouveau document
        </Button>
      </div>

      {/* Status filter tabs */}
      <Tabs
        value={statusFilter || "all"}
        onValueChange={(v) => setStatusFilter(v === "all" ? undefined : v)}
      >
        <TabsList>
          <TabsTrigger value="all">Tous</TabsTrigger>
          <TabsTrigger value="draft">Brouillons</TabsTrigger>
          <TabsTrigger value="validated">Validés</TabsTrigger>
          <TabsTrigger value="sent">Envoyés</TabsTrigger>
          <TabsTrigger value="archived">Archivés</TabsTrigger>
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

      {/* Documents grid */}
      {documents && documents.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <FileEdit className="h-12 w-12 text-muted-foreground/50 mb-4" />
          <p className="text-lg font-medium">Aucun document</p>
          <p className="text-muted-foreground mb-4">
            Creez votre premier document pour commencer.
          </p>
          <Button onClick={() => setIsCreateOpen(true)}>
            <Plus className="h-4 w-4 mr-2" />
            Creer un document
          </Button>
        </div>
      )}

      {documents && documents.length > 0 && (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {documents.map((doc: WorkspaceDocumentListItem) => {
            const isGenerating = docGen?.generatingDocIds.has(doc.id) ?? false
            return (
            <Card
              key={doc.id}
              className="relative group cursor-pointer hover:shadow-md transition-shadow"
              onClick={() => navigate(`/app/documents/${doc.id}`)}
            >
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  {isGenerating ? (
                    <Badge variant="secondary" className="gap-1.5 bg-amber-500/15 text-amber-700 dark:bg-amber-500/20 dark:text-amber-400">
                      <Loader2 className="h-3 w-3 animate-spin" />
                      En génération
                    </Badge>
                  ) : (
                    <Badge variant={STATUS_VARIANTS[doc.status] || "outline"}>
                      {STATUS_LABELS[doc.status] || doc.status}
                    </Badge>
                  )}
                  <Badge variant="outline" className="text-[10px]">
                    {DOC_TYPES.find((t) => t.value === doc.doc_type)?.label ||
                      doc.doc_type}
                  </Badge>
                </div>
                <CardTitle className="text-lg mt-2">{doc.title}</CardTitle>
                <CardDescription>
                  v{doc.version} — Modifie le{" "}
                  {new Date(doc.updated_at).toLocaleDateString("fr-FR")}
                </CardDescription>
              </CardHeader>
              <CardFooter className="text-xs text-muted-foreground">
                {isGenerating ? (
                  <span className="flex items-center gap-1.5 text-amber-600 dark:text-amber-500">
                    <Construction className="h-3 w-3" />
                    Génération en cours…
                  </span>
                ) : (
                  <>
                    Cree le{" "}
                    {new Date(doc.created_at).toLocaleDateString("fr-FR")}
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
                  <DropdownMenuItem onClick={() => setAddToFolderTarget({ id: doc.id, title: doc.title })}>
                    <FolderPlus className="h-4 w-4 mr-2" />
                    Ajouter à un dossier
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => duplicateMutation.mutate(doc.id)}>
                    <Copy className="h-4 w-4 mr-2" />
                    Dupliquer
                  </DropdownMenuItem>
                  {doc.status !== "archived" && (
                    <DropdownMenuItem onClick={() => archiveMutation.mutate(doc.id)}>
                      <Archive className="h-4 w-4 mr-2" />
                      Archiver
                    </DropdownMenuItem>
                  )}
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    className="text-destructive"
                    onClick={() => setDeleteTarget(doc.id)}
                  >
                    <Trash2 className="h-4 w-4 mr-2" />
                    Supprimer
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </Card>
          )})}
        </div>
      )}

      {/* Create dialog */}
      <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Nouveau document</DialogTitle>
            <DialogDescription>
              Creez un document vierge ou a partir d'un modele.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="title">Titre</Label>
              <Input
                id="title"
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                placeholder="Sans titre"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="doc_type">Type de document</Label>
              <Select value={newDocType} onValueChange={setNewDocType}>
                <SelectTrigger>
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
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setIsCreateOpen(false)}
            >
              Annuler
            </Button>
            <Button
              onClick={() => createMutation.mutate()}
              disabled={createMutation.isPending}
            >
              {createMutation.isPending && (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              )}
              Creer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete confirmation */}
      <AlertDialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Supprimer le document ?</AlertDialogTitle>
            <AlertDialogDescription>
              Cette action est irréversible. Le document sera définitivement supprimé.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => {
                if (deleteTarget) deleteMutation.mutate(deleteTarget)
                setDeleteTarget(null)
              }}
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
  )
}
