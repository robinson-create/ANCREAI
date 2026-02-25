import { useState } from "react"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { cn } from "@/lib/utils"
import { ChevronRight, X } from "lucide-react"
import type { SlideNode } from "@/types"
import type { ReactNode } from "react"

// ── Types ──

interface ElementCategory {
  name: string
  elements: ElementDef[]
}

interface ElementDef {
  name: string
  thumbnail: ReactNode
  factory: () => SlideNode[]
}

interface AddElementsPanelProps {
  onInsertElements: (nodes: SlideNode[]) => void
  onClose: () => void
}

// ── Mini SVG thumbnails for visual preview ──

function MiniThumb({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn("w-full aspect-[16/10] rounded border bg-background flex items-center justify-center p-1.5 overflow-hidden", className)}>
      {children}
    </div>
  )
}

// Basic text thumbnails
function ThumbTextHeading() {
  return (
    <MiniThumb>
      <div className="w-full space-y-1">
        <div className="h-1.5 w-3/4 bg-foreground/70 rounded-sm" />
        <div className="h-1 w-full bg-muted-foreground/30 rounded-sm" />
        <div className="h-1 w-5/6 bg-muted-foreground/30 rounded-sm" />
      </div>
    </MiniThumb>
  )
}

function ThumbTextImage() {
  return (
    <MiniThumb>
      <div className="w-full flex gap-1.5">
        <div className="flex-1 space-y-0.5">
          <div className="h-1.5 w-full bg-foreground/70 rounded-sm" />
          <div className="h-1 w-full bg-muted-foreground/30 rounded-sm" />
          <div className="h-1 w-3/4 bg-muted-foreground/30 rounded-sm" />
        </div>
        <div className="w-8 h-8 bg-muted rounded-sm shrink-0" />
      </div>
    </MiniThumb>
  )
}

function ThumbTwoColumns() {
  return (
    <MiniThumb>
      <div className="w-full flex gap-1">
        <div className="flex-1 space-y-0.5">
          <div className="h-1 w-full bg-foreground/60 rounded-sm" />
          <div className="h-0.5 w-full bg-muted-foreground/30 rounded-sm" />
          <div className="h-0.5 w-3/4 bg-muted-foreground/30 rounded-sm" />
        </div>
        <div className="flex-1 space-y-0.5">
          <div className="h-1 w-full bg-foreground/60 rounded-sm" />
          <div className="h-0.5 w-full bg-muted-foreground/30 rounded-sm" />
          <div className="h-0.5 w-3/4 bg-muted-foreground/30 rounded-sm" />
        </div>
      </div>
    </MiniThumb>
  )
}

// Box variant thumbnails
function ThumbBoxes({ variant }: { variant: string }) {
  const styles: Record<string, string> = {
    solid: "bg-primary/15 border-0",
    outline: "bg-transparent border border-primary/40",
    sideline: "bg-transparent border-l-2 border-l-primary border-y-0 border-r-0",
    joined: "bg-muted/30 border-0 rounded-none",
    icons: "bg-primary/10 border-0",
    leaf: "bg-green-500/10 border-0 rounded-tr-xl rounded-bl-xl",
  }
  return (
    <MiniThumb>
      <div className="w-full grid grid-cols-3 gap-0.5">
        {[0, 1, 2].map(i => (
          <div key={i} className={cn("h-5 rounded-sm p-0.5 flex flex-col justify-center", styles[variant] || styles.solid)}>
            {variant === "icons" && <div className="h-1.5 w-1.5 rounded-full bg-primary/50 mb-0.5 mx-auto" />}
            <div className="h-0.5 w-full bg-foreground/40 rounded-sm" />
            <div className="h-0.5 w-2/3 bg-muted-foreground/30 rounded-sm mt-0.5" />
          </div>
        ))}
      </div>
    </MiniThumb>
  )
}

// Card layout thumbnails
function ThumbAccent({ position }: { position: "left" | "right" | "top" | "left-fit" | "right-fit" | "bg" }) {
  const accent = "bg-primary/30"
  if (position === "top") {
    return (
      <MiniThumb>
        <div className="w-full space-y-0.5">
          <div className={cn("h-1 w-full rounded-sm", accent)} />
          <div className="space-y-0.5 pt-0.5">
            <div className="h-1 w-2/3 bg-foreground/60 rounded-sm" />
            <div className="h-0.5 w-full bg-muted-foreground/30 rounded-sm" />
          </div>
        </div>
      </MiniThumb>
    )
  }
  if (position === "bg") {
    return (
      <MiniThumb className="relative">
        <div className={cn("absolute inset-0", accent)} />
        <div className="relative z-10 space-y-0.5 p-1">
          <div className="h-1 w-2/3 bg-foreground/80 rounded-sm" />
          <div className="h-0.5 w-full bg-foreground/40 rounded-sm" />
        </div>
      </MiniThumb>
    )
  }
  const isFit = position.includes("fit")
  const isLeft = position.startsWith("left")
  return (
    <MiniThumb>
      <div className="w-full flex gap-0.5 h-full">
        {isLeft && <div className={cn(isFit ? "w-1/2 -m-1.5 mr-0" : "w-2/5", "rounded-sm shrink-0", accent)} />}
        <div className="flex-1 space-y-0.5 flex flex-col justify-center">
          <div className="h-1 w-3/4 bg-foreground/60 rounded-sm" />
          <div className="h-0.5 w-full bg-muted-foreground/30 rounded-sm" />
          <div className="h-0.5 w-2/3 bg-muted-foreground/30 rounded-sm" />
        </div>
        {!isLeft && <div className={cn(isFit ? "w-1/2 -m-1.5 ml-0" : "w-2/5", "rounded-sm shrink-0", accent)} />}
      </div>
    </MiniThumb>
  )
}

// Image gallery thumbnails
function ThumbGallery({ cols, withText }: { cols: number; withText?: boolean }) {
  return (
    <MiniThumb>
      <div className={cn("w-full grid gap-0.5", cols === 2 ? "grid-cols-2" : cols === 4 ? "grid-cols-4" : "grid-cols-3")}>
        {Array.from({ length: cols }).map((_, i) => (
          <div key={i} className="flex flex-col gap-0.5">
            <div className="aspect-square bg-muted rounded-sm" />
            {withText && <div className="h-0.5 w-full bg-muted-foreground/30 rounded-sm" />}
          </div>
        ))}
      </div>
    </MiniThumb>
  )
}

