import { useState, useCallback, useMemo, useRef } from "react"
import { useParams, useNavigate } from "react-router-dom"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  ArrowLeft,
  Loader2,
  AlertCircle,
  Download,
  Palette,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Skeleton } from "@/components/ui/skeleton"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useToast } from "@/hooks/use-toast"
import { usePresentationSSE } from "@/hooks/use-presentation-sse"
import { presentationsApi } from "@/api/presentations"
import { AnchorSpinner } from "@/components/documents/AnchorSpinner"
// OutlineEditor removed — auto-chain outline → slides, no intermediate review
import { SlidePanel } from "@/components/presentation/SlidePanel"
import { SlideEditor } from "@/components/presentation/SlideEditor"
// InstructionBar removed per user request
import { ThemePanel } from "@/components/presentation/ThemePanel"
import type {
  PresentationFull,
  PresentationStatus,
  PresentationSSEEvent,
  SlideUpdate,
} from "@/types"

// ── Status labels ──

const STATUS_LABELS: Record<PresentationStatus, string> = {
  draft: "Brouillon",
  generating_outline: "Génération...",
  outline_ready: "Génération...",
  generating_slides: "Génération des slides...",
  ready: "Prêt",
  exporting: "Export en cours...",
  error: "Erreur",
}

const STATUS_VARIANTS: Record<
  PresentationStatus,
  "default" | "secondary" | "outline" | "destructive"
> = {
  draft: "outline",
  generating_outline: "secondary",
  outline_ready: "secondary",
  generating_slides: "secondary",
  ready: "default",
  exporting: "secondary",
  error: "destructive",
}

// Step-by-step labels for the generation loading screen
const GENERATION_STEPS = [
  { key: "split", label: "Découpage du contenu en sections" },
  { key: "slides", label: "Génération des slides" },
  { key: "finalize", label: "Finalisation" },
] as const

// ── Main page ──

