import { useState, useCallback, useRef, useEffect } from "react"
import { RefreshCw, Loader2 } from "lucide-react"
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
    case "bullet_group":
      return <ul className="space-y-1 mb-3 pl-4">{renderChildren()}</ul>
    case "bullet_item":
      return <li className="text-sm leading-relaxed list-disc">{renderChildren()}</li>
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

  const handleNodeChange = useCallback(
    (nodeIdx: number, updated: SlideNode) => {
      const newNodes = [...contentNodes]
      newNodes[nodeIdx] = updated
      const newContentJson = { ...slide.content_json, content_json: newNodes }
      debouncedSave({ content_json: newContentJson })
    },
    [contentNodes, slide.content_json, debouncedSave],
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

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center gap-3 px-4 py-2 border-b bg-card shrink-0">
        <Select value={slide.layout_type} onValueChange={handleLayoutChange}>
          <SelectTrigger className="w-36 h-8">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="vertical">Vertical</SelectItem>
            <SelectItem value="horizontal">Horizontal</SelectItem>
            <SelectItem value="left">Image gauche</SelectItem>
            <SelectItem value="right">Image droite</SelectItem>
            <SelectItem value="background">Fond image</SelectItem>
          </SelectContent>
        </Select>

        <div className="flex items-center gap-1.5">
          <label className="text-xs text-muted-foreground">Fond</label>
          <input
            type="color"
            value={localBgColor}
            onChange={(e) => handleBgColorChange(e.target.value)}
            className="h-7 w-7 rounded border cursor-pointer"
          />
        </div>

        <div className="flex-1" />

        <Button
          variant="outline"
          size="sm"
          onClick={() => onRegenerateSlide(slide.id)}
          disabled={isRegenerating}
          className="gap-1.5"
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
          className="w-full max-w-3xl aspect-video rounded-lg shadow-lg border p-8 overflow-auto"
          style={{ backgroundColor: localBgColor }}
        >
          {contentNodes.length > 0 ? (
            contentNodes.map((node, i) => (
              <SlideNodeRenderer
                key={i}
                node={node}
                editable
                onNodeChange={(updated) => handleNodeChange(i, updated)}
              />
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