function ThumbTeam() {
  return (
    <MiniThumb>
      <div className="w-full grid grid-cols-3 gap-1">
        {[0, 1, 2].map(i => (
          <div key={i} className="flex flex-col items-center gap-0.5">
            <div className="h-4 w-4 rounded-full bg-muted" />
            <div className="h-0.5 w-full bg-foreground/40 rounded-sm" />
            <div className="h-0.5 w-2/3 bg-muted-foreground/30 rounded-sm" />
          </div>
        ))}
      </div>
    </MiniThumb>
  )
}

// Stats thumbnails
function ThumbStats({ variant }: { variant: string }) {
  if (variant === "circle") {
    return (
      <MiniThumb>
        <div className="w-full grid grid-cols-3 gap-1">
          {[0, 1, 2].map(i => (
            <div key={i} className="flex flex-col items-center gap-0.5">
              <div className="h-5 w-5 rounded-full border-2 border-primary/50 flex items-center justify-center">
                <span className="text-[5px] font-bold text-primary/70">85%</span>
              </div>
              <div className="h-0.5 w-full bg-muted-foreground/30 rounded-sm" />
            </div>
          ))}
        </div>
      </MiniThumb>
    )
  }
  if (variant === "bar") {
    return (
      <MiniThumb>
        <div className="w-full grid grid-cols-3 gap-1">
          {[70, 50, 90].map((v, i) => (
            <div key={i} className="flex flex-col items-center gap-0.5">
              <div className="h-1 w-full bg-muted rounded-full overflow-hidden">
                <div className="h-full bg-primary/50 rounded-full" style={{ width: `${v}%` }} />
              </div>
              <span className="text-[4px] text-muted-foreground">{v}%</span>
            </div>
          ))}
        </div>
      </MiniThumb>
    )
  }
  if (variant === "star-rating") {
    return (
      <MiniThumb>
        <div className="w-full grid grid-cols-3 gap-1">
          {[0, 1, 2].map(i => (
            <div key={i} className="flex flex-col items-center gap-0.5">
              <div className="flex gap-px">
                {[0, 1, 2, 3, 4].map(s => (
                  <div key={s} className={cn("h-1.5 w-1.5", s <= 3 - i ? "text-yellow-500" : "text-muted")}>★</div>
                ))}
              </div>
              <div className="h-0.5 w-full bg-muted-foreground/30 rounded-sm" />
            </div>
          ))}
        </div>
      </MiniThumb>
    )
  }
  if (variant === "dot-grid") {
    return (
      <MiniThumb>
        <div className="w-full grid grid-cols-3 gap-1">
          {[7, 5, 9].map((v, i) => (
            <div key={i} className="flex flex-col items-center gap-0.5">
              <div className="grid grid-cols-5 gap-px">
                {Array.from({ length: 10 }).map((_, d) => (
                  <div key={d} className={cn("h-1 w-1 rounded-full", d < v ? "bg-primary/50" : "bg-muted")} />
                ))}
              </div>
            </div>
          ))}
        </div>
      </MiniThumb>
    )
  }
  // default
  return (
    <MiniThumb>
      <div className="w-full grid grid-cols-3 gap-1">
        {["85%", "12K", "99%"].map((v, i) => (
          <div key={i} className="flex flex-col items-center rounded-sm border p-0.5">
            <span className="text-[6px] font-bold text-primary/70">{v}</span>
            <div className="h-0.5 w-2/3 bg-muted-foreground/30 rounded-sm" />
          </div>
        ))}
      </div>
    </MiniThumb>
  )
}

// Timeline/sequence thumbnails
function ThumbTimeline({ variant }: { variant: string }) {
  if (variant === "minimal") {
    return (
      <MiniThumb>
        <div className="w-full space-y-1">
          {[0, 1, 2].map(i => (
            <div key={i} className="flex items-center gap-1">
              <div className="h-1.5 w-1.5 rounded-full bg-primary/50 shrink-0" />
              <div className="h-0.5 flex-1 bg-muted-foreground/30 rounded-sm" />
            </div>
          ))}
        </div>
      </MiniThumb>
    )
  }
  if (variant === "minimal-boxes") {
    return (
      <MiniThumb>
        <div className="w-full space-y-0.5">
          {[0, 1, 2].map(i => (
            <div key={i} className="flex items-center gap-1">
              <div className="h-1.5 w-1.5 rounded-full bg-primary/50 shrink-0" />
              <div className="flex-1 rounded-sm border p-0.5">
                <div className="h-0.5 w-2/3 bg-foreground/50 rounded-sm" />
              </div>
            </div>
          ))}
        </div>
      </MiniThumb>
    )
  }
  if (variant === "pills") {
    return (
      <MiniThumb>
        <div className="w-full flex gap-0.5 items-center justify-center">
          {[0, 1, 2].map(i => (
            <div key={i} className="flex-1 h-5 rounded-full bg-primary/15 flex items-center justify-center">
              <div className="h-0.5 w-2/3 bg-foreground/50 rounded-sm" />
            </div>
          ))}
        </div>
      </MiniThumb>
    )
  }
  if (variant === "slanted") {
    return (
      <MiniThumb>
        <div className="w-full flex gap-0.5 items-end">
          {[0, 1, 2].map(i => (
            <div key={i} className="flex-1 rounded-sm bg-primary/15 flex items-center justify-center"
              style={{ height: `${12 + i * 4}px` }}>
              <div className="h-0.5 w-2/3 bg-foreground/50 rounded-sm" />
            </div>
          ))}
        </div>
      </MiniThumb>
    )
  }
  if (variant === "arrows") {
    return (
      <MiniThumb>
        <div className="w-full flex gap-0.5 items-center">
          {[0, 1, 2].map(i => (
            <div key={i} className="flex items-center flex-1">
              <div className="flex-1 h-5 bg-primary/15 rounded-sm flex items-center justify-center">
                <div className="h-0.5 w-2/3 bg-foreground/50 rounded-sm" />
              </div>
              {i < 2 && <div className="text-[8px] text-primary/50 mx-0.5">→</div>}
            </div>
          ))}
        </div>
      </MiniThumb>
    )
  }
  // default timeline
  return (
    <MiniThumb>
      <div className="w-full flex gap-0.5">
        <div className="flex flex-col items-center gap-0.5 shrink-0">
          {[0, 1, 2].map(i => (
            <div key={i} className="flex flex-col items-center">
              <div className="h-2 w-2 rounded-full bg-primary/50" />
              {i < 2 && <div className="h-2 w-px bg-primary/30" />}
            </div>
          ))}
        </div>
        <div className="flex-1 space-y-1">
          {[0, 1, 2].map(i => (
            <div key={i} className="space-y-0.5">
              <div className="h-0.5 w-1/2 bg-foreground/60 rounded-sm" />
              <div className="h-0.5 w-full bg-muted-foreground/20 rounded-sm" />
            </div>
          ))}
        </div>
      </div>
    </MiniThumb>
  )
}

