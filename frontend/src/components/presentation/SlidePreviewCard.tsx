import { cn } from "@/lib/utils"
import type { Slide, SlideNode, TextLeaf } from "@/types"

interface SlidePreviewCardProps {
  slide: Slide
  index: number
  isSelected: boolean
  onClick: () => void
}

function isTextLeaf(node: SlideNode | TextLeaf): node is TextLeaf {
  return "text" in node
}

function extractText(nodes: (SlideNode | TextLeaf)[]): string {
  return nodes
    .map((n) => {
      if (isTextLeaf(n)) return n.text
      if ("children" in n && n.children) return extractText(n.children)
      return ""
    })
    .join("")
}

function MiniNodeRenderer({ node }: { node: SlideNode }) {
  const text = extractText(node.children || [])
  if (!text && node.type !== "img") return null

  switch (node.type) {
    case "h1":
      return <div className="text-[6px] font-bold leading-tight truncate">{text}</div>
    case "h2":
      return <div className="text-[5px] font-semibold leading-tight truncate">{text}</div>
    case "h3":
    case "h4":
    case "h5":
    case "h6":
      return <div className="text-[4.5px] font-medium leading-tight truncate">{text}</div>
    case "p":
      return <div className="text-[4px] leading-tight truncate text-muted-foreground">{text}</div>
    case "bullet_group":
      return (
        <div className="space-y-0.5">
          {(node.children as SlideNode[])
            ?.filter((c) => !isTextLeaf(c))
            .slice(0, 4)
            .map((child, i) => (
              <div key={i} className="flex items-start gap-0.5">
                <span className="text-[3px] mt-[1px]">•</span>
                <span className="text-[4px] leading-tight truncate">
                  {extractText((child as SlideNode).children || [])}
                </span>
              </div>
            ))}
        </div>
      )
    case "img":
      return (
        <div className="bg-muted/50 rounded-[2px] h-4 flex items-center justify-center">
          <span className="text-[3px] text-muted-foreground">IMG</span>
        </div>
      )
    default:
      return <div className="text-[4px] truncate">{text}</div>
  }
}

export function SlidePreviewCard({
  slide,
  index,
  isSelected,
  onClick,
}: SlidePreviewCardProps) {
  const contentNodes = (
    slide.content_json?.content_json ||
    (Array.isArray(slide.content_json) ? slide.content_json : [])
  ) as SlideNode[]

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
        <div
          className="aspect-video w-full rounded overflow-hidden p-1.5"
          style={{ backgroundColor: slide.bg_color || "#ffffff" }}
        >
          <div className="space-y-0.5 pointer-events-none overflow-hidden h-full">
            {contentNodes.slice(0, 5).map((node, i) => (
              <MiniNodeRenderer key={i} node={node} />
            ))}
          </div>
        </div>
      </div>
    </button>
  )
}
