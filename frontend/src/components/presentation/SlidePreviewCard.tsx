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

function MiniGroupRenderer({ node, symbol = "•" }: { node: SlideNode; symbol?: string }) {
  return (
    <div className="space-y-0.5">
      {(node.children as SlideNode[])
        ?.filter((c) => !isTextLeaf(c))
        .slice(0, 4)
        .map((child, i) => (
          <div key={i} className="flex items-start gap-0.5">
            <span className="text-[3px] mt-[1px]">{symbol}</span>
            <span className="text-[4px] leading-tight truncate">
              {extractText((child as SlideNode).children || [])}
            </span>
          </div>
        ))}
    </div>
  )
}

function MiniNodeRenderer({ node }: { node: SlideNode }) {
  const text = extractText(node.children || [])
  if (!text && node.type !== "img" && !node.type.startsWith("chart-")) return null

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

    // Lists
    case "bullet_group":
      return <MiniGroupRenderer node={node} symbol="•" />
    case "icon_list":
      return <MiniGroupRenderer node={node} symbol="◆" />

    // Boxes / Cards
    case "box_group":
    case "stats_group":
      return (
        <div className="flex gap-0.5">
          {(node.children as SlideNode[])
            ?.filter((c) => !isTextLeaf(c))
            .slice(0, 3)
            .map((child, i) => (
              <div key={i} className="flex-1 rounded-[1px] border border-muted/40 p-0.5">
                <span className="text-[3.5px] leading-tight truncate block">
                  {extractText((child as SlideNode).children || [])}
                </span>
              </div>
            ))}
        </div>
      )

    // Comparison (2-col)
    case "compare_group":
    case "before_after_group":
    case "pros_cons_group":
      return (
        <div className="flex gap-0.5">
          {(node.children as SlideNode[])
            ?.filter((c) => !isTextLeaf(c))
            .slice(0, 2)
            .map((child, i) => (
              <div key={i} className="flex-1 rounded-[1px] border border-muted/40 p-0.5">
                <span className="text-[3.5px] leading-tight truncate block">
                  {extractText((child as SlideNode).children || [])}
                </span>
              </div>
            ))}
        </div>
      )

    // Process elements
    case "timeline_group":
      return <MiniGroupRenderer node={node} symbol="○" />
    case "cycle_group":
    case "arrow_list":
    case "sequence_arrow_group":
      return <MiniGroupRenderer node={node} symbol="→" />
    case "staircase_group":
      return <MiniGroupRenderer node={node} symbol="▸" />
    case "pyramid_group":
      return <MiniGroupRenderer node={node} symbol="△" />

    // Content
    case "quote":
      return <div className="text-[4px] italic leading-tight truncate border-l border-muted pl-0.5">"{text}"</div>
    case "image_gallery_group":
      return (
        <div className="flex gap-0.5">
          {(node.children as SlideNode[])
            ?.filter((c) => !isTextLeaf(c))
            .slice(0, 3)
            .map((_, i) => (
              <div key={i} className="flex-1 bg-muted/30 rounded-[1px] h-3 flex items-center justify-center">
                <span className="text-[2.5px] text-muted-foreground">IMG</span>
              </div>
            ))}
        </div>
      )

    // Charts
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
        <div className="bg-muted/30 rounded-[2px] h-4 flex items-center justify-center">
          <span className="text-[3px] text-muted-foreground">📊</span>
        </div>
      )

    // Image
    case "img":
      return (
        <div className="bg-muted/50 rounded-[2px] h-4 flex items-center justify-center">
          <span className="text-[3px] text-muted-foreground">IMG</span>
        </div>
      )
    default:
      return text ? <div className="text-[4px] truncate">{text}</div> : null
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