// Process thumbnails
function ThumbCycle() {
  return (
    <MiniThumb>
      <div className="relative w-10 h-10">
        {[0, 1, 2, 3].map(i => {
          const angle = (i * 90 - 45) * (Math.PI / 180)
          const x = 50 + 35 * Math.cos(angle)
          const y = 50 + 35 * Math.sin(angle)
          return (
            <div key={i} className="absolute h-2.5 w-2.5 rounded-full bg-primary/30 border border-primary/50"
              style={{ left: `${x}%`, top: `${y}%`, transform: "translate(-50%, -50%)" }} />
          )
        })}
        <div className="absolute inset-2 rounded-full border border-dashed border-primary/30" />
      </div>
    </MiniThumb>
  )
}

function ThumbStaircase() {
  return (
    <MiniThumb>
      <div className="w-full flex items-end gap-0.5 h-full px-1 pb-1">
        {[0, 1, 2, 3].map(i => (
          <div key={i} className="flex-1 bg-primary/20 rounded-t-sm" style={{ height: `${30 + i * 20}%` }}>
            <div className="h-0.5 w-2/3 bg-foreground/40 rounded-sm mx-auto mt-1" />
          </div>
        ))}
      </div>
    </MiniThumb>
  )
}

function ThumbPyramid({ inverted }: { inverted?: boolean }) {
  const widths = inverted ? ["90%", "70%", "50%"] : ["50%", "70%", "90%"]
  return (
    <MiniThumb>
      <div className="w-full flex flex-col items-center gap-0.5">
        {widths.map((w, i) => (
          <div key={i} className="h-3 bg-primary/20 rounded-sm flex items-center justify-center" style={{ width: w }}>
            <div className="h-0.5 w-2/3 bg-foreground/40 rounded-sm" />
          </div>
        ))}
      </div>
    </MiniThumb>
  )
}

// Comparison thumbnails
function ThumbCompare() {
  return (
    <MiniThumb>
      <div className="w-full flex gap-0.5">
        <div className="flex-1 rounded-sm border p-0.5 space-y-0.5">
          <div className="h-0.5 w-2/3 bg-foreground/60 rounded-sm" />
          <div className="h-0.5 w-full bg-muted-foreground/20 rounded-sm" />
        </div>
        <div className="flex-1 rounded-sm border p-0.5 space-y-0.5">
          <div className="h-0.5 w-2/3 bg-foreground/60 rounded-sm" />
          <div className="h-0.5 w-full bg-muted-foreground/20 rounded-sm" />
        </div>
      </div>
    </MiniThumb>
  )
}

function ThumbProsCons() {
  return (
    <MiniThumb>
      <div className="w-full flex gap-0.5">
        <div className="flex-1 rounded-sm border border-green-500/30 bg-green-500/5 p-0.5 space-y-0.5">
          <div className="h-0.5 w-1/2 bg-green-600/40 rounded-sm" />
          <div className="h-0.5 w-full bg-muted-foreground/20 rounded-sm" />
        </div>
        <div className="flex-1 rounded-sm border border-red-500/30 bg-red-500/5 p-0.5 space-y-0.5">
          <div className="h-0.5 w-1/2 bg-red-600/40 rounded-sm" />
          <div className="h-0.5 w-full bg-muted-foreground/20 rounded-sm" />
        </div>
      </div>
    </MiniThumb>
  )
}

function ThumbBeforeAfter() {
  return (
    <MiniThumb>
      <div className="w-full flex gap-0.5 items-center">
        <div className="flex-1 rounded-sm border p-0.5 space-y-0.5 opacity-50">
          <div className="h-0.5 w-2/3 bg-foreground/60 rounded-sm" />
          <div className="h-0.5 w-full bg-muted-foreground/20 rounded-sm" />
        </div>
        <div className="text-[8px] text-primary shrink-0">→</div>
        <div className="flex-1 rounded-sm border p-0.5 space-y-0.5">
          <div className="h-0.5 w-2/3 bg-foreground/60 rounded-sm" />
          <div className="h-0.5 w-full bg-muted-foreground/20 rounded-sm" />
        </div>
      </div>
    </MiniThumb>
  )
}

// Quote thumbnails
function ThumbQuote({ variant }: { variant: string }) {
  if (variant === "side-icon") {
    return (
      <MiniThumb>
        <div className="w-full flex gap-1">
          <div className="text-[10px] text-primary/40 leading-none shrink-0">"</div>
          <div className="flex-1 space-y-0.5">
            <div className="h-0.5 w-full bg-foreground/40 rounded-sm" />
            <div className="h-0.5 w-3/4 bg-foreground/40 rounded-sm" />
            <div className="h-0.5 w-1/3 bg-muted-foreground/30 rounded-sm mt-1" />
          </div>
        </div>
      </MiniThumb>
    )
  }
  if (variant === "simple-side") {
    return (
      <MiniThumb>
        <div className="w-full border-l-2 border-primary/40 pl-1.5 space-y-0.5">
          <div className="h-0.5 w-full bg-foreground/40 rounded-sm" />
          <div className="h-0.5 w-3/4 bg-foreground/40 rounded-sm" />
          <div className="h-0.5 w-1/3 bg-muted-foreground/30 rounded-sm mt-1" />
        </div>
      </MiniThumb>
    )
  }
  // large
  return (
    <MiniThumb>
      <div className="w-full text-center space-y-0.5">
        <div className="text-[10px] text-primary/30 leading-none">"</div>
        <div className="h-0.5 w-3/4 bg-foreground/40 rounded-sm mx-auto" />
        <div className="h-0.5 w-1/2 bg-foreground/40 rounded-sm mx-auto" />
        <div className="h-0.5 w-1/4 bg-muted-foreground/30 rounded-sm mx-auto mt-1" />
      </div>
    </MiniThumb>
  )
}

