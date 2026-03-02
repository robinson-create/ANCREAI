import { useMemo } from "react"
import { cn } from "@/lib/utils"
import {
  SLIDE_REF_WIDTH, SLIDE_REF_HEIGHT, CARD_INNER_MAX,
  DEFAULT_THEME,
  buildThemeCSSVars, buildSizingCSSVars, resolveChartColors,
  SlideNodeRenderer,
} from "./SlideRenderer"
import type { Slide, SlideNode, ThemeData } from "@/types"

interface SlidePreviewCardProps {
  slide: Slide
  index: number
  isSelected: boolean
  onClick: () => void
  themeData?: ThemeData | null
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
  const sizingVars = useMemo(() => buildSizingCSSVars(slide.sizing), [slide.sizing])
  const chartColors = useMemo(() => resolveChartColors(theme), [theme])

  const contentNodes = (
    slide.content_json?.content_json ||
    (Array.isArray(slide.content_json) ? slide.content_json : [])
  ) as SlideNode[]

  const slideBg = slide.bg_color && slide.bg_color !== "#ffffff"
    ? slide.bg_color
    : theme.colors.background

  const rootImage = slide.root_image as { url?: string; asset_id?: string } | null
  const rootImageUrl = rootImage?.url || rootImage?.asset_id || null

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
              ...sizingVars,
              backgroundColor: slideBg,
              color: "var(--pres-text)",
              fontFamily: "var(--pres-body-font)",
            }}
          >
            {/* Background image */}
            {rootImageUrl && slide.layout_type === "background" && (
              <>
                <img src={rootImageUrl} alt="" className="absolute inset-0 w-full h-full object-cover" />
                <div className="absolute inset-0 bg-black/40" />
              </>
            )}

            {/* Layout with side image */}
            {rootImageUrl && ["left", "right", "left-fit", "right-fit"].includes(slide.layout_type) ? (
              <div className={`flex h-full ${slide.layout_type.startsWith("right") ? "flex-row" : "flex-row-reverse"}`}>
                <div
                  className="flex-1 overflow-hidden"
                  style={{ padding: "20px", maxWidth: CARD_INNER_MAX[slide.sizing?.card_width ?? "M"] }}
                >
                  {contentNodes.map((node, i) => (
                    <SlideNodeRenderer key={i} node={node} editable={false} themeColors={chartColors} />
                  ))}
                </div>
                <div className={`shrink-0 ${slide.layout_type.includes("fit") ? "w-1/2" : "w-2/5"}`}>
                  <img src={rootImageUrl} alt="" className="w-full h-full object-cover" />
                </div>
              </div>
            ) : (
              <div
                className={`h-full mx-auto ${slide.layout_type === "background" && rootImageUrl ? "relative z-10" : ""}`}
                style={{ padding: "20px", maxWidth: CARD_INNER_MAX[slide.sizing?.card_width ?? "M"] }}
              >
                {contentNodes.map((node, i) => (
                  <SlideNodeRenderer key={i} node={node} editable={false} themeColors={chartColors} />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </button>
  )
}
