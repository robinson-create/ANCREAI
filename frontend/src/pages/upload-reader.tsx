import { useCallback } from "react"
import { useParams, useNavigate } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import {
  ArrowLeft,
  Download,
  FileText,
  Image,
  Loader2,
  AlertCircle,
  Eye,
  Cpu,
  Clock,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { useToast } from "@/hooks/use-toast"
import { uploadsApi } from "@/api/uploads"

export function UploadReaderPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { toast } = useToast()

  const { data: doc, isLoading, error } = useQuery({
    queryKey: ["upload", id],
    queryFn: () => uploadsApi.get(id!),
    enabled: !!id,
    refetchInterval: (query) => {
      const data = query.state.data
      if (!data) return false
      return data.status === "pending" || data.status === "processing" ? 3000 : false
    },
  })

  const handleDownload = useCallback(async () => {
    if (!id) return
    try {
      const { url } = await uploadsApi.getDownloadUrl(id)
      window.open(url, "_blank")
    } catch {
      toast({
        variant: "destructive",
        title: "Erreur",
        description: "Impossible de télécharger le fichier.",
      })
    }
  }, [id, toast])

  const isImage = doc?.content_type.startsWith("image/")
  const isProcessing = doc?.status === "pending" || doc?.status === "processing"

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-4 p-4 border-b bg-background">
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 shrink-0"
          onClick={() => navigate("/app/uploads")}
        >
          <ArrowLeft className="h-4 w-4" />
        </Button>

        <div className="flex-1 min-w-0">
          {isLoading ? (
            <Skeleton className="h-5 w-48" />
          ) : doc ? (
            <div className="flex items-center gap-2">
              {isImage ? (
                <Image className="h-4 w-4 text-muted-foreground shrink-0" />
              ) : (
                <FileText className="h-4 w-4 text-muted-foreground shrink-0" />
              )}
              <h1 className="font-heading text-lg font-semibold text-foreground truncate">
                {doc.filename}
              </h1>
            </div>
          ) : null}
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {doc && (
            <>
              {doc.ocr_used && (
                <Badge variant="outline" className="gap-1 text-xs">
                  <Eye className="h-3 w-3" />
                  OCR
                </Badge>
              )}
              {doc.parser_used !== "pending" && doc.parser_used !== "native" && (
                <Badge variant="outline" className="gap-1 text-xs">
                  <Cpu className="h-3 w-3" />
                  {doc.parser_used}
                </Badge>
              )}
            </>
          )}
          <Button
            variant="outline"
            size="sm"
            className="gap-2"
            onClick={handleDownload}
            disabled={!doc}
          >
            <Download className="h-3.5 w-3.5" />
            Télécharger
          </Button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden">
        {isLoading && (
          <div className="p-6 space-y-4">
            <Skeleton className="h-6 w-64" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
          </div>
        )}

        {error && (
          <div className="flex flex-col items-center justify-center h-full gap-3">
            <AlertCircle className="h-8 w-8 text-destructive" />
            <p className="text-sm text-destructive">Document introuvable.</p>
            <Button variant="outline" size="sm" onClick={() => navigate("/app/uploads")}>
              Retour aux uploads
            </Button>
          </div>
        )}

        {doc && isProcessing && (
          <div className="flex flex-col items-center justify-center h-full gap-4">
            <Loader2 className="h-10 w-10 animate-spin text-primary" />
            <div className="text-center">
              <p className="text-sm font-medium text-foreground">
                Traitement en cours...
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                Le document est en cours d'extraction et d'indexation.
              </p>
            </div>
          </div>
        )}

        {doc && doc.status === "failed" && (
          <div className="flex flex-col items-center justify-center h-full gap-3">
            <AlertCircle className="h-8 w-8 text-destructive" />
            <div className="text-center">
              <p className="text-sm font-medium text-destructive">
                Le traitement a échoué
              </p>
              {doc.error_message && (
                <p className="text-xs text-muted-foreground mt-1 max-w-md">
                  {doc.error_message}
                </p>
              )}
            </div>
          </div>
        )}

        {doc && doc.status === "ready" && (
          <ScrollArea className="h-full">
            <div className="max-w-4xl mx-auto p-6 space-y-6">
              {/* Document info bar */}
              <div className="flex items-center gap-3 text-xs text-muted-foreground bg-muted/30 rounded-lg px-4 py-2.5">
                <Clock className="h-3.5 w-3.5 shrink-0" />
                <span>
                  {doc.page_count} page{(doc.page_count || 0) > 1 ? "s" : ""}
                  {" — "}
                  {doc.chunk_count} chunks indexés
                  {doc.tokens_used ? ` — ${doc.tokens_used.toLocaleString()} tokens` : ""}
                </span>
                <span className="ml-auto">
                  Texte extrait automatiquement
                  {doc.ocr_used ? " (OCR)" : ""}
                </span>
              </div>

              {/* Pages */}
              {doc.pages.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-8">
                  Aucun contenu extrait pour ce document.
                </p>
              ) : (
                doc.pages.map((page, idx) => (
                  <div key={page.page_number}>
                    {idx > 0 && <Separator className="my-4" />}
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="text-[10px] px-2 py-0.5">
                          Page {page.page_number}
                        </Badge>
                        {page.meta?.parser && (
                          <span className="text-[10px] text-muted-foreground">
                            via {String(page.meta.parser)}
                          </span>
                        )}
                      </div>
                      <div className="prose prose-sm max-w-none dark:prose-invert font-body text-sm leading-relaxed whitespace-pre-wrap">
                        {page.text}
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </ScrollArea>
        )}
      </div>
    </div>
  )
}