// Chart thumbnails
function ThumbChart({ type }: { type: string }) {
  if (type === "bar") {
    return (
      <MiniThumb>
        <div className="w-full flex items-end gap-0.5 h-full px-1 pb-0.5">
          {[60, 80, 45, 90].map((h, i) => (
            <div key={i} className="flex-1 bg-primary/30 rounded-t-sm" style={{ height: `${h}%` }} />
          ))}
        </div>
      </MiniThumb>
    )
  }
  if (type === "pie") {
    return (
      <MiniThumb>
        <div className="h-8 w-8 rounded-full border-4 border-primary/30 border-t-primary/60 border-r-primary/50" />
      </MiniThumb>
    )
  }
  if (type === "donut") {
    return (
      <MiniThumb>
        <div className="h-8 w-8 rounded-full border-[3px] border-primary/30 border-t-primary/60 border-r-primary/50 bg-background" />
      </MiniThumb>
    )
  }
  if (type === "line") {
    return (
      <MiniThumb>
        <svg viewBox="0 0 40 20" className="w-full h-full">
          <polyline points="2,16 12,8 22,12 38,4" fill="none" stroke="currentColor" strokeWidth="1" className="text-primary/50" />
        </svg>
      </MiniThumb>
    )
  }
  if (type === "gauge") {
    return (
      <MiniThumb>
        <div className="relative">
          <div className="h-6 w-12 rounded-t-full border-4 border-b-0 border-primary/30 border-l-primary/60" />
          <div className="text-[5px] text-center text-primary/60 font-bold -mt-0.5">72%</div>
        </div>
      </MiniThumb>
    )
  }
  if (type === "area") {
    return (
      <MiniThumb>
        <svg viewBox="0 0 40 20" className="w-full h-full">
          <polygon points="2,18 12,8 22,12 38,4 38,18" fill="currentColor" className="text-primary/15" />
          <polyline points="2,18 12,8 22,12 38,4" fill="none" stroke="currentColor" strokeWidth="1" className="text-primary/50" />
        </svg>
      </MiniThumb>
    )
  }
  if (type === "radar") {
    return (
      <MiniThumb>
        <svg viewBox="0 0 30 30" className="w-8 h-8">
          <polygon points="15,3 27,11 24,25 6,25 3,11" fill="none" stroke="currentColor" strokeWidth="0.5" className="text-muted-foreground/40" />
          <polygon points="15,7 23,13 21,22 9,22 7,13" fill="currentColor" className="text-primary/20" />
        </svg>
      </MiniThumb>
    )
  }
  if (type === "funnel") {
    return (
      <MiniThumb>
        <div className="w-full flex flex-col items-center gap-0.5">
          {[100, 75, 50, 30].map((w, i) => (
            <div key={i} className="h-2 bg-primary/25 rounded-sm" style={{ width: `${w}%` }} />
          ))}
        </div>
      </MiniThumb>
    )
  }
  // fallback
  return (
    <MiniThumb>
      <span className="text-[8px] text-muted-foreground">📊 {type}</span>
    </MiniThumb>
  )
}

// Bullets thumbnails
function ThumbBullets({ variant }: { variant: string }) {
  const symbols: Record<string, string[]> = {
    numbered: ["1", "2", "3"],
    small: ["•", "•", "•"],
    arrow: ["→", "→", "→"],
  }
  const syms = symbols[variant] ?? symbols.numbered!
  return (
    <MiniThumb>
      <div className="w-full space-y-0.5">
        {syms.map((s, i) => (
          <div key={i} className="flex items-center gap-1">
            <span className="text-[6px] text-primary/60 shrink-0 w-2 text-center">{s}</span>
            <div className="flex-1 space-y-0.5">
              <div className="h-0.5 w-2/3 bg-foreground/50 rounded-sm" />
              <div className="h-0.5 w-full bg-muted-foreground/20 rounded-sm" />
            </div>
          </div>
        ))}
      </div>
    </MiniThumb>
  )
}

// ── Element categories & factories ──

