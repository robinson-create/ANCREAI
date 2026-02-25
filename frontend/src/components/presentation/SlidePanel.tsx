import { useMemo } from "react"
import { ChevronUp, ChevronDown, Plus, Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { SlidePreviewCard } from "./SlidePreviewCard"
import type { Slide } from "@/types"

interface SlidePanelProps {
  slides: Slide[]
  slideOrder: string[]
  selectedSlideId: string | null
  onSelectSlide: (id: string) => void
  onAddSlide: () => void
  onDeleteSlide: (id: string) => void
  onMoveSlide: (id: string, direction: "up" | "down") => void
}

export function SlidePanel({
  slides,
  slideOrder,
  selectedSlideId,
  onSelectSlide,
  onAddSlide,
  onDeleteSlide,
  onMoveSlide,
}: SlidePanelProps) {
  const orderedSlides = useMemo(() => {
    const map = new Map(slides.map((s) => [s.id, s]))
    return slideOrder.map((id) => map.get(id)).filter(Boolean) as Slide[]
  }, [slides, slideOrder])

  return (
    <div className="w-56 border-r bg-card flex flex-col shrink-0">
      <div className="px-3 py-2 border-b">
        <p className="text-xs font-medium text-muted-foreground">
          {orderedSlides.length} slide{orderedSlides.length > 1 ? "s" : ""}
        </p>
      </div>

      <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
        {orderedSlides.map((slide, idx) => (
          <div key={slide.id} className="group relative">
            <SlidePreviewCard
              slide={slide}
              index={idx}
              isSelected={slide.id === selectedSlideId}
              onClick={() => onSelectSlide(slide.id)}
            />

            {/* Hover actions */}
            <div className="absolute top-1 right-1 hidden group-hover:flex gap-0.5 bg-background/90 rounded p-0.5">
              <Button
                variant="ghost"
                size="icon"
                className="h-5 w-5"
                disabled={idx === 0}
                onClick={(e) => {
                  e.stopPropagation()
                  onMoveSlide(slide.id, "up")
                }}
              >
                <ChevronUp className="h-3 w-3" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-5 w-5"
                disabled={idx === orderedSlides.length - 1}
                onClick={(e) => {
                  e.stopPropagation()
                  onMoveSlide(slide.id, "down")
                }}
              >
                <ChevronDown className="h-3 w-3" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-5 w-5 text-muted-foreground hover:text-destructive"
                onClick={(e) => {
                  e.stopPropagation()
                  onDeleteSlide(slide.id)
                }}
              >
                <Trash2 className="h-3 w-3" />
              </Button>
            </div>
          </div>
        ))}
      </div>

      <div className="p-2 border-t">
        <Button
          variant="outline"
          size="sm"
          className="w-full"
          onClick={onAddSlide}
        >
          <Plus className="h-3.5 w-3.5 mr-1.5" />
          Ajouter un slide
        </Button>
      </div>
    </div>
  )
}
