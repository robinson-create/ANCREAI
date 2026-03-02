import { useMemo } from "react"
import { cn } from "@/lib/utils"
import {
  SLIDE_REF_WIDTH, SLIDE_REF_HEIGHT,
  DEFAULT_THEME,
  buildThemeCSSVars,
} from "./SlideRenderer"
import SlideTemplateRenderer from "./SlideTemplateRenderer"
import type { Slide, ThemeData, FooterConfig } from "@/types"

interface SlidePreviewCardProps {
  slide: Slide
  index: number
  isSelected: boolean
  onClick: () => void
  themeData?: ThemeData | null
  footer?: FooterConfig | null
}

// Thumbnail renders a 960x540 canvas scaled down to this width
const THUMB_WIDTH = 180
const THUMB_SCALE = THUMB_WIDTH / SLIDE_REF_WIDTH
const THUMB_HEIGHT = SLIDE_REF_HEIGHT * THUMB_SCALE

export function SlidePreviewCard({
  slide,
  index,
  isSelected,
  onClick,
  themeData,
}: SlidePreviewCardProps) {
  const theme = themeData ?? DEFAULT_THEME
  const cssVars = useMemo(() => buildThemeCSSVars(theme), [theme])

  const data = (
    typeof slide.content_json === 'object' && !Array.isArray(slide.content_json)
      ? slide.content_json
      : {}
  ) as Record<string, any>

  return (
    <button
      onClick={onClick}
      className={cn(
        "w-full text-left group relative",
        "rounded-lg border-2 transition-all",
        isSelected
          ? "border-primary ring-1 ring-primary/20"
          : "border-border hover:border-primary/40",
      )}
    >
      <div className="flex items-center gap-2 p-1.5">
        <span className="text-[10px] text-muted-foreground font-medium w-4 shrink-0 text-center">
          {index + 1}
        </span>

        {/* Outer container clips to thumbnail size */}
        <div
          className="overflow-hidden rounded"
          style={{ width: THUMB_WIDTH, height: THUMB_HEIGHT }}
        >
          {/* Inner: full 960x540 canvas scaled down */}
          <div
            className="overflow-hidden relative pointer-events-none"
            style={{
              width: SLIDE_REF_WIDTH,
              height: SLIDE_REF_HEIGHT,
              transform: `scale(${THUMB_SCALE})`,
              transformOrigin: "top left",
              ...cssVars,
            }}
          >
            <SlideTemplateRenderer
              layoutType={slide.layout_type}
              data={data}
            />
          </div>
        </div>
      </div>
    </button>
  )
}