const ELEMENT_CATEGORIES: ElementCategory[] = [
  {
    name: "Basique",
    elements: [
      {
        name: "Texte + Titre",
        thumbnail: <ThumbTextHeading />,
        factory: () => [
          { type: "h2", children: [{ text: "Titre de section" }] },
          { type: "p", children: [{ text: "Votre contenu ici. Ajoutez du texte, des images ou d'autres éléments." }] },
        ],
      },
      {
        name: "Texte + Image",
        thumbnail: <ThumbTextImage />,
        factory: () => [
          { type: "h2", children: [{ text: "Titre" }] },
          { type: "p", children: [{ text: "Description de l'image et du contenu." }] },
          { type: "img", children: [{ text: "" }], query: "illustration" },
        ],
      },
      {
        name: "Deux colonnes",
        thumbnail: <ThumbTwoColumns />,
        factory: () => [
          {
            type: "compare_group",
            children: [
              { type: "compare_side", children: [{ type: "h3", children: [{ text: "Colonne 1" }] }, { type: "p", children: [{ text: "Contenu de la première colonne." }] }] },
              { type: "compare_side", children: [{ type: "h3", children: [{ text: "Colonne 2" }] }, { type: "p", children: [{ text: "Contenu de la deuxième colonne." }] }] },
            ],
          },
        ],
      },
    ],
  },
  {
    name: "Boîtes",
    elements: [
      {
        name: "Solid",
        thumbnail: <ThumbBoxes variant="solid" />,
        factory: () => [{
          type: "box_group", variant: "solid",
          children: [
            { type: "box_item", children: [{ type: "h3", children: [{ text: "Titre" }] }, { type: "p", children: [{ text: "Description" }] }] },
            { type: "box_item", children: [{ type: "h3", children: [{ text: "Titre" }] }, { type: "p", children: [{ text: "Description" }] }] },
            { type: "box_item", children: [{ type: "h3", children: [{ text: "Titre" }] }, { type: "p", children: [{ text: "Description" }] }] },
          ],
        }],
      },
      {
        name: "Outline",
        thumbnail: <ThumbBoxes variant="outline" />,
        factory: () => [{
          type: "box_group", variant: "outline",
          children: [
            { type: "box_item", children: [{ type: "h3", children: [{ text: "Titre" }] }, { type: "p", children: [{ text: "Description" }] }] },
            { type: "box_item", children: [{ type: "h3", children: [{ text: "Titre" }] }, { type: "p", children: [{ text: "Description" }] }] },
            { type: "box_item", children: [{ type: "h3", children: [{ text: "Titre" }] }, { type: "p", children: [{ text: "Description" }] }] },
          ],
        }],
      },
      {
        name: "Ligne latérale",
        thumbnail: <ThumbBoxes variant="sideline" />,
        factory: () => [{
          type: "box_group", variant: "sideline",
          children: [
            { type: "box_item", children: [{ type: "h3", children: [{ text: "Titre" }] }, { type: "p", children: [{ text: "Description" }] }] },
            { type: "box_item", children: [{ type: "h3", children: [{ text: "Titre" }] }, { type: "p", children: [{ text: "Description" }] }] },
            { type: "box_item", children: [{ type: "h3", children: [{ text: "Titre" }] }, { type: "p", children: [{ text: "Description" }] }] },
          ],
        }],
      },
      {
        name: "Jointes",
        thumbnail: <ThumbBoxes variant="joined" />,
        factory: () => [{
          type: "box_group", variant: "joined",
          children: [
            { type: "box_item", children: [{ type: "h3", children: [{ text: "Titre" }] }, { type: "p", children: [{ text: "Description" }] }] },
            { type: "box_item", children: [{ type: "h3", children: [{ text: "Titre" }] }, { type: "p", children: [{ text: "Description" }] }] },
            { type: "box_item", children: [{ type: "h3", children: [{ text: "Titre" }] }, { type: "p", children: [{ text: "Description" }] }] },
          ],
        }],
      },
      {
        name: "Avec icônes",
        thumbnail: <ThumbBoxes variant="icons" />,
        factory: () => [{
          type: "box_group", variant: "icons",
          children: [
            { type: "box_item", children: [{ type: "icon", query: "rocket", children: [{ text: "" }] }, { type: "h3", children: [{ text: "Titre" }] }, { type: "p", children: [{ text: "Description" }] }] },
            { type: "box_item", children: [{ type: "icon", query: "shield", children: [{ text: "" }] }, { type: "h3", children: [{ text: "Titre" }] }, { type: "p", children: [{ text: "Description" }] }] },
            { type: "box_item", children: [{ type: "icon", query: "target", children: [{ text: "" }] }, { type: "h3", children: [{ text: "Titre" }] }, { type: "p", children: [{ text: "Description" }] }] },
          ],
        }],
      },
      {
        name: "Feuille",
        thumbnail: <ThumbBoxes variant="leaf" />,
        factory: () => [{
          type: "box_group", variant: "leaf",
          children: [
            { type: "box_item", children: [{ type: "h3", children: [{ text: "Titre" }] }, { type: "p", children: [{ text: "Description" }] }] },
            { type: "box_item", children: [{ type: "h3", children: [{ text: "Titre" }] }, { type: "p", children: [{ text: "Description" }] }] },
            { type: "box_item", children: [{ type: "h3", children: [{ text: "Titre" }] }, { type: "p", children: [{ text: "Description" }] }] },
          ],
        }],
      },
    ],
  },
  {
    name: "Listes",
    elements: [
      {
        name: "Numérotée",
        thumbnail: <ThumbBullets variant="numbered" />,
        factory: () => [{
          type: "bullet_group", variant: "numbered",
          children: [
            { type: "bullet_item", children: [{ type: "h3", children: [{ text: "Premier point" }] }, { type: "p", children: [{ text: "Description" }] }] },
            { type: "bullet_item", children: [{ type: "h3", children: [{ text: "Deuxième point" }] }, { type: "p", children: [{ text: "Description" }] }] },
            { type: "bullet_item", children: [{ type: "h3", children: [{ text: "Troisième point" }] }, { type: "p", children: [{ text: "Description" }] }] },
          ],
        }],
      },
      {
        name: "Puces simples",
        thumbnail: <ThumbBullets variant="small" />,
        factory: () => [{
          type: "bullet_group", variant: "small",
          children: [
            { type: "bullet_item", children: [{ type: "p", children: [{ text: "Premier point" }] }] },
            { type: "bullet_item", children: [{ type: "p", children: [{ text: "Deuxième point" }] }] },
            { type: "bullet_item", children: [{ type: "p", children: [{ text: "Troisième point" }] }] },
          ],
        }],
      },
      {
        name: "Flèches",
        thumbnail: <ThumbBullets variant="arrow" />,
        factory: () => [{
          type: "bullet_group", variant: "arrow",
          children: [
            { type: "bullet_item", children: [{ type: "h3", children: [{ text: "Premier point" }] }, { type: "p", children: [{ text: "Description" }] }] },
            { type: "bullet_item", children: [{ type: "h3", children: [{ text: "Deuxième point" }] }, { type: "p", children: [{ text: "Description" }] }] },
          ],
        }],
      },
      {
        name: "Avec icônes",
        thumbnail: <ThumbBoxes variant="icons" />,
        factory: () => [{
          type: "icon_list",
          children: [
            { type: "icon_list_item", children: [{ type: "icon", query: "rocket", children: [{ text: "" }] }, { type: "h3", children: [{ text: "Fonctionnalité" }] }, { type: "p", children: [{ text: "Description" }] }] },
            { type: "icon_list_item", children: [{ type: "icon", query: "shield", children: [{ text: "" }] }, { type: "h3", children: [{ text: "Fonctionnalité" }] }, { type: "p", children: [{ text: "Description" }] }] },
          ],
        }],
      },
    ],
  },
  {
    name: "Comparaison",
    elements: [
      {
        name: "Comparer",
        thumbnail: <ThumbCompare />,
        factory: () => [{
          type: "compare_group",
          children: [
            { type: "compare_side", children: [{ type: "h3", children: [{ text: "Option A" }] }, { type: "p", children: [{ text: "Détails" }] }] },
            { type: "compare_side", children: [{ type: "h3", children: [{ text: "Option B" }] }, { type: "p", children: [{ text: "Détails" }] }] },
          ],
        }],
      },
      {
        name: "Avant / Après",
        thumbnail: <ThumbBeforeAfter />,
        factory: () => [{
          type: "before_after_group",
          children: [
            { type: "before_after_side", children: [{ type: "h3", children: [{ text: "Avant" }] }, { type: "p", children: [{ text: "État précédent" }] }] },
            { type: "before_after_side", children: [{ type: "h3", children: [{ text: "Après" }] }, { type: "p", children: [{ text: "Nouvel état" }] }] },
          ],
        }],
      },
      {
        name: "Pour / Contre",
        thumbnail: <ThumbProsCons />,
        factory: () => [{
          type: "pros_cons_group",
          children: [
            { type: "pros_item", children: [{ type: "h3", children: [{ text: "Avantages" }] }, { type: "p", children: [{ text: "Point positif" }] }] },
            { type: "cons_item", children: [{ type: "h3", children: [{ text: "Inconvénients" }] }, { type: "p", children: [{ text: "Point négatif" }] }] },
          ],
        }],
      },
    ],
  },
  {
    name: "Processus",
    elements: [
      {
        name: "Timeline",
        thumbnail: <ThumbTimeline variant="default" />,
        factory: () => [{
          type: "timeline_group", variant: "default",
          children: [
            { type: "timeline_item", children: [{ type: "h3", children: [{ text: "Étape 1" }] }, { type: "p", children: [{ text: "Description" }] }] },
            { type: "timeline_item", children: [{ type: "h3", children: [{ text: "Étape 2" }] }, { type: "p", children: [{ text: "Description" }] }] },
            { type: "timeline_item", children: [{ type: "h3", children: [{ text: "Étape 3" }] }, { type: "p", children: [{ text: "Description" }] }] },
          ],
        }],
      },
      {
        name: "Timeline minimale",
        thumbnail: <ThumbTimeline variant="minimal" />,
        factory: () => [{
          type: "timeline_group", variant: "minimal",
          children: [
            { type: "timeline_item", children: [{ type: "h3", children: [{ text: "Étape 1" }] }, { type: "p", children: [{ text: "Description" }] }] },
            { type: "timeline_item", children: [{ type: "h3", children: [{ text: "Étape 2" }] }, { type: "p", children: [{ text: "Description" }] }] },
            { type: "timeline_item", children: [{ type: "h3", children: [{ text: "Étape 3" }] }, { type: "p", children: [{ text: "Description" }] }] },
          ],
        }],
      },
      {
        name: "Timeline boîtes",
        thumbnail: <ThumbTimeline variant="minimal-boxes" />,
        factory: () => [{
          type: "timeline_group", variant: "minimal-boxes",
          children: [
            { type: "timeline_item", children: [{ type: "h3", children: [{ text: "Étape 1" }] }, { type: "p", children: [{ text: "Description" }] }] },
            { type: "timeline_item", children: [{ type: "h3", children: [{ text: "Étape 2" }] }, { type: "p", children: [{ text: "Description" }] }] },
            { type: "timeline_item", children: [{ type: "h3", children: [{ text: "Étape 3" }] }, { type: "p", children: [{ text: "Description" }] }] },
          ],
        }],
      },
      {
        name: "Flèches",
        thumbnail: <ThumbTimeline variant="arrows" />,
        factory: () => [{
          type: "sequence_arrow_group",
          children: [
            { type: "sequence_arrow_item", children: [{ type: "h3", children: [{ text: "Étape 1" }] }, { type: "p", children: [{ text: "Description" }] }] },
            { type: "sequence_arrow_item", children: [{ type: "h3", children: [{ text: "Étape 2" }] }, { type: "p", children: [{ text: "Description" }] }] },
            { type: "sequence_arrow_item", children: [{ type: "h3", children: [{ text: "Étape 3" }] }, { type: "p", children: [{ text: "Description" }] }] },
          ],
        }],
      },
      {
        name: "Pilules",
        thumbnail: <ThumbTimeline variant="pills" />,
        factory: () => [{
          type: "timeline_group", variant: "pills",
          children: [
            { type: "timeline_item", children: [{ type: "h3", children: [{ text: "Phase 1" }] }] },
            { type: "timeline_item", children: [{ type: "h3", children: [{ text: "Phase 2" }] }] },
            { type: "timeline_item", children: [{ type: "h3", children: [{ text: "Phase 3" }] }] },
          ],
        }],
      },
      {
        name: "Étiquettes obliques",
        thumbnail: <ThumbTimeline variant="slanted" />,
        factory: () => [{
          type: "timeline_group", variant: "slanted",
          children: [
            { type: "timeline_item", children: [{ type: "h3", children: [{ text: "Phase 1" }] }, { type: "p", children: [{ text: "Description" }] }] },
            { type: "timeline_item", children: [{ type: "h3", children: [{ text: "Phase 2" }] }, { type: "p", children: [{ text: "Description" }] }] },
            { type: "timeline_item", children: [{ type: "h3", children: [{ text: "Phase 3" }] }, { type: "p", children: [{ text: "Description" }] }] },
          ],
        }],
      },
      {
        name: "Cycle",
        thumbnail: <ThumbCycle />,
        factory: () => [{
          type: "cycle_group",
          children: [
            { type: "cycle_item", children: [{ type: "h3", children: [{ text: "Phase 1" }] }, { type: "p", children: [{ text: "Description" }] }] },
            { type: "cycle_item", children: [{ type: "h3", children: [{ text: "Phase 2" }] }, { type: "p", children: [{ text: "Description" }] }] },
            { type: "cycle_item", children: [{ type: "h3", children: [{ text: "Phase 3" }] }, { type: "p", children: [{ text: "Description" }] }] },
          ],
        }],
      },
      {
        name: "Escalier",
        thumbnail: <ThumbStaircase />,
        factory: () => [{
          type: "staircase_group",
          children: [
            { type: "stair_item", children: [{ type: "h3", children: [{ text: "Niveau 1" }] }, { type: "p", children: [{ text: "Description" }] }] },
            { type: "stair_item", children: [{ type: "h3", children: [{ text: "Niveau 2" }] }, { type: "p", children: [{ text: "Description" }] }] },
            { type: "stair_item", children: [{ type: "h3", children: [{ text: "Niveau 3" }] }, { type: "p", children: [{ text: "Description" }] }] },
          ],
        }],
      },
      {
        name: "Pyramide",
        thumbnail: <ThumbPyramid />,
        factory: () => [{
          type: "pyramid_group", variant: "pyramid",
          children: [
            { type: "pyramid_item", children: [{ type: "h3", children: [{ text: "Sommet" }] }, { type: "p", children: [{ text: "Le plus important" }] }] },
            { type: "pyramid_item", children: [{ type: "h3", children: [{ text: "Milieu" }] }, { type: "p", children: [{ text: "Support" }] }] },
            { type: "pyramid_item", children: [{ type: "h3", children: [{ text: "Base" }] }, { type: "p", children: [{ text: "Fondation" }] }] },
          ],
        }],
      },
      {
        name: "Entonnoir",
        thumbnail: <ThumbPyramid inverted />,
        factory: () => [{
          type: "pyramid_group", variant: "funnel",
          children: [
            { type: "pyramid_item", children: [{ type: "h3", children: [{ text: "Large" }] }, { type: "p", children: [{ text: "Début" }] }] },
            { type: "pyramid_item", children: [{ type: "h3", children: [{ text: "Moyen" }] }, { type: "p", children: [{ text: "Filtrage" }] }] },
            { type: "pyramid_item", children: [{ type: "h3", children: [{ text: "Étroit" }] }, { type: "p", children: [{ text: "Résultat" }] }] },
          ],
        }],
      },
    ],
  },
  {
    name: "Contenu",
    elements: [
      {
        name: "Citation large",
        thumbnail: <ThumbQuote variant="large" />,
        factory: () => [{
          type: "quote", variant: "large",
          children: [
            { type: "p", children: [{ text: "Votre citation ici." }] },
            { type: "p", children: [{ text: "— Attribution" }] },
          ],
        }],
      },
      {
        name: "Citation icône",
        thumbnail: <ThumbQuote variant="side-icon" />,
        factory: () => [{
          type: "quote", variant: "side-icon",
          children: [
            { type: "p", children: [{ text: "Votre citation ici." }] },
            { type: "p", children: [{ text: "— Attribution" }] },
          ],
        }],
      },
      {
        name: "Citation simple",
        thumbnail: <ThumbQuote variant="simple-side" />,
        factory: () => [{
          type: "quote", variant: "simple-side",
          children: [
            { type: "p", children: [{ text: "Votre citation ici." }] },
            { type: "p", children: [{ text: "— Attribution" }] },
          ],
        }],
      },
      {
        name: "Statistiques",
        thumbnail: <ThumbStats variant="default" />,
        factory: () => [{
          type: "stats_group", variant: "default",
          children: [
            { type: "stats_item", value: "85%", children: [{ type: "h3", children: [{ text: "Satisfaction" }] }, { type: "p", children: [{ text: "Taux client" }] }] },
            { type: "stats_item", value: "12K", children: [{ type: "h3", children: [{ text: "Utilisateurs" }] }, { type: "p", children: [{ text: "Ce mois-ci" }] }] },
            { type: "stats_item", value: "99%", children: [{ type: "h3", children: [{ text: "Uptime" }] }, { type: "p", children: [{ text: "Fiabilité" }] }] },
          ],
        }],
      },
      {
        name: "Stats cercles",
        thumbnail: <ThumbStats variant="circle" />,
        factory: () => [{
          type: "stats_group", variant: "circle",
          children: [
            { type: "stats_item", value: "85%", children: [{ type: "h3", children: [{ text: "Satisfaction" }] }] },
            { type: "stats_item", value: "92%", children: [{ type: "h3", children: [{ text: "Qualité" }] }] },
            { type: "stats_item", value: "78%", children: [{ type: "h3", children: [{ text: "Croissance" }] }] },
          ],
        }],
      },
      {
        name: "Stats barres",
        thumbnail: <ThumbStats variant="bar" />,
        factory: () => [{
          type: "stats_group", variant: "bar",
          children: [
            { type: "stats_item", value: "85%", children: [{ type: "h3", children: [{ text: "Satisfaction" }] }] },
            { type: "stats_item", value: "72%", children: [{ type: "h3", children: [{ text: "Rétention" }] }] },
            { type: "stats_item", value: "96%", children: [{ type: "h3", children: [{ text: "Uptime" }] }] },
          ],
        }],
      },
      {
        name: "Étoiles",
        thumbnail: <ThumbStats variant="star-rating" />,
        factory: () => [{
          type: "stats_group", variant: "star-rating",
          children: [
            { type: "stats_item", value: "4.5", children: [{ type: "h3", children: [{ text: "Produit" }] }] },
            { type: "stats_item", value: "4.8", children: [{ type: "h3", children: [{ text: "Service" }] }] },
            { type: "stats_item", value: "4.2", children: [{ type: "h3", children: [{ text: "Support" }] }] },
          ],
        }],
      },
      {
        name: "Points grille",
        thumbnail: <ThumbStats variant="dot-grid" />,
        factory: () => [{
          type: "stats_group", variant: "dot-grid",
          children: [
            { type: "stats_item", value: "70%", children: [{ type: "h3", children: [{ text: "Objectif A" }] }] },
            { type: "stats_item", value: "50%", children: [{ type: "h3", children: [{ text: "Objectif B" }] }] },
            { type: "stats_item", value: "90%", children: [{ type: "h3", children: [{ text: "Objectif C" }] }] },
          ],
        }],
      },
    ],
  },
  {
    name: "Images",
    elements: [
      {
        name: "2 colonnes",
        thumbnail: <ThumbGallery cols={2} />,
        factory: () => [{
          type: "image_gallery_group", variant: "2-col",
          children: [
            { type: "image_gallery_item", query: "image placeholder", children: [{ type: "p", children: [{ text: "Légende 1" }] }] },
            { type: "image_gallery_item", query: "image placeholder", children: [{ type: "p", children: [{ text: "Légende 2" }] }] },
          ],
        }],
      },
      {
        name: "3 colonnes",
        thumbnail: <ThumbGallery cols={3} />,
        factory: () => [{
          type: "image_gallery_group", variant: "3-col",
          children: [
            { type: "image_gallery_item", query: "image placeholder", children: [{ type: "p", children: [{ text: "Légende 1" }] }] },
            { type: "image_gallery_item", query: "image placeholder", children: [{ type: "p", children: [{ text: "Légende 2" }] }] },
            { type: "image_gallery_item", query: "image placeholder", children: [{ type: "p", children: [{ text: "Légende 3" }] }] },
          ],
        }],
      },
      {
        name: "4 colonnes",
        thumbnail: <ThumbGallery cols={4} />,
        factory: () => [{
          type: "image_gallery_group", variant: "4-col",
          children: [
            { type: "image_gallery_item", query: "image placeholder", children: [{ type: "p", children: [{ text: "1" }] }] },
            { type: "image_gallery_item", query: "image placeholder", children: [{ type: "p", children: [{ text: "2" }] }] },
            { type: "image_gallery_item", query: "image placeholder", children: [{ type: "p", children: [{ text: "3" }] }] },
            { type: "image_gallery_item", query: "image placeholder", children: [{ type: "p", children: [{ text: "4" }] }] },
          ],
        }],
      },
      {
        name: "Avec texte",
        thumbnail: <ThumbGallery cols={3} withText />,
        factory: () => [{
          type: "image_gallery_group", variant: "with-text",
          children: [
            { type: "image_gallery_item", query: "image placeholder", children: [{ type: "h3", children: [{ text: "Titre" }] }, { type: "p", children: [{ text: "Description de l'image" }] }] },
            { type: "image_gallery_item", query: "image placeholder", children: [{ type: "h3", children: [{ text: "Titre" }] }, { type: "p", children: [{ text: "Description de l'image" }] }] },
            { type: "image_gallery_item", query: "image placeholder", children: [{ type: "h3", children: [{ text: "Titre" }] }, { type: "p", children: [{ text: "Description de l'image" }] }] },
          ],
        }],
      },
      {
        name: "Équipe",
        thumbnail: <ThumbTeam />,
        factory: () => [{
          type: "image_gallery_group", variant: "team",
          children: [
            { type: "image_gallery_item", query: "professional headshot", children: [{ type: "h3", children: [{ text: "Nom Prénom" }] }, { type: "p", children: [{ text: "Poste" }] }] },
            { type: "image_gallery_item", query: "professional headshot", children: [{ type: "h3", children: [{ text: "Nom Prénom" }] }, { type: "p", children: [{ text: "Poste" }] }] },
            { type: "image_gallery_item", query: "professional headshot", children: [{ type: "h3", children: [{ text: "Nom Prénom" }] }, { type: "p", children: [{ text: "Poste" }] }] },
          ],
        }],
      },
    ],
  },
  {
    name: "Layouts",
    elements: [
      {
        name: "Accent gauche",
        thumbnail: <ThumbAccent position="left" />,
        factory: () => [
          { type: "h2", children: [{ text: "Titre de section" }] },
          { type: "p", children: [{ text: "Contenu textuel de votre slide avec un accent visuel à gauche." }] },
        ],
      },
      {
        name: "Accent droite",
        thumbnail: <ThumbAccent position="right" />,
        factory: () => [
          { type: "h2", children: [{ text: "Titre de section" }] },
          { type: "p", children: [{ text: "Contenu textuel de votre slide avec un accent visuel à droite." }] },
        ],
      },
      {
        name: "Accent haut",
        thumbnail: <ThumbAccent position="top" />,
        factory: () => [
          { type: "h2", children: [{ text: "Titre de section" }] },
          { type: "p", children: [{ text: "Contenu textuel sous la barre d'accent." }] },
        ],
      },
      {
        name: "Gauche pleine",
        thumbnail: <ThumbAccent position="left-fit" />,
        factory: () => [
          { type: "h2", children: [{ text: "Titre" }] },
          { type: "p", children: [{ text: "Image pleine hauteur à gauche avec contenu à droite." }] },
        ],
      },
      {
        name: "Droite pleine",
        thumbnail: <ThumbAccent position="right-fit" />,
        factory: () => [
          { type: "h2", children: [{ text: "Titre" }] },
          { type: "p", children: [{ text: "Image pleine hauteur à droite avec contenu à gauche." }] },
        ],
      },
      {
        name: "Fond image",
        thumbnail: <ThumbAccent position="bg" />,
        factory: () => [
          { type: "h2", children: [{ text: "Titre impactant" }] },
          { type: "p", children: [{ text: "Texte sur fond d'image." }] },
        ],
      },
    ],
  },
  {
    name: "Graphiques",
    elements: [
      { name: "Barres", thumbnail: <ThumbChart type="bar" />, factory: () => [{ type: "chart-bar", data: [{ label: "T1", value: 24 }, { label: "T2", value: 36 }, { label: "T3", value: 28 }, { label: "T4", value: 42 }], children: [{ text: "" }] }] },
      { name: "Courbe", thumbnail: <ThumbChart type="line" />, factory: () => [{ type: "chart-line", data: [{ label: "Jan", value: 10 }, { label: "Fév", value: 25 }, { label: "Mar", value: 18 }, { label: "Avr", value: 35 }], children: [{ text: "" }] }] },
      { name: "Camembert", thumbnail: <ThumbChart type="pie" />, factory: () => [{ type: "chart-pie", data: [{ label: "A", value: 40 }, { label: "B", value: 30 }, { label: "C", value: 20 }, { label: "D", value: 10 }], children: [{ text: "" }] }] },
      { name: "Donut", thumbnail: <ThumbChart type="donut" />, factory: () => [{ type: "chart-donut", data: [{ label: "Utilisé", value: 72 }, { label: "Libre", value: 28 }], children: [{ text: "" }] }] },
      { name: "Aire", thumbnail: <ThumbChart type="area" />, factory: () => [{ type: "chart-area", data: [{ label: "Jan", value: 10 }, { label: "Fév", value: 25 }, { label: "Mar", value: 18 }, { label: "Avr", value: 35 }], children: [{ text: "" }] }] },
      { name: "Radar", thumbnail: <ThumbChart type="radar" />, factory: () => [{ type: "chart-radar", data: [{ label: "Vitesse", value: 80 }, { label: "Force", value: 65 }, { label: "Endurance", value: 90 }, { label: "Agilité", value: 70 }, { label: "Intelligence", value: 85 }], children: [{ text: "" }] }] },
      { name: "Entonnoir", thumbnail: <ThumbChart type="funnel" />, factory: () => [{ type: "chart-funnel", data: [{ label: "Visiteurs", value: 1000 }, { label: "Leads", value: 600 }, { label: "Prospects", value: 300 }, { label: "Clients", value: 100 }], children: [{ text: "" }] }] },
      { name: "Jauge", thumbnail: <ThumbChart type="gauge" />, factory: () => [{ type: "chart-gauge", data: [{ label: "Score", value: 72 }], children: [{ text: "" }] }] },
    ],
  },
]

