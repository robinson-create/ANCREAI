import { useState, useCallback, useRef, useEffect, useMemo } from "react"
import { Textarea } from "@/components/ui/textarea"
import type { Slide, SlideUpdate, ThemeData } from "@/types"
import {
  SLIDE_REF_WIDTH, SLIDE_REF_HEIGHT,
  DEFAULT_THEME,
  buildThemeCSSVars,
} from "./SlideRenderer"
import SlideTemplateRenderer from "./SlideTemplateRenderer"
import { SlideEditProvider, type SlideEditContextValue } from "./SlideEditContext"
import { presentationsApi } from "@/api/presentations"

// ── Types ──

interface SlideEditorProps {
  presentationId?: string
  slide: Slide
  themeData: ThemeData | null
  footer?: unknown
  onSlideUpdate: (slideId: string, update: SlideUpdate) => void
}

// ── Helpers ──

/** Set a nested value in an object using a dot-separated path.
 *  e.g. setNestedField(obj, "teamMembers.0.image", value)
 */
function setNestedField(obj: Record<string, any>, path: string, value: any): Record<string, any> {
  const result = { ...obj }
  const parts = path.split(".")
  let current: any = result

  for (let i = 0; i < parts.length - 1; i++) {
    const key = parts[i]!
    const idx = Number(key)
    if (!isNaN(idx) && Array.isArray(current)) {
      current[idx] = { ...current[idx] }
      current = current[idx]
    } else {
      current[key] = Array.isArray(current[key])
        ? [...current[key]]
        : { ...current[key] }
      current = current[key]
    }
  }

  const lastKey = parts[parts.length - 1]!
  const lastIdx = Number(lastKey)
  if (!isNaN(lastIdx) && Array.isArray(current)) {
    current[lastIdx] = value
  } else {
    current[lastKey] = value
  }

  return result
}

// ── Main SlideEditor component ──

export function SlideEditor({
  presentationId,
  slide,
  themeData,
  onSlideUpdate,
}: SlideEditorProps) {
  const [localNotes, setLocalNotes] = useState(slide.speaker_notes || "")
  const canvasContainerRef = useRef<HTMLDivElement>(null)
  const [scaleFactor, setScaleFactor] = useState(1)

  const theme = themeData ?? DEFAULT_THEME
  const cssVars = useMemo(() => buildThemeCSSVars(theme), [theme])

  // Load Google Fonts for the theme
  useEffect(() => {
    const fonts = [theme.fonts.heading, theme.fonts.body].filter(Boolean)
    const families = [...new Set(fonts)].map(f => f.replace(/\s+/g, "+"))
    if (families.length === 0) return

    const linkId = "slide-editor-fonts"
    let link = document.getElementById(linkId) as HTMLLinkElement | null
    if (!link) {
      link = document.createElement("link")
      link.id = linkId
      link.rel = "stylesheet"
      document.head.appendChild(link)
    }
    link.href = `https://fonts.googleapis.com/css2?${families.map(f => `family=${f}:wght@400;600;700`).join("&")}&display=swap`
  }, [theme.fonts.heading, theme.fonts.body])

  // Compute scale factor to fit fixed canvas in available space
  useEffect(() => {
    const el = canvasContainerRef.current
    if (!el) return
    const obs = new ResizeObserver(([entry]) => {
      if (!entry) return
      const { width, height } = entry.contentRect
      const sx = (width - 48) / SLIDE_REF_WIDTH
      const sy = (height - 48) / SLIDE_REF_HEIGHT
      setScaleFactor(Math.min(sx, sy, 1))
    })
    obs.observe(el)
    return () => obs.disconnect()
  }, [])

  // Reset local state when slide changes
  useEffect(() => {
    setLocalNotes(slide.speaker_notes || "")
  }, [slide.id, slide.speaker_notes])

  const handleNotesBlur = useCallback(() => {
    if (localNotes !== (slide.speaker_notes || "")) {
      onSlideUpdate(slide.id, { speaker_notes: localNotes })
    }
  }, [slide.id, localNotes, slide.speaker_notes, onSlideUpdate])

  // Extract content_json as flat dict for the template renderer
  const data = useMemo(() => {
    const cj = slide.content_json
    if (typeof cj === 'object' && cj !== null && !Array.isArray(cj)) {
      return cj as Record<string, any>
    }
    return {} as Record<string, any>
  }, [slide.content_json])

  // Image upload handler — uploads file, then patches the slide's content_json
  const handleImageUpload = useCallback(async (fieldPath: string, file: File) => {
    if (!presentationId) return

    // 1. Upload the file as a presentation asset
    const asset = await presentationsApi.uploadAsset(presentationId, file)

    // 2. Build the new image value with asset_id and url
    const imageValue = {
      __image_url__: asset.url,
      __asset_id__: asset.id,
    }

    // 3. Patch the slide's content_json with the new image
    const updatedContent = setNestedField(data, fieldPath, imageValue)
    onSlideUpdate(slide.id, { content_json: updatedContent })
  }, [presentationId, slide.id, data, onSlideUpdate])

  // Text field update handler — patches content_json at a given dot-path
  const handleFieldUpdate = useCallback((fieldPath: string, value: string) => {
    const updatedContent = setNestedField(data, fieldPath, value)
    onSlideUpdate(slide.id, { content_json: updatedContent })
  }, [slide.id, data, onSlideUpdate])

  const editCtx = useMemo<SlideEditContextValue>(() => ({
    onImageUpload: handleImageUpload,
    onFieldUpdate: handleFieldUpdate,
    isEditable: !!presentationId,
  }), [handleImageUpload, handleFieldUpdate, presentationId])

  return (
    <div className="flex flex-col h-full">
      {/* Slide canvas — fixed 960x540 with scale transform */}
      <div
        ref={canvasContainerRef}
        className="flex-1 min-h-0 overflow-hidden flex items-center justify-center"
      >
        <div
          className="rounded-lg shadow-lg border overflow-hidden relative"
          style={{
            width: SLIDE_REF_WIDTH,
            height: SLIDE_REF_HEIGHT,
            transform: `scale(${scaleFactor})`,
            transformOrigin: "center center",
            ...cssVars,
          }}
        >
          <SlideEditProvider value={editCtx}>
            <SlideTemplateRenderer
              layoutType={slide.layout_type}
              data={data}
            />
          </SlideEditProvider>
        </div>
      </div>

      {/* Speaker notes */}
      <div className="border-t bg-card px-4 py-3 shrink-0">
        <label className="text-xs font-medium text-muted-foreground block mb-1">
          Notes de l&apos;intervenant
        </label>
        <Textarea
          value={localNotes}
          onChange={(e) => setLocalNotes(e.target.value)}
          onBlur={handleNotesBlur}
          placeholder="Notes visibles uniquement par le présentateur..."
          className="resize-none h-20 text-sm"
        />
      </div>
    </div>
  )
}
