import { useState, useRef, useCallback, useMemo } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "react-router-dom"
import {
  Upload,
  FileText,
  Image,
  FileSpreadsheet,
  Presentation,
  Loader2,
  AlertCircle,
  CheckCircle2,
  Clock,
  Trash2,
  Download,
  Eye,
  RotateCcw,
  MoreVertical,
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
import { useToast } from "@/hooks/use-toast"
import { uploadsApi } from "@/api/uploads"
import type { UploadDocument } from "@/types"

// ── Helpers ──

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} o`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} Ko`
  return `${(bytes / (1024 * 1024)).toFixed(1)} Mo`
}

function getFileIcon(contentType: string) {
  if (contentType.startsWith("image/")) return Image
  if (contentType.includes("spreadsheet") || contentType.includes("excel")) return FileSpreadsheet
  if (contentType.includes("presentation") || contentType.includes("powerpoint")) return Presentation
  return FileText
}

function getFileTypeBadge(contentType: string, filename: string): string {
  if (contentType === "application/pdf") return "PDF"
  if (contentType.startsWith("image/")) return "Image"
  if (contentType.includes("wordprocessing") || filename.endsWith(".docx")) return "Word"
  if (contentType.includes("spreadsheet") || filename.endsWith(".xlsx")) return "Excel"
  if (contentType.includes("presentation") || filename.endsWith(".pptx")) return "PowerPoint"
  if (contentType === "text/html") return "HTML"
  if (contentType === "text/markdown") return "Markdown"
  if (contentType === "text/plain") return "Texte"
  return "Fichier"
}

const STATUS_CONFIG: Record<string, { label: string; variant: "default" | "secondary" | "outline" | "destructive"; icon: typeof CheckCircle2 }> = {
  pending: { label: "En attente", variant: "outline", icon: Clock },
  processing: { label: "Traitement...", variant: "secondary", icon: Loader2 },
  ready: { label: "Prêt", variant: "default", icon: CheckCircle2 },
  failed: { label: "Erreur", variant: "destructive", icon: AlertCircle },
}

const ACCEPTED_TYPES = ".pdf,.jpg,.jpeg,.png,.tiff,.tif,.webp,.bmp,.docx,.xlsx,.pptx,.txt,.html,.htm,.md"

// ── Component ──

