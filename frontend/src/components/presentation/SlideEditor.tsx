import { useState, useCallback, useRef, useEffect } from "react"
import { RefreshCw, Loader2, ChevronUp, ChevronDown, Trash2, GripVertical } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { Slide, SlideNode, TextLeaf, SlideUpdate } from "@/types"

interface SlideEditorProps {
  presentationId: string
  slide: Slide
  onSlideUpdate: (slideId: string, update: SlideUpdate) => void
  onRegenerateSlide: (slideId: string) => void
  isRegenerating: boolean
}

// ── Type guards ──

function isTextLeaf(node: SlideNode | TextLeaf): node is TextLeaf {
  return "text" in node
}

// ── Recursive content renderer ──

function TextLeafRenderer({
  leaf,
  editable,
  onTextChange,
}: {
  leaf: TextLeaf
  editable: boolean
  onTextChange?: (text: string) => void
}) {
  const ref = useRef<HTMLSpanElement>(null)

  const handleBlur = useCallback(() => {
    if (ref.current && onTextChange) {
      const newText = ref.current.textContent || ""
      if (newText !== leaf.text) {
        onTextChange(newText)
      }
    }
  }, [leaf.text, onTextChange])

  return (
    <span
      ref={ref}
      contentEditable={editable}
      suppressContentEditableWarning
      onBlur={handleBlur}
      className="outline-none"
      style={{
        fontWeight: leaf.bold ? "bold" : undefined,
        fontStyle: leaf.italic ? "italic" : undefined,
        textDecoration: leaf.underline ? "underline" : undefined,
        color: leaf.color || undefined,
        fontSize: leaf.font_size || undefined,
        fontFamily: leaf.font_family || undefined,
      }}
    >
      {leaf.text}
    </span>
  )
}

function SlideNodeRenderer({
  node,
  editable,
  onNodeChange,
}: {
  node: SlideNode
  editable: boolean
  onNodeChange?: (updated: SlideNode) => void
}) {
  const handleChildTextChange = useCallback(
    (childIdx: number, text: string) => {
      if (!onNodeChange) return
      const newChildren = [...(node.children || [])]
      const child = newChildren[childIdx]
      if (child && isTextLeaf(child)) {
        newChildren[childIdx] = { ...child, text }
      }
      onNodeChange({ ...node, children: newChildren })
    },
    [node, onNodeChange],
  )

  const handleChildNodeChange = useCallback(
    (childIdx: number, updated: SlideNode) => {
      if (!onNodeChange) return
      const newChildren = [...(node.children || [])]
      newChildren[childIdx] = updated
      onNodeChange({ ...node, children: newChildren })
    },
    [node, onNodeChange],
  )

  const renderChildren = () =>
    (node.children || []).map((child, i) => {
      if (isTextLeaf(child)) {
        return (
          <TextLeafRenderer
            key={i}
            leaf={child}
            editable={editable}
            onTextChange={(text) => handleChildTextChange(i, text)}
          />
        )
      }
      return (
        <SlideNodeRenderer
          key={i}
          node={child}
          editable={editable}
          onNodeChange={(updated) => handleChildNodeChange(i, updated)}
        />
      )
    })

  switch (node.type) {
    case "h1":
      return <h1 className="text-2xl font-bold leading-tight mb-3">{renderChildren()}</h1>
    case "h2":
      return <h2 className="text-xl font-semibold leading-tight mb-2">{renderChildren()}</h2>
    case "h3":
      return <h3 className="text-lg font-semibold leading-tight mb-2">{renderChildren()}</h3>
    case "h4":
    case "h5":
    case "h6":
      return <h4 className="text-base font-medium leading-tight mb-1.5">{renderChildren()}</h4>
    case "p":
      return <p className="text-sm leading-relaxed mb-2">{renderChildren()}</p>

    // Lists
    case "bullet_group":
      return <ul className="space-y-1 mb-3 pl-4">{renderChildren()}</ul>
    case "bullet_item":
      return <li className="text-sm leading-relaxed list-disc">{renderChildren()}</li>
    case "icon_list":
      return <div className="grid grid-cols-2 gap-3 mb-3">{renderChildren()}</div>
    case "icon_list_item":
      return <div className="flex gap-2 items-start p-2 rounded-md bg-muted/20">{renderChildren()}</div>
    case "icon":
      return <span className="text-lg">●</span>

    // Boxes
    case "box_group":
      return <div className="grid grid-cols-2 gap-3 mb-3">{renderChildren()}</div>
    case "box_item":
      return <div className="rounded-lg border p-3 bg-muted/10">{renderChildren()}</div>

    // Comparison
    case "compare_group":
    case "before_after_group":
    case "pros_cons_group":
      return <div className="grid grid-cols-2 gap-4 mb-3">{renderChildren()}</div>
    case "compare_side":
    case "before_after_side":
      return <div className="rounded-lg border p-3">{renderChildren()}</div>
    case "pros_item":
      return <div className="rounded-lg border border-green-500/30 bg-green-500/5 p-3">{renderChildren()}</div>
    case "cons_item":
      return <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-3">{renderChildren()}</div>

    // Process
    case "timeline_group":
      return <div className="space-y-2 mb-3 border-l-2 border-primary/30 pl-4">{renderChildren()}</div>
    case "timeline_item":
      return <div className="relative pl-2 pb-2"><div className="absolute -left-[1.35rem] top-1 h-2.5 w-2.5 rounded-full bg-primary" />{renderChildren()}</div>
    case "cycle_group":
      return <div className="flex flex-wrap gap-2 mb-3">{renderChildren()}</div>
    case "cycle_item":
      return <div className="flex-1 min-w-[120px] rounded-lg border p-2 text-center">{renderChildren()}</div>
    case "arrow_list":
      return <div className="flex gap-2 items-stretch mb-3">{renderChildren()}</div>
    case "arrow_list_item":
      return <div className="flex-1 rounded-lg border p-2 text-center">{renderChildren()}</div>
    case "sequence_arrow_group":
      return <div className="space-y-2 mb-3">{renderChildren()}</div>
    case "sequence_arrow_item":
      return <div className="rounded-lg border p-2 flex items-center gap-2">{renderChildren()}</div>
    case "staircase_group":
      return <div className="space-y-1 mb-3">{renderChildren()}</div>
    case "stair_item":
      return <div className="rounded border p-2 ml-4 first:ml-0">{renderChildren()}</div>
    case "pyramid_group":
      return <div className="flex flex-col items-center gap-1 mb-3">{renderChildren()}</div>
    case "pyramid_item":
      return <div className="rounded border p-2 text-center w-full">{renderChildren()}</div>

    // Content
    case "quote":
      return <blockquote className="border-l-4 border-primary pl-4 italic mb-3">{renderChildren()}</blockquote>
    case "stats_group":
      return <div className="grid grid-cols-3 gap-3 mb-3">{renderChildren()}</div>
    case "stats_item":
      return (
        <div className="rounded-lg border p-3 text-center">
          <div className="text-2xl font-bold text-primary">{node.value || "—"}</div>
          {renderChildren()}
        </div>
      )
    case "image_gallery_group":
      return <div className="grid grid-cols-3 gap-2 mb-3">{renderChildren()}</div>
    case "image_gallery_item":
      return (
        <div className="rounded-lg border overflow-hidden">
          <div className="bg-muted/30 flex items-center justify-center py-6 text-xs text-muted-foreground">
            {node.query || "Image"}
          </div>
          {renderChildren()}
        </div>
      )

    // Charts (placeholder rendering)
    case "chart-bar":
    case "chart-line":
    case "chart-pie":
    case "chart-donut":
    case "chart-area":
    case "chart-radar":
    case "chart-scatter":
    case "chart-funnel":
    case "chart-treemap":
    case "chart-radial-bar":
    case "chart-waterfall":
    case "chart-nightingale":
    case "chart-gauge":
    case "chart-sunburst":
    case "chart-heatmap":
      return (
        <div className="bg-muted/20 rounded-lg flex items-center justify-center py-12 mb-3 border border-dashed">
          <span className="text-sm text-muted-foreground capitalize">
            📊 {node.type.replace("chart-", "").replace(/-/g, " ")}
          </span>
        </div>
      )

    // Image
    case "img":
      return (
        <div className="bg-muted/30 rounded-lg flex items-center justify-center py-8 mb-3 border border-dashed">
          <span className="text-sm text-muted-foreground">
            {node.url ? "Image" : "Emplacement image"}
          </span>
        </div>
      )
    default:
      return <div className="mb-2">{renderChildren()}</div>
  }
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
      className="group relative"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {hovered && (
        <div className="absolute -left-10 top-0 flex flex-col gap-0.5 z-10">
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
      )}
      <div className={hovered ? "ring-1 ring-primary/30 rounded-md" : ""}>
        {children}
      </div>
    </div>
  )
}