export function PresentationEditorPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { toast } = useToast()

  // ── Server state ──
  const {
    data: presentation,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["presentation", id],
    queryFn: () => presentationsApi.get(id!),
    enabled: !!id,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (
        status === "generating_outline" ||
        status === "outline_ready" ||
        status === "generating_slides" ||
        status === "exporting"
      )
        return 3000 // Poll faster for better UX during generation
      return false
    },
  })

  // ── Local UI state ──
  const [title, setTitle] = useState("")
  const [selectedSlideId, setSelectedSlideId] = useState<string | null>(null)
  const [exportProgress, setExportProgress] = useState<number | undefined>()
  // regeneratingSlideId removed — InstructionBar removed
  const [slideGenProgress, setSlideGenProgress] = useState<{ current: number; total: number } | null>(null)
  const [showThemePanel, setShowThemePanel] = useState(false)
  const titleInitialized = useRef(false)

  // Sync title from server on first load + when status transitions to ready
  if (presentation && !titleInitialized.current) {
    setTitle(presentation.title)
    titleInitialized.current = true
  }
  // Auto-select first slide when slides become available
  if (presentation && presentation.slides.length > 0 && !selectedSlideId) {
    const firstId =
      presentation.slide_order[0] || presentation.slides[0]?.id
    if (firstId) setSelectedSlideId(firstId)
  }
  // Sync title when it changes from server (e.g. after outline generation sets a title)
  if (presentation && titleInitialized.current && title === "Sans titre" && presentation.title !== "Sans titre") {
    setTitle(presentation.title)
  }

  // ── SSE for generation tracking ──
  const isGenerating =
    presentation?.status === "generating_outline" ||
    presentation?.status === "outline_ready" ||
    presentation?.status === "generating_slides" ||
    presentation?.status === "exporting"

  // Track current generation step for step-by-step display
  const [generationStep, setGenerationStep] = useState<"split" | "slides" | "finalize" | null>(null)

  // Auto-set step based on status
  if (isGenerating && !generationStep && !slideGenProgress) {
    if (presentation?.status === "generating_slides" || presentation?.status === "generating_outline") {
      setGenerationStep("split")
    }
  }

  const handleSSEEvent = useCallback(
    (event: PresentationSSEEvent) => {
      console.log('[SSE]', event.type, event.payload)
      switch (event.type) {
        case "outline_ready":
        case "generation_complete":
        case "export_ready":
          queryClient.invalidateQueries({ queryKey: ["presentation", id] })
          if (event.type === "generation_complete") {
            setGenerationStep("finalize")
            // Small delay to show "Finalisation" before clearing
            setTimeout(() => {
              setSlideGenProgress(null)
              setGenerationStep(null)
            }, 800)
          }
          if (event.type === "export_ready") {
            toast({ title: "Export terminé", description: "Votre présentation est prête." })
          }
          break
        case "slide_generated":
          setGenerationStep("slides")
          setSlideGenProgress({
            current: (event.payload.slide_index as number) + 1,
            total: event.payload.total as number,
          })
          queryClient.invalidateQueries({ queryKey: ["presentation", id] })
          break
        case "export_progress":
          setExportProgress(event.payload.percent as number)
          break
        case "error":
          setGenerationStep(null)
          setSlideGenProgress(null)
          queryClient.invalidateQueries({ queryKey: ["presentation", id] })
          toast({
            title: "Erreur de génération",
            description: (event.payload.message as string) || "Une erreur est survenue.",
            variant: "destructive",
          })
          break
      }
    },
    [id, queryClient, toast],
  )

  usePresentationSSE({
    presentationId: id,
    enabled: !!isGenerating,
    onEvent: handleSSEEvent,
  })

  // ── Mutations ──

  const titleMutation = useMutation({
    mutationFn: (newTitle: string) =>
      presentationsApi.update(id!, { title: newTitle }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["presentation", id] }),
  })

  // outlineSaveMutation and generateSlidesMutation removed — auto-chain handles both

  const slideUpdateMutation = useMutation({
    mutationFn: ({ slideId, update }: { slideId: string; update: SlideUpdate }) =>
      presentationsApi.updateSlide(id!, slideId, update),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["presentation", id] }),
  })

  // regenerateSlideMutation removed — InstructionBar removed

  const addSlideMutation = useMutation({
    mutationFn: () => presentationsApi.addSlide(id!),
    onSuccess: (newSlide) => {
      queryClient.invalidateQueries({ queryKey: ["presentation", id] })
      setSelectedSlideId(newSlide.id)
    },
  })

  const deleteSlideMutation = useMutation({
    mutationFn: (slideId: string) => presentationsApi.deleteSlide(id!, slideId),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["presentation", id] }),
  })

  const reorderMutation = useMutation({
    mutationFn: ({ slideId, direction }: { slideId: string; direction: "up" | "down" }) => {
      if (!presentation) return Promise.resolve(null)
      const order = [...presentation.slide_order]
      const idx = order.indexOf(slideId)
      const target = direction === "up" ? idx - 1 : idx + 1
      if (target < 0 || target >= order.length) return Promise.resolve(null)
      const temp = order[idx]!
      order[idx] = order[target]!
      order[target] = temp
      return presentationsApi.reorderSlides(id!, order)
    },
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["presentation", id] }),
  })

  const exportMutation = useMutation({
    mutationFn: (format: "pptx" | "pdf") =>
      presentationsApi.exportPresentation(id!, { format }),
    onSuccess: () => {
      setExportProgress(0)
      queryClient.invalidateQueries({ queryKey: ["presentation", id] })
      toast({ title: "Export lancé", description: "La génération du fichier est en cours." })
    },
    onError: () =>
      toast({
        title: "Erreur",
        description: "Impossible de lancer l'export.",
        variant: "destructive",
      }),
  })

  // ── Handlers ──

  const handleTitleBlur = useCallback(() => {
    if (title !== presentation?.title) {
      titleMutation.mutate(title)
    }
  }, [title, presentation?.title, titleMutation])

  const handleSlideUpdate = useCallback(
    (slideId: string, update: SlideUpdate) => {
      slideUpdateMutation.mutate({ slideId, update })
    },
    [slideUpdateMutation],
  )

  const handleDeleteSlide = useCallback(
    (slideId: string) => {
      if (slideId === selectedSlideId && presentation) {
        const order = presentation.slide_order
        const idx = order.indexOf(slideId)
        const nextId = order[idx + 1] || order[idx - 1] || null
        setSelectedSlideId(nextId)
      }
      deleteSlideMutation.mutate(slideId)
    },
    [selectedSlideId, presentation, deleteSlideMutation],
  )

  // ── Derived data ──

  const selectedSlide = useMemo(() => {
    if (!presentation || !selectedSlideId) return null
    const slide = presentation.slides.find((s) => s.id === selectedSlideId) || null
    if (slide) {
      console.log('[Slide] Selected:', slide.id, 'layout:', slide.layout_type, 'content keys:', Object.keys(slide.content_json || {}))
    }
    return slide
  }, [presentation, selectedSlideId])

  // ── Loading / Error ──

  if (isLoading) {
    return (
      <div className="flex flex-col h-full">
        <div className="flex items-center gap-3 px-4 py-3 border-b">
          <Skeleton className="h-8 w-8" />
          <Skeleton className="h-8 w-48" />
        </div>
        <div className="flex-1 flex items-center justify-center">
          <Skeleton className="w-96 h-64" />
        </div>
      </div>
    )
  }

  if (error || !presentation) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4">
        <AlertCircle className="h-8 w-8 text-destructive" />
        <p className="text-muted-foreground">Présentation introuvable.</p>
        <Button variant="ghost" onClick={() => navigate("/app/documents")}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Retour aux documents
        </Button>
      </div>
    )
  }

  // ── Phase renderer ──

  function renderPhase(pres: PresentationFull) {
    switch (pres.status) {
      case "draft":
        return (
          <div className="relative flex-1">
            <AnchorSpinner active className="relative h-full" label="Lancement de la génération..." />
          </div>
        )
      case "generating_outline":
      case "outline_ready":
      case "generating_slides":
        return (
          <div className="relative flex-1">
            <AnchorSpinner active className="relative h-full" label={null} />
            {/* Step-by-step progress overlay */}
            <div className="absolute inset-x-0 bottom-0 z-30 flex flex-col items-center gap-4 pb-16">
              {/* Steps indicator */}
              <div className="flex flex-col gap-2 w-72">
                {GENERATION_STEPS.map((step) => {
                  const currentIdx = GENERATION_STEPS.findIndex(
                    (s) => s.key === generationStep,
                  )
                  const stepIdx = GENERATION_STEPS.findIndex((s) => s.key === step.key)
                  const isActive = step.key === generationStep
                  const isDone = currentIdx > stepIdx

                  return (
                    <div
                      key={step.key}
                      className={`flex items-center gap-2.5 text-sm transition-opacity ${
                        isActive
                          ? "text-foreground font-medium"
                          : isDone
                            ? "text-muted-foreground/60"
                            : "text-muted-foreground/40"
                      }`}
                    >
                      <div
                        className={`h-2 w-2 rounded-full shrink-0 transition-colors ${
                          isActive
                            ? "bg-primary animate-pulse"
                            : isDone
                              ? "bg-primary/40"
                              : "bg-muted-foreground/20"
                        }`}
                      />
                      <span>{step.label}</span>
                      {isActive && step.key === "slides" && slideGenProgress && (
                        <span className="ml-auto tabular-nums text-xs text-muted-foreground">
                          {slideGenProgress.current}/{slideGenProgress.total}
                        </span>
                      )}
                    </div>
                  )
                })}
              </div>
              {/* Progress bar for slides */}
              {slideGenProgress && (
                <Progress
                  value={
                    (slideGenProgress.current / slideGenProgress.total) * 100
                  }
                  className="w-72 h-1.5"
                />
              )}
              <p className="text-xs text-muted-foreground">
                Vous pouvez revenir à l'accueil, la génération continue en arrière-plan.
              </p>
            </div>
          </div>
        )

      case "ready":
      case "exporting":
        return (
          <div className="flex flex-1 overflow-hidden">
            <SlidePanel
              slides={pres.slides}
              slideOrder={pres.slide_order}
              selectedSlideId={selectedSlideId}
              themeData={pres.theme?.theme_data}
              footer={pres.settings?.footer}
              onSelectSlide={setSelectedSlideId}
              onAddSlide={() => addSlideMutation.mutate()}
              onDeleteSlide={handleDeleteSlide}
              onMoveSlide={(slideId, direction) =>
                reorderMutation.mutate({ slideId, direction })
              }
            />
            <div className="flex-1 min-w-0">
              {selectedSlide ? (
                <SlideEditor
                  presentationId={pres.id}
                  slide={selectedSlide}
                  themeData={pres.theme?.theme_data ?? null}
                  footer={pres.settings?.footer}
                  onSlideUpdate={handleSlideUpdate}
                />
              ) : (
                <div className="flex items-center justify-center h-full text-muted-foreground">
                  Sélectionnez un slide dans le panneau de gauche
                </div>
              )}
            </div>
            {showThemePanel && (
              <ThemePanel
                presentationId={pres.id}
                currentThemeId={pres.theme_id}
                onClose={() => setShowThemePanel(false)}
              />
            )}
            {/* InstructionBar removed */}
          </div>
        )

      case "error":
        return (
          <div className="flex flex-col items-center justify-center h-full gap-4">
            <AlertCircle className="h-8 w-8 text-destructive" />
            <p className="text-muted-foreground">
              {pres.error_message || "Une erreur est survenue lors de la génération."}
            </p>
            <Button variant="outline" onClick={() => navigate("/app/documents")}>
              Retour aux documents
            </Button>
          </div>
        )

      default:
        return null
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Top bar */}
      <div className="flex items-center gap-2 px-4 py-2 border-b bg-card shrink-0 flex-nowrap overflow-x-auto">
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
          className="text-base font-semibold border-0 shadow-none bg-transparent h-auto py-1 px-2 focus-visible:ring-1 max-w-sm"
          placeholder="Sans titre"
        />

        <Badge variant={STATUS_VARIANTS[presentation.status]}>
          {STATUS_LABELS[presentation.status]}
        </Badge>

        <div className="flex-1" />

        {/* Action buttons (only when ready) — all on same line */}
        {presentation.status === "ready" && (
          <>
            <Button
              variant={showThemePanel ? "default" : "outline"}
              size="sm"
              className="gap-1.5 shrink-0"
              onClick={() => setShowThemePanel(!showThemePanel)}
            >
              <Palette className="h-3.5 w-3.5" />
              Thème
            </Button>
          </>
        )}

        {/* Export button (only when ready) */}
        {presentation.status === "ready" && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" className="gap-1.5">
                <Download className="h-3.5 w-3.5" />
                Exporter
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => exportMutation.mutate("pptx")}>
                PowerPoint (.pptx)
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => exportMutation.mutate("pdf")}>
                PDF
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        )}

        {presentation.status === "exporting" && exportProgress !== undefined && (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            Export {Math.round(exportProgress)}%
          </div>
        )}
      </div>

      {/* Phase content */}
      <div className="flex-1 overflow-hidden flex flex-col">
        {renderPhase(presentation)}
      </div>
    </div>
  )
}
