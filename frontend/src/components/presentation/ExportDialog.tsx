import { useState, useCallback } from "react"
import { useMutation } from "@tanstack/react-query"
import {
  Download,
  FileText,
  Loader2,
  CheckCircle2,
  AlertCircle,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Badge } from "@/components/ui/badge"
import { usePresentationSSE } from "@/hooks/use-presentation-sse"
import { presentationsApi } from "@/api/presentations"
import type { PresentationSSEEvent } from "@/types"

interface ExportDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  presentationId: string
}

type ExportPhase = "select" | "exporting" | "done" | "error"

export function ExportDialog({
  open,
  onOpenChange,
  presentationId,
}: ExportDialogProps) {
  const [phase, setPhase] = useState<ExportPhase>("select")
  const [format, setFormat] = useState<"pptx" | "pdf">("pptx")
  const [progress, setProgress] = useState(0)
  const [exportId, setExportId] = useState<string | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const exportMutation = useMutation({
    mutationFn: (fmt: "pptx" | "pdf") =>
      presentationsApi.exportPresentation(presentationId, { format: fmt }),
    onSuccess: (data) => {
      setExportId(data.export_id)
      setPhase("exporting")
      setProgress(0)
    },
    onError: () => {
      setPhase("error")
      setErrorMessage("Impossible de lancer l'export.")
    },
  })

  const handleSSEEvent = useCallback(
    (event: PresentationSSEEvent) => {
      if (event.type === "export_progress") {
        setProgress(event.payload.percent as number)
      } else if (event.type === "export_ready") {
        setExportId(event.payload.export_id as string)
        setPhase("done")
      } else if (event.type === "error") {
        setPhase("error")
        setErrorMessage(
          (event.payload.message as string) || "Erreur lors de l'export.",
        )
      }
    },
    [],
  )

  usePresentationSSE({
    presentationId,
    enabled: phase === "exporting",
    onEvent: handleSSEEvent,
  })

  const handleDownload = async () => {
    if (!exportId) return
    try {
      const { url } = await presentationsApi.getExportDownloadUrl(
        presentationId,
        exportId,
      )
      window.open(url, "_blank")
    } catch {
      setPhase("error")
      setErrorMessage("Impossible de récupérer le lien de téléchargement.")
    }
  }

  const handleClose = (isOpen: boolean) => {
    if (!isOpen && phase !== "exporting") {
      setPhase("select")
      setFormat("pptx")
      setProgress(0)
      setExportId(null)
      setErrorMessage(null)
    }
    if (phase !== "exporting") {
      onOpenChange(isOpen)
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-md">
        {/* ── Phase: select ── */}
        {phase === "select" && (
          <>
            <DialogHeader>
              <DialogTitle>Exporter la présentation</DialogTitle>
              <DialogDescription>
                Choisissez le format d'export.
              </DialogDescription>
            </DialogHeader>

            <div className="flex flex-col gap-2 py-2">
              {/* PowerPoint option */}
              <button
                type="button"
                onClick={() => setFormat("pptx")}
                className={`flex items-center gap-3 rounded-lg border p-3 text-left transition-colors ${
                  format === "pptx"
                    ? "border-primary bg-primary/5"
                    : "border-border hover:bg-muted/50"
                }`}
              >
                <FileText className="h-5 w-5 shrink-0 text-orange-500" />
                <div className="flex-1">
                  <div className="text-sm font-medium">PowerPoint (.pptx)</div>
                  <div className="text-xs text-muted-foreground">
                    Compatible Microsoft Office et Google Slides
                  </div>
                </div>
              </button>

              {/* PDF option — disabled */}
              <button
                type="button"
                disabled
                className="flex items-center gap-3 rounded-lg border border-border p-3 text-left opacity-50 cursor-not-allowed"
              >
                <FileText className="h-5 w-5 shrink-0 text-red-500" />
                <div className="flex-1">
                  <div className="flex items-center gap-2 text-sm font-medium">
                    PDF
                    <Badge
                      variant="secondary"
                      className="text-[10px] px-1.5 py-0"
                    >
                      Bientôt
                    </Badge>
                  </div>
                  <div className="text-xs text-muted-foreground">
                    Document non modifiable
                  </div>
                </div>
              </button>
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={() => handleClose(false)}>
                Annuler
              </Button>
              <Button
                onClick={() => exportMutation.mutate(format)}
                disabled={exportMutation.isPending}
              >
                {exportMutation.isPending && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                Générer
              </Button>
            </DialogFooter>
          </>
        )}

        {/* ── Phase: exporting ── */}
        {phase === "exporting" && (
          <>
            <DialogHeader>
              <DialogTitle>Export en cours...</DialogTitle>
            </DialogHeader>

            <div className="flex flex-col items-center gap-4 py-6">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
              <Progress value={progress} className="w-full" />
              <p className="text-sm text-muted-foreground">
                Génération du fichier... {Math.round(progress)}%
              </p>
            </div>
          </>
        )}

        {/* ── Phase: done ── */}
        {phase === "done" && (
          <>
            <DialogHeader>
              <DialogTitle>Export terminé</DialogTitle>
            </DialogHeader>

            <div className="flex flex-col items-center gap-3 py-6">
              <CheckCircle2 className="h-10 w-10 text-green-500" />
              <p className="text-sm text-muted-foreground">
                Votre fichier est prêt.
              </p>
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={() => handleClose(false)}>
                Fermer
              </Button>
              <Button onClick={handleDownload} className="gap-1.5">
                <Download className="h-4 w-4" />
                Télécharger
              </Button>
            </DialogFooter>
          </>
        )}

        {/* ── Phase: error ── */}
        {phase === "error" && (
          <>
            <DialogHeader>
              <DialogTitle>Erreur</DialogTitle>
            </DialogHeader>

            <div className="flex flex-col items-center gap-3 py-6">
              <AlertCircle className="h-10 w-10 text-destructive" />
              <p className="text-sm text-muted-foreground text-center">
                {errorMessage || "Une erreur est survenue lors de l'export."}
              </p>
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={() => handleClose(false)}>
                Fermer
              </Button>
              <Button
                onClick={() => {
                  setPhase("select")
                  setErrorMessage(null)
                }}
              >
                Réessayer
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}