// ── Main SlideEditor component ──

export function SlideEditor({
  slide,
  onSlideUpdate,
  onRegenerateSlide,
  isRegenerating,
}: SlideEditorProps) {
  const [localNotes, setLocalNotes] = useState(slide.speaker_notes || "")
  const [localBgColor, setLocalBgColor] = useState(slide.bg_color || "#ffffff")
  const saveTimerRef = useRef<ReturnType<typeof setTimeout>>()

  // Reset local state when slide changes
  useEffect(() => {
    setLocalNotes(slide.speaker_notes || "")
    setLocalBgColor(slide.bg_color || "#ffffff")
  }, [slide.id, slide.speaker_notes, slide.bg_color])

  const contentNodes = (
    slide.content_json?.content_json ||
    (Array.isArray(slide.content_json) ? slide.content_json : [])
  ) as SlideNode[]

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

  const handleRegenerate = useCallback(() => {
    console.log("[SlideEditor] Regenerating slide:", slide.id)
    onRegenerateSlide(slide.id)
  }, [slide.id, onRegenerateSlide])

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

        <div className="flex-1 min-w-0" />

        <Button
          variant="outline"
          size="sm"
          onClick={handleRegenerate}
          disabled={isRegenerating}
          className="gap-1.5 shrink-0"
        >
          {isRegenerating ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <RefreshCw className="h-3.5 w-3.5" />
          )}
          Régénérer
        </Button>
      </div>

      {/* Slide canvas */}
      <div className="flex-1 overflow-auto p-6 flex items-start justify-center">
        <div
          className="w-full max-w-3xl aspect-video rounded-lg shadow-lg border p-8 pl-14 overflow-auto relative"
          style={{ backgroundColor: localBgColor }}
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
                />
              </DraggableNodeWrapper>
            ))
          ) : (
            <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
              Slide vide — cliquez sur "Régénérer" pour générer le contenu
            </div>
          )}
        </div>
      </div>

      {/* Speaker notes */}
      <div className="border-t bg-card px-4 py-3 shrink-0">
        <label className="text-xs font-medium text-muted-foreground block mb-1">
          Notes de l'intervenant
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
