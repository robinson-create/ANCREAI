import React, { useState, useCallback, useRef, useEffect, useMemo } from "react"
import { ChevronUp, ChevronDown, Trash2, GripVertical, ImagePlus, X, Upload, Link, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { presentationsApi } from "@/api/presentations"
import type { Slide, SlideNode, SlideUpdate, ThemeData, FooterConfig } from "@/types"
import {
  SLIDE_REF_WIDTH, SLIDE_REF_HEIGHT, CARD_INNER_MAX,
  DEFAULT_THEME,
  buildThemeCSSVars, buildSizingCSSVars, resolveChartColors,
  SlideNodeRenderer, SlideFooter,
} from "./SlideRenderer"

// ── Types ──

interface SlideEditorProps {
  presentationId: string
  slide: Slide
  themeData: ThemeData | null
  footer?: FooterConfig | null
  onSlideUpdate: (slideId: string, update: SlideUpdate) => void
}

// ── Draggable Node Wrapper ──

function DraggableNodeWrapper({
  index,
  total,
  onMoveUp,
  onMoveDown,
  onDelete,
  children,
}: {
  index: number
  total: number
  onMoveUp: () => void
  onMoveDown: () => void
  onDelete: () => void
  children: React.ReactNode
}) {
  const [hovered, setHovered] = useState(false)

  return (
    <div
      className="relative -ml-10 pl-10"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <div
        className={`absolute left-0 top-1/2 -translate-y-1/2 flex flex-col gap-0.5 z-10 transition-opacity ${hovered ? "opacity-100" : "opacity-0 pointer-events-none"}`}
      >
        <div className="flex flex-col items-center bg-card border rounded shadow-sm p-0.5">
          <button
            className="p-0.5 hover:bg-muted rounded disabled:opacity-30"
            onClick={onMoveUp}
            disabled={index === 0}
            title="Monter"
          >
            <ChevronUp className="h-3.5 w-3.5" />
          </button>
          <GripVertical className="h-3 w-3 text-muted-foreground" />
          <button
            className="p-0.5 hover:bg-muted rounded disabled:opacity-30"
            onClick={onMoveDown}
            disabled={index === total - 1}
            title="Descendre"
          >
            <ChevronDown className="h-3.5 w-3.5" />
          </button>
          <button
            className="p-0.5 hover:bg-destructive/10 hover:text-destructive rounded mt-0.5"
            onClick={onDelete}
            title="Supprimer"
          >
            <Trash2 className="h-3 w-3" />
          </button>
        </div>
      </div>

      <div className={`rounded-md ${hovered ? "ring-1 ring-primary/30" : ""}`}>
        {children}
      </div>
    </div>
  )
}

// ── Main SlideEditor component ──

export function SlideEditor({
  presentationId,
  slide,
  themeData,
  footer,
  onSlideUpdate,
}: SlideEditorProps) {
  const [localNotes, setLocalNotes] = useState(slide.speaker_notes || "")
  const [localBgColor, setLocalBgColor] = useState(slide.bg_color || "#ffffff")
  const [showImageInput, setShowImageInput] = useState(false)
  const [imageUrl, setImageUrl] = useState("")
  const [uploading, setUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const canvasContainerRef = useRef<HTMLDivElement>(null)
  const [scaleFactor, setScaleFactor] = useState(1)
  const saveTimerRef = useRef<ReturnType<typeof setTimeout>>()

  const theme = themeData ?? DEFAULT_THEME
  const cssVars = useMemo(() => buildThemeCSSVars(theme), [theme])
  const sizingVars = useMemo(() => buildSizingCSSVars(slide.sizing), [slide.sizing])
  const chartColors = useMemo(() => resolveChartColors(theme), [theme])

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
      setScaleFactor(Math.min(sx, sy, 1.5))
    })
    obs.observe(el)
    return () => obs.disconnect()
  }, [])

  // Reset local state when slide changes
  useEffect(() => {
    setLocalNotes(slide.speaker_notes || "")
    setLocalBgColor(slide.bg_color || "#ffffff")
  }, [slide.id, slide.speaker_notes, slide.bg_color])

  const contentNodes = (
    slide.content_json?.content_json ||
    (Array.isArray(slide.content_json) ? slide.content_json : [])
  ) as SlideNode[]

  // Root image (layout image)
  const rootImage = slide.root_image as { asset_id?: string; query?: string; url?: string } | null
  const rootImageUrl = rootImage?.url || rootImage?.asset_id || null

  const debouncedSave = useCallback(
    (update: SlideUpdate) => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
      saveTimerRef.current = setTimeout(() => {
        onSlideUpdate(slide.id, update)
      }, 1500)
    },
    [slide.id, onSlideUpdate],
  )

  const saveImmediate = useCallback(
    (newNodes: SlideNode[]) => {
      const newContentJson = { ...slide.content_json, content_json: newNodes }
      onSlideUpdate(slide.id, { content_json: newContentJson })
    },
    [slide.id, slide.content_json, onSlideUpdate],
  )

  const handleNodeChange = useCallback(
    (nodeIdx: number, updated: SlideNode) => {
      const newNodes = [...contentNodes]
      newNodes[nodeIdx] = updated
      const newContentJson = { ...slide.content_json, content_json: newNodes }
      debouncedSave({ content_json: newContentJson })
    },
    [contentNodes, slide.content_json, debouncedSave],
  )

  const handleMoveNode = useCallback(
    (fromIdx: number, toIdx: number) => {
      if (toIdx < 0 || toIdx >= contentNodes.length) return
      const newNodes = [...contentNodes]
      const [moved] = newNodes.splice(fromIdx, 1)
      if (!moved) return
      newNodes.splice(toIdx, 0, moved)
      saveImmediate(newNodes)
    },
    [contentNodes, saveImmediate],
  )

  const handleDeleteNode = useCallback(
    (nodeIdx: number) => {
      const newNodes = contentNodes.filter((_, i) => i !== nodeIdx)
      saveImmediate(newNodes)
    },
    [contentNodes, saveImmediate],
  )

  const handleLayoutChange = useCallback(
    (layout: string) => {
      onSlideUpdate(slide.id, { layout_type: layout })
    },
    [slide.id, onSlideUpdate],
  )

  const handleBgColorChange = useCallback(
    (color: string) => {
      setLocalBgColor(color)
      debouncedSave({ bg_color: color })
    },
    [debouncedSave],
  )

  const handleNotesBlur = useCallback(() => {
    if (localNotes !== (slide.speaker_notes || "")) {
      onSlideUpdate(slide.id, { speaker_notes: localNotes })
    }
  }, [slide.id, localNotes, slide.speaker_notes, onSlideUpdate])

  const handleSetImage = useCallback(() => {
    const url = imageUrl.trim()
    if (!url) return
    onSlideUpdate(slide.id, {
      root_image: { url, query: "", layout_type: slide.layout_type },
    })
    setShowImageInput(false)
    setImageUrl("")
  }, [imageUrl, slide.id, slide.layout_type, onSlideUpdate])

  const handleRemoveImage = useCallback(() => {
    onSlideUpdate(slide.id, { root_image: null })
  }, [slide.id, onSlideUpdate])

  const handleFileUpload = useCallback(async (file: File) => {
    if (!file.type.startsWith("image/")) return
    setUploading(true)
    try {
      const asset = await presentationsApi.uploadAsset(presentationId, file)
      if (asset.url) {
        onSlideUpdate(slide.id, {
          root_image: { url: asset.url, asset_id: asset.id, layout_type: slide.layout_type },
        })
      }
    } catch (err) {
      console.error("Image upload failed:", err)
    } finally {
      setUploading(false)
    }
  }, [presentationId, slide.id, slide.layout_type, onSlideUpdate])

  const handleFileInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleFileUpload(file)
    // Reset so the same file can be re-selected
    if (fileInputRef.current) fileInputRef.current.value = ""
  }, [handleFileUpload])

  const handleImageError = useCallback(async () => {
    const ri = slide.root_image as { asset_id?: string; url?: string } | null
    if (ri?.asset_id) {
      try {
        const { url } = await presentationsApi.getAssetUrl(presentationId, ri.asset_id)
        onSlideUpdate(slide.id, {
          root_image: { ...ri, url },
        })
      } catch {
        // Ignore — image is genuinely broken
      }
    }
  }, [presentationId, slide.id, slide.root_image, onSlideUpdate])

  // Use theme background if no custom bg_color has been set
  const slideBg = localBgColor !== "#ffffff" ? localBgColor : theme.colors.background

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar — all buttons on a single line */}
      <div className="flex items-center gap-2 px-4 py-2 border-b bg-card shrink-0 overflow-x-auto flex-nowrap">
        <Select value={slide.layout_type} onValueChange={handleLayoutChange}>
          <SelectTrigger className="w-32 h-8 shrink-0">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="vertical">Vertical</SelectItem>
            <SelectItem value="left">Image gauche</SelectItem>
            <SelectItem value="right">Image droite</SelectItem>
            <SelectItem value="left-fit">Gauche pleine</SelectItem>
            <SelectItem value="right-fit">Droite pleine</SelectItem>
            <SelectItem value="accent-top">Accent haut</SelectItem>
            <SelectItem value="background">Fond image</SelectItem>
          </SelectContent>
        </Select>

        <div className="flex items-center gap-1.5 shrink-0">
          <label className="text-xs text-muted-foreground">Fond</label>
          <input
            type="color"
            value={localBgColor}
            onChange={(e) => handleBgColorChange(e.target.value)}
            className="h-7 w-7 rounded border cursor-pointer"
          />
        </div>

        <div className="h-5 w-px bg-border shrink-0" />

        {/* Image controls */}
        <input
          ref={fileInputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp,image/gif"
          className="hidden"
          onChange={handleFileInputChange}
        />
        {rootImageUrl ? (
          <div className="flex items-center gap-1 shrink-0">
            <span className="text-xs text-muted-foreground truncate max-w-[120px]">Image</span>
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6 text-muted-foreground hover:text-destructive"
              onClick={handleRemoveImage}
              title="Supprimer l'image"
            >
              <X className="h-3 w-3" />
            </Button>
          </div>
        ) : showImageInput ? (
          <div className="flex items-center gap-1 shrink-0">
            <Input
              value={imageUrl}
              onChange={(e) => setImageUrl(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSetImage()}
              placeholder="URL de l'image..."
              className="h-7 w-52 text-xs"
              autoFocus
            />
            <Button variant="default" size="sm" className="h-7 text-xs px-2" onClick={handleSetImage}>
              OK
            </Button>
            <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => setShowImageInput(false)}>
              <X className="h-3 w-3" />
            </Button>
          </div>
        ) : (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                className="h-7 gap-1 text-xs shrink-0"
                disabled={uploading}
              >
                {uploading ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <ImagePlus className="h-3.5 w-3.5" />
                )}
                {uploading ? "Upload..." : "Image"}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start">
              <DropdownMenuItem onClick={() => fileInputRef.current?.click()}>
                <Upload className="h-4 w-4 mr-2" />
                Importer un fichier
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => setShowImageInput(true)}>
                <Link className="h-4 w-4 mr-2" />
                Coller une URL
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>

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
            ...sizingVars,
            backgroundColor: slideBg,
            color: "var(--pres-text)",
            fontFamily: "var(--pres-body-font)",
          }}
        >
          {/* Background image (layout: background) */}
          {rootImageUrl && slide.layout_type === "background" && (
            <img src={rootImageUrl} alt="" className="absolute inset-0 w-full h-full object-cover" onError={handleImageError} />
          )}
          {rootImageUrl && slide.layout_type === "background" && (
            <div className="absolute inset-0 bg-black/40" />
          )}

          {/* Layout with side image */}
          {rootImageUrl && ["left", "right", "left-fit", "right-fit"].includes(slide.layout_type) ? (
            <div className={`flex h-full ${slide.layout_type.startsWith("right") ? "flex-row" : "flex-row-reverse"}`}>
              <div className="flex-1 overflow-hidden relative" style={{ padding: "20px 20px 20px 48px", maxWidth: CARD_INNER_MAX[slide.sizing?.card_width ?? "M"] }}>
                {contentNodes.length > 0 ? (
                  contentNodes.map((node, i) => (
                    <DraggableNodeWrapper
                      key={`${node.type}-${i}`}
                      index={i}
                      total={contentNodes.length}
                      onMoveUp={() => handleMoveNode(i, i - 1)}
                      onMoveDown={() => handleMoveNode(i, i + 1)}
                      onDelete={() => handleDeleteNode(i)}
                    >
                      <SlideNodeRenderer
                        node={node}
                        editable
                        onNodeChange={(updated) => handleNodeChange(i, updated)}
                        themeColors={chartColors}
                      />
                    </DraggableNodeWrapper>
                  ))
                ) : (
                  <div className="flex items-center justify-center h-full text-sm" style={{ color: "var(--pres-muted)" }}>
                    Slide vide
                  </div>
                )}
              </div>
              <div className={`shrink-0 ${slide.layout_type.includes("fit") ? "w-1/2" : "w-2/5"}`}>
                <img src={rootImageUrl} alt="" className="w-full h-full object-cover" onError={handleImageError} />
              </div>
            </div>
          ) : (
            <div
              className={`h-full mx-auto ${slide.layout_type === "background" && rootImageUrl ? "relative z-10" : ""}`}
              style={{ padding: "20px 20px 20px 48px", maxWidth: CARD_INNER_MAX[slide.sizing?.card_width ?? "M"] }}
            >
              {contentNodes.length > 0 ? (
                contentNodes.map((node, i) => (
                  <DraggableNodeWrapper
                    key={`${node.type}-${i}`}
                    index={i}
                    total={contentNodes.length}
                    onMoveUp={() => handleMoveNode(i, i - 1)}
                    onMoveDown={() => handleMoveNode(i, i + 1)}
                    onDelete={() => handleDeleteNode(i)}
                  >
                    <SlideNodeRenderer
                      node={node}
                      editable
                      onNodeChange={(updated) => handleNodeChange(i, updated)}
                      themeColors={chartColors}
                    />
                  </DraggableNodeWrapper>
                ))
              ) : (
                <div className="flex items-center justify-center h-full text-sm" style={{ color: "var(--pres-muted)" }}>
                  Slide vide — utilisez le panneau IA pour générer le contenu
                </div>
              )}
            </div>
          )}

          <SlideFooter footer={footer} />
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