// ── Component ──

export function AddElementsPanel({ onInsertElements, onClose }: AddElementsPanelProps) {
  const [expandedCategory, setExpandedCategory] = useState<string | null>(null)

  return (
    <div className="flex h-full w-80 shrink-0 flex-col border-l bg-card">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-4 py-3">
        <h3 className="text-sm font-semibold">Ajouter des éléments</h3>
        <Button variant="ghost" size="icon" className="h-6 w-6" onClick={onClose}>
          <X className="h-4 w-4" />
        </Button>
      </div>

      {/* Categories */}
      <ScrollArea className="flex-1">
        <div className="p-2">
          {ELEMENT_CATEGORIES.map((category) => (
            <div key={category.name} className="mb-1">
              <button
                className={cn(
                  "flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-accent",
                  expandedCategory === category.name && "bg-accent",
                )}
                onClick={() =>
                  setExpandedCategory(expandedCategory === category.name ? null : category.name)
                }
              >
                <span className="flex-1 text-left">{category.name}</span>
                <span className="text-xs text-muted-foreground">{category.elements.length}</span>
                <ChevronRight
                  className={cn(
                    "h-4 w-4 transition-transform",
                    expandedCategory === category.name && "rotate-90",
                  )}
                />
              </button>

              {expandedCategory === category.name && (
                <div className="grid grid-cols-2 gap-2 p-2">
                  {category.elements.map((element) => (
                    <button
                      key={element.name}
                      className="flex flex-col items-center gap-1.5 rounded-lg border border-transparent p-2 transition-colors hover:border-primary/30 hover:bg-accent/50"
                      onClick={() => onInsertElements(element.factory())}
                      title={element.name}
                    >
                      {element.thumbnail}
                      <span className="text-[11px] font-medium text-muted-foreground leading-tight text-center">
                        {element.name}
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </ScrollArea>
    </div>
  )
}