export function UploadsPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [isDragOver, setIsDragOver] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null)

  // ── Query ──

  const { data: documents, isLoading, error } = useQuery({
    queryKey: ["uploads"],
    queryFn: () => uploadsApi.list(),
    refetchInterval: (query) => {
      const data = query.state.data
      if (!data) return false
      const hasProcessing = data.some(
        (d) => d.status === "pending" || d.status === "processing"
      )
      return hasProcessing ? 3000 : false
    },
  })

  // ── Mutations ──

  const uploadMutation = useMutation({
    mutationFn: (files: File[]) => uploadsApi.upload(files),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["uploads"] })
      toast({ title: "Fichiers importés", description: "Le traitement a démarré." })
    },
    onError: () => {
      toast({
        variant: "destructive",
        title: "Erreur",
        description: "Impossible d'importer les fichiers.",
      })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => uploadsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["uploads"] })
      toast({ title: "Document supprimé" })
    },
    onError: () => {
      toast({
        variant: "destructive",
        title: "Erreur",
        description: "Impossible de supprimer le document.",
      })
    },
  })

  const reprocessMutation = useMutation({
    mutationFn: (id: string) => uploadsApi.reprocess(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["uploads"] })
      toast({ title: "Relance du traitement" })
    },
  })

  // ── File handling ──

  const handleFiles = useCallback(
    (files: FileList | File[]) => {
      const fileArray = Array.from(files)
      if (fileArray.length > 0) {
        uploadMutation.mutate(fileArray)
      }
    },
    [uploadMutation]
  )

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(false)
  }, [])

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setIsDragOver(false)
      if (e.dataTransfer.files.length > 0) {
        handleFiles(e.dataTransfer.files)
      }
    },
    [handleFiles]
  )

  const handleDownload = useCallback(async (id: string) => {
    try {
      const { url } = await uploadsApi.getDownloadUrl(id)
      window.open(url, "_blank")
    } catch {
      toast({
        variant: "destructive",
        title: "Erreur",
        description: "Impossible de générer le lien de téléchargement.",
      })
    }
  }, [toast])

  // ── Sorted documents ──

  const sortedDocs = useMemo(() => {
    if (!documents) return []
    return [...documents].sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    )
  }, [documents])

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between p-6 border-b bg-background">
        <div>
          <h1 className="font-heading text-2xl font-bold tracking-tight text-foreground">
            Uploads
          </h1>
          <p className="text-sm text-muted-foreground font-body mt-1">
            Importez vos documents pour les rendre accessibles au RAG.
          </p>
        </div>
        <Button
          onClick={() => fileInputRef.current?.click()}
          className="gap-2"
          disabled={uploadMutation.isPending}
        >
          {uploadMutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Upload className="h-4 w-4" />
          )}
          Importer
        </Button>
      </div>

      <div className="flex-1 overflow-auto p-6 space-y-6">
        {/* Drop zone */}
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`
            flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed
            p-8 cursor-pointer transition-all
            ${isDragOver
              ? "border-primary bg-primary/5 scale-[1.01]"
              : "border-border hover:border-primary/40 hover:bg-muted/30"
            }
          `}
        >
          <Upload className={`h-8 w-8 ${isDragOver ? "text-primary" : "text-muted-foreground/50"}`} />
          <div className="text-center">
            <p className="text-sm font-medium text-foreground">
              {isDragOver ? "Déposez vos fichiers ici" : "Glissez-déposez ou cliquez pour importer"}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              PDF, images, Word, Excel, PowerPoint, texte
            </p>
          </div>
        </div>

        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept={ACCEPTED_TYPES}
          className="hidden"
          onChange={(e) => {
            if (e.target.files) {
              handleFiles(e.target.files)
              e.target.value = ""
            }
          }}
        />

        {/* Loading */}
        {isLoading && (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-36 rounded-lg" />
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
        {!isLoading && !error && sortedDocs.length === 0 && (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <Upload className="h-12 w-12 text-muted-foreground/50 mb-4" />
            <p className="text-lg font-semibold font-heading text-foreground">
              Aucun document importé
            </p>
            <p className="text-sm text-muted-foreground mb-4 font-body">
              Importez vos premiers fichiers pour enrichir votre base de connaissances.
            </p>
          </div>
        )}

        {/* Document grid */}
        {sortedDocs.length > 0 && (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {sortedDocs.map((doc) => {
              const FileIcon = getFileIcon(doc.content_type)
              const statusCfg = STATUS_CONFIG[doc.status] || STATUS_CONFIG.pending
              const StatusIcon = statusCfg.icon
              const isProcessing = doc.status === "pending" || doc.status === "processing"

              return (
                <Card
                  key={doc.id}
                  className="relative group cursor-pointer hover:shadow-lg hover:border-primary/20 transition-all rounded-xl border-border"
                  onClick={() => navigate(`/app/uploads/${doc.id}`)}
                >
                  <CardHeader className="pb-2">
                    <div className="flex items-center justify-between gap-2">
                      <Badge variant={statusCfg.variant} className="gap-1.5 font-medium">
                        <StatusIcon className={`h-3 w-3 ${isProcessing ? "animate-spin" : ""}`} />
                        {statusCfg.label}
                      </Badge>
                      <div className="flex items-center gap-1.5">
                        <Badge variant="outline" className="text-[10px] font-medium px-2 py-0.5 gap-1 flex items-center">
                          <FileIcon className="h-3 w-3" />
                          {getFileTypeBadge(doc.content_type, doc.filename)}
                        </Badge>
                        {doc.ocr_used && (
                          <Badge variant="outline" className="text-[10px] font-medium px-2 py-0.5">
                            OCR
                          </Badge>
                        )}
                      </div>
                    </div>
                    <CardTitle className="font-heading text-sm mt-2 text-foreground truncate">
                      {doc.filename}
                    </CardTitle>
                    <CardDescription className="font-body text-xs">
                      {formatFileSize(doc.file_size)}
                      {doc.page_count ? ` — ${doc.page_count} page${doc.page_count > 1 ? "s" : ""}` : ""}
                      {doc.chunk_count ? ` — ${doc.chunk_count} chunks` : ""}
                    </CardDescription>
                  </CardHeader>
                  <CardFooter className="text-xs text-muted-foreground font-body">
                    {doc.parser_used !== "pending" && doc.parser_used !== "native" && (
                      <span className="mr-2 text-muted-foreground/60">
                        Parser: {doc.parser_used}
                      </span>
                    )}
                    Importé le {new Date(doc.created_at).toLocaleDateString("fr-FR")}
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
                      <DropdownMenuItem onClick={() => navigate(`/app/uploads/${doc.id}`)}>
                        <Eye className="h-4 w-4 mr-2" />
                        Voir
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => handleDownload(doc.id)}>
                        <Download className="h-4 w-4 mr-2" />
                        Télécharger
                      </DropdownMenuItem>
                      {doc.status === "failed" && (
                        <DropdownMenuItem onClick={() => reprocessMutation.mutate(doc.id)}>
                          <RotateCcw className="h-4 w-4 mr-2" />
                          Relancer
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
              )
            })}
          </div>
        )}
      </div>

      {/* Delete confirmation */}
      <AlertDialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Supprimer ce document ?</AlertDialogTitle>
            <AlertDialogDescription>
              Cette action est irréversible. Le document sera supprimé du stockage,
              de l'index et de la base de connaissances.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => {
                if (deleteTarget) {
                  deleteMutation.mutate(deleteTarget)
                  setDeleteTarget(null)
                }
              }}
            >
              Supprimer
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
