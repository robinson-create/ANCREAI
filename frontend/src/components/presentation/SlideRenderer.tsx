/**
 * Shared slide rendering primitives.
 *
 * Used by both the main SlideEditor (editable) and SlidePreviewCard (read-only thumbnail).
 */
import React, { useRef, useCallback } from "react"
import { icons as lucideIcons } from "lucide-react"
import type { LucideIcon } from "lucide-react"
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  AreaChart, Area, RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  ScatterChart, Scatter, CartesianGrid, XAxis, YAxis, Tooltip, Legend,
  ResponsiveContainer,
} from "recharts"
import type { SlideNode, TextLeaf, ThemeData, SlideSizing } from "@/types"

// ── Constants ──

export const SLIDE_REF_WIDTH = 960
export const SLIDE_REF_HEIGHT = 540

export const CARD_INNER_MAX: Record<string, number> = { S: 640, M: 800, L: 920 }

export const FONT_SCALE_MAP: Record<string, Record<string, string>> = {
  L: { h1: "40px", h2: "35px", h3: "24px", p: "17px" },
  M: { h1: "32px", h2: "28px", h3: "21px", p: "15px" },
  S: { h1: "25px", h2: "21px", h3: "17px", p: "13px" },
}

export const BLOCK_SPACING_MAP: Record<string, string> = {
  tight: "5px",
  normal: "12px",
  loose: "20px",
}

// ── Default theme ──

export const DEFAULT_THEME: ThemeData = {
  colors: {
    primary: "#6C63FF",
    secondary: "#2D2B55",
    accent: "#FF6584",
    background: "#FFFFFF",
    text: "#333333",
    heading: "#1a1a2e",
    muted: "#6b7280",
  },
  fonts: { heading: "Inter", body: "Inter" },
  border_radius: "12px",
}

// ── Theme & sizing CSS var builders ──

export function buildThemeCSSVars(theme: ThemeData): React.CSSProperties {
  return {
    "--pres-primary": theme.colors.primary,
    "--pres-secondary": theme.colors.secondary,
    "--pres-accent": theme.colors.accent,
    "--pres-bg": theme.colors.background,
    "--pres-text": theme.colors.text,
    "--pres-heading": theme.colors.heading,
    "--pres-muted": theme.colors.muted,
    "--pres-heading-font": `"${theme.fonts.heading}", system-ui, sans-serif`,
    "--pres-body-font": `"${theme.fonts.body}", system-ui, sans-serif`,
    "--pres-radius": theme.border_radius,
  } as React.CSSProperties
}

export function buildSizingCSSVars(sizing?: SlideSizing | null): React.CSSProperties {
  const scale = sizing?.font_scale ?? "M"
  const spacing = sizing?.block_spacing ?? "normal"
  const fonts = FONT_SCALE_MAP[scale] ?? FONT_SCALE_MAP["M"]!
  return {
    "--slide-h1-size": fonts!.h1,
    "--slide-h2-size": fonts!.h2,
    "--slide-h3-size": fonts!.h3,
    "--slide-p-size": fonts!.p,
    "--slide-block-gap": BLOCK_SPACING_MAP[spacing] ?? BLOCK_SPACING_MAP["normal"],
  } as React.CSSProperties
}

// ── Lucide icon resolver ──

const ICON_ROLE_SIZES: Record<string, number> = {
  inline: 16,
  card: 24,
  section: 32,
  hero: 48,
}

export function SlideIcon({ iconName, role = "card" }: { iconName?: string | null; role?: string }) {
  if (!iconName) return null
  const IconComponent = (lucideIcons as Record<string, LucideIcon>)[iconName]
  if (!IconComponent) return null
  const size = ICON_ROLE_SIZES[role] ?? 24
  return (
    <IconComponent
      size={size}
      strokeWidth={size >= 32 ? 1.5 : 1.75}
      style={{ color: "var(--pres-primary)" }}
      className="shrink-0"
    />
  )
}

// ── Chart helpers ──

type AnyRecord = Record<string, unknown>

const CHART_COLORS = ["#6C63FF", "#FF6584", "#2D2B55", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4"]

function getChartData(node: SlideNode): AnyRecord[] {
  return Array.isArray(node.data) ? (node.data as AnyRecord[]) : []
}

function getLabelKey(data: AnyRecord[]): string {
  if (data.length === 0) return "label"
  const s = data[0]!
  if ("label" in s) return "label"
  if ("name" in s) return "name"
  return "label"
}

function getValueKey(data: AnyRecord[]): string {
  if (data.length === 0) return "value"
  const s = data[0]!
  if ("value" in s) return "value"
  if ("count" in s) return "count"
  if ("y" in s) return "y"
  return "value"
}

function ChartPlaceholder({ type }: { type: string }) {
  return (
    <div
      className="mb-1.5 flex flex-col items-center justify-center gap-1 border border-dashed p-4"
      style={{
        backgroundColor: "color-mix(in srgb, var(--pres-primary) 5%, transparent)",
        borderColor: "color-mix(in srgb, var(--pres-primary) 30%, transparent)",
        borderRadius: "var(--pres-radius)",
      }}
    >
      <span className="text-lg" style={{ color: "var(--pres-primary)" }}>
        {type === "pie" || type === "donut" ? "◐" : type === "bar" ? "▊" : type === "line" ? "📈" : type === "radar" ? "⬡" : "📊"}
      </span>
      <span className="text-[10px] capitalize" style={{ color: "var(--pres-muted)" }}>
        {type.replace(/-/g, " ")} chart
      </span>
    </div>
  )
}

export function resolveChartColors(theme: ThemeData): string[] {
  return [theme.colors.primary, theme.colors.accent, theme.colors.secondary, ...CHART_COLORS.slice(3)]
}

// ── Type guard ──

export function isTextLeaf(node: SlideNode | TextLeaf): node is TextLeaf {
  return "text" in node
}

// ── Text leaf renderer ──

export function TextLeafRenderer({
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

// ── Main node renderer ──

export function SlideNodeRenderer({
  node,
  editable,
  onNodeChange,
  themeColors,
}: {
  node: SlideNode
  editable: boolean
  onNodeChange?: (updated: SlideNode) => void
  themeColors: string[]
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
          themeColors={themeColors}
        />
      )
    })

  switch (node.type) {
    // ── Text ──
    case "h1":
      return (
        <h1
          className="font-bold leading-tight mb-1.5"
          style={{
            fontSize: "var(--slide-h1-size, 2em)",
            background: "linear-gradient(135deg, var(--pres-primary), var(--pres-accent))",
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
            backgroundClip: "text",
            fontFamily: "var(--pres-heading-font)",
          }}
        >
          {renderChildren()}
        </h1>
      )
    case "h2":
      return (
        <h2
          className="font-semibold leading-tight mb-1"
          style={{ fontSize: "var(--slide-h2-size, 1.8em)", color: "var(--pres-heading)", fontFamily: "var(--pres-heading-font)" }}
        >
          {renderChildren()}
        </h2>
      )
    case "h3":
      return (
        <h3
          className="font-semibold leading-tight mb-0.5"
          style={{ fontSize: "var(--slide-h3-size, 1.4em)", color: "var(--pres-heading)", fontFamily: "var(--pres-heading-font)" }}
        >
          {renderChildren()}
        </h3>
      )
    case "h4":
    case "h5":
    case "h6":
      return (
        <h4
          className="font-medium leading-tight mb-0.5"
          style={{ fontSize: "var(--slide-h3-size, 1.4em)", color: "var(--pres-heading)", fontFamily: "var(--pres-heading-font)" }}
        >
          {renderChildren()}
        </h4>
      )
    case "p":
      return (
        <p
          className="leading-snug mb-1"
          style={{ fontSize: "var(--slide-p-size, 1em)", color: "var(--pres-text)", fontFamily: "var(--pres-body-font)" }}
        >
          {renderChildren()}
        </p>
      )

    // ── Lists ──
    case "bullet_group":
      return <ul className="mb-1.5" style={{ display: "flex", flexDirection: "column", gap: "var(--slide-block-gap, 0.75rem)" }}>{renderChildren()}</ul>
    case "bullet_item":
      return (
        <li
          className="text-xs leading-snug flex items-start gap-1.5"
          style={{ color: "var(--pres-text)", fontFamily: "var(--pres-body-font)" }}
        >
          <span
            className="mt-[5px] h-1.5 w-1.5 rounded-full shrink-0"
            style={{ backgroundColor: "var(--pres-primary)" }}
          />
          <span className="flex-1">{renderChildren()}</span>
        </li>
      )
    case "icon_list":
      return <div className="grid grid-cols-2 gap-1.5 mb-1.5">{renderChildren()}</div>
    case "icon_list_item":
      return (
        <div
          className="flex gap-1.5 items-start p-1.5"
          style={{
            backgroundColor: "color-mix(in srgb, var(--pres-primary) 8%, transparent)",
            borderRadius: "var(--pres-radius)",
          }}
        >
          {renderChildren()}
        </div>
      )
    case "icon": {
      const iconName = node.icon_name as string | undefined
      const iconRole = (node.icon_role as string) || "card"
      if (iconName) {
        return <SlideIcon iconName={iconName} role={iconRole} />
      }
      return <span className="text-sm" style={{ color: "var(--pres-primary)" }}>●</span>
    }

    // ── Boxes ──
    case "box_group": {
      const childCount = (node.children || []).filter(c => !isTextLeaf(c)).length
      const cols = childCount <= 2 ? "grid-cols-2"
        : childCount === 3 ? "grid-cols-3"
        : childCount <= 4 ? "grid-cols-2"
        : "grid-cols-3"
      return <div className={`grid ${cols} mb-1.5`} style={{ gap: "var(--slide-block-gap, 0.375rem)" }}>{renderChildren()}</div>
    }
    case "box_item": {
      const variant = node.variant || "solid"
      if (variant === "outline") {
        return (
          <div
            className="p-2 border-2 bg-transparent"
            style={{ borderColor: "var(--pres-primary)", borderRadius: "var(--pres-radius)" }}
          >
            {renderChildren()}
          </div>
        )
      }
      if (variant === "sideline") {
        return (
          <div
            className="border-l-[3px] py-1.5 pl-2.5 pr-1.5"
            style={{ borderLeftColor: "var(--pres-primary)" }}
          >
            {renderChildren()}
          </div>
        )
      }
      return (
        <div
          className="p-2"
          style={{
            backgroundColor: "color-mix(in srgb, var(--pres-primary) 10%, transparent)",
            borderRadius: "var(--pres-radius)",
            borderLeft: "3px solid var(--pres-primary)",
          }}
        >
          {renderChildren()}
        </div>
      )
    }

    // ── Comparison ──
    case "compare_group":
    case "before_after_group":
    case "pros_cons_group":
      return <div className="grid grid-cols-2 gap-2 mb-1.5">{renderChildren()}</div>
    case "compare_side":
    case "before_after_side":
      return (
        <div
          className="border p-2"
          style={{
            borderColor: "color-mix(in srgb, var(--pres-primary) 30%, transparent)",
            borderRadius: "var(--pres-radius)",
            borderTop: "3px solid var(--pres-primary)",
          }}
        >
          {renderChildren()}
        </div>
      )
    case "pros_item":
      return (
        <div className="border p-2" style={{ borderColor: "#22c55e50", backgroundColor: "#22c55e08", borderRadius: "var(--pres-radius)", borderTop: "3px solid #22c55e" }}>
          {renderChildren()}
        </div>
      )
    case "cons_item":
      return (
        <div className="border p-2" style={{ borderColor: "#ef444450", backgroundColor: "#ef444408", borderRadius: "var(--pres-radius)", borderTop: "3px solid #ef4444" }}>
          {renderChildren()}
        </div>
      )

    // ── Process ──
    case "timeline_group":
      return (
        <div className="relative mb-1.5 pl-4">
          <div className="absolute left-1.5 top-0 bottom-0 w-0.5" style={{ backgroundColor: "var(--pres-primary)" }} />
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--slide-block-gap, 0.375rem)" }}>{renderChildren()}</div>
        </div>
      )
    case "timeline_item":
      return (
        <div className="relative pl-3 pb-1">
          <div
            className="absolute -left-[14px] top-1.5 h-2.5 w-2.5 rounded-full border-2"
            style={{ backgroundColor: "var(--pres-bg)", borderColor: "var(--pres-primary)" }}
          />
          {renderChildren()}
        </div>
      )
    case "cycle_group": {
      const childCount = (node.children || []).filter(c => !isTextLeaf(c)).length
      const cols = childCount <= 3 ? `grid-cols-${childCount}` : "grid-cols-3"
      return <div className={`grid ${cols} gap-1.5 mb-1.5`}>{renderChildren()}</div>
    }
    case "cycle_item":
      return (
        <div
          className="p-1.5 text-center border"
          style={{
            borderColor: "color-mix(in srgb, var(--pres-primary) 30%, transparent)",
            borderRadius: "var(--pres-radius)",
          }}
        >
          {renderChildren()}
        </div>
      )
    case "arrow_list":
      return (
        <div className="flex items-stretch gap-1 mb-1.5">
          {(node.children || []).map((child, i) => {
            if (isTextLeaf(child)) return null
            const total = (node.children || []).filter(c => !isTextLeaf(c)).length
            return (
              <React.Fragment key={i}>
                <div
                  className="flex-1 p-1.5 text-center"
                  style={{
                    backgroundColor: "color-mix(in srgb, var(--pres-primary) 12%, transparent)",
                    borderRadius: "var(--pres-radius)",
                  }}
                >
                  <SlideNodeRenderer node={child} editable={editable} onNodeChange={(u) => handleChildNodeChange(i, u)} themeColors={themeColors} />
                </div>
                {i < total - 1 && (
                  <div className="flex items-center px-0.5 text-sm font-bold" style={{ color: "var(--pres-primary)" }}>→</div>
                )}
              </React.Fragment>
            )
          })}
        </div>
      )
    case "arrow_list_item":
      return <div>{renderChildren()}</div>
    case "sequence_arrow_group":
      return <div className="space-y-0 mb-1.5">{renderChildren()}</div>
    case "sequence_arrow_item":
      return (
        <div className="mb-0">
          <div
            className="p-1.5"
            style={{ backgroundColor: "color-mix(in srgb, var(--pres-primary) 10%, transparent)", borderRadius: "var(--pres-radius)", borderLeft: "3px solid var(--pres-primary)" }}
          >
            {renderChildren()}
          </div>
          <div className="flex justify-center">
            <div style={{ width: 0, height: 0, borderLeft: "6px solid transparent", borderRight: "6px solid transparent", borderTop: "8px solid var(--pres-primary)" }} />
          </div>
        </div>
      )
    case "staircase_group":
      return <div className="mb-1.5" style={{ display: "flex", flexDirection: "column", gap: "var(--slide-block-gap, 0.375rem)" }}>{renderChildren()}</div>
    case "stair_item":
      return (
        <div className="flex items-center gap-2 border-b pb-1 ml-3 first:ml-0" style={{ borderColor: "color-mix(in srgb, var(--pres-muted) 30%, transparent)" }}>
          <div
            className="shrink-0 flex items-center justify-center h-6 w-6 text-[9px] font-bold"
            style={{ backgroundColor: "var(--pres-primary)", color: "var(--pres-bg)", borderRadius: "var(--pres-radius)" }}
          >
            #
          </div>
          <div className="flex-1">{renderChildren()}</div>
        </div>
      )
    case "pyramid_group":
      return <div className="flex flex-col items-center gap-0.5 mb-1.5">{renderChildren()}</div>
    case "pyramid_item":
      return (
        <div
          className="p-1.5 text-center w-full"
          style={{
            backgroundColor: "color-mix(in srgb, var(--pres-primary) 15%, transparent)",
            borderRadius: "var(--pres-radius)",
            borderLeft: "3px solid var(--pres-primary)",
          }}
        >
          {renderChildren()}
        </div>
      )

    // ── Content ──
    case "quote":
      return (
        <blockquote className="py-2 text-center mb-1.5">
          <div className="text-xl font-serif leading-none mb-0.5" style={{ color: "var(--pres-primary)" }}>&ldquo;</div>
          <div
            className="text-xs italic leading-relaxed px-4"
            style={{ color: "var(--pres-text)", fontFamily: "var(--pres-body-font)" }}
          >
            {renderChildren()}
          </div>
          <div className="text-xl font-serif leading-none mt-0.5" style={{ color: "var(--pres-primary)" }}>&rdquo;</div>
        </blockquote>
      )
    case "stats_group": {
      const childCount = (node.children || []).filter(c => !isTextLeaf(c)).length
      const cols = childCount <= 2 ? "grid-cols-2" : childCount === 3 ? "grid-cols-3" : "grid-cols-4"
      return <div className={`grid ${cols} mb-1.5`} style={{ gap: "var(--slide-block-gap, 0.5rem)" }}>{renderChildren()}</div>
    }
    case "stats_item": {
      const variant = node.variant || "default"
      if (variant === "circle") {
        return (
          <div className="flex flex-col items-center text-center p-1.5">
            <div
              className="flex h-12 w-12 items-center justify-center rounded-full border-[3px] text-sm font-bold"
              style={{ borderColor: "var(--pres-primary)", color: "var(--pres-primary)" }}
            >
              {node.value || "—"}
            </div>
            <div className="mt-1">{renderChildren()}</div>
          </div>
        )
      }
      if (variant === "bar") {
        const numValue = parseFloat(String(node.value || "0").replace(/[^0-9.]/g, ""))
        const percent = isNaN(numValue) ? 50 : Math.min(numValue, 100)
        return (
          <div className="p-2" style={{ borderRadius: "var(--pres-radius)" }}>
            <div className="text-lg font-bold mb-0.5" style={{ color: "var(--pres-primary)" }}>{node.value || "—"}</div>
            <div className="h-1.5 w-full overflow-hidden rounded-full" style={{ backgroundColor: "color-mix(in srgb, var(--pres-muted) 20%, transparent)" }}>
              <div className="h-full rounded-full transition-all" style={{ width: `${percent}%`, backgroundColor: "var(--pres-primary)" }} />
            </div>
            <div className="mt-1">{renderChildren()}</div>
          </div>
        )
      }
      return (
        <div
          className="border p-2 text-center"
          style={{
            borderColor: "color-mix(in srgb, var(--pres-primary) 25%, transparent)",
            borderRadius: "var(--pres-radius)",
          }}
        >
          <div className="text-lg font-bold" style={{ color: "var(--pres-primary)" }}>
            {node.value || "—"}
          </div>
          {renderChildren()}
        </div>
      )
    }

    case "image_gallery_group":
      return <div className="grid grid-cols-3 gap-1.5 mb-1.5">{renderChildren()}</div>
    case "image_gallery_item":
      return (
        <div className="overflow-hidden border" style={{ borderRadius: "var(--pres-radius)" }}>
          <div
            className="flex items-center justify-center py-3 text-[10px]"
            style={{ backgroundColor: "color-mix(in srgb, var(--pres-muted) 10%, transparent)", color: "var(--pres-muted)" }}
          >
            {node.query || "Image"}
          </div>
          {renderChildren()}
        </div>
      )

    // ── Charts (real recharts for supported types) ──
    case "chart-bar": {
      const data = getChartData(node)
      if (data.length === 0) return <ChartPlaceholder type="bar" />
      const lk = getLabelKey(data), vk = getValueKey(data)
      return (
        <div className="mb-1.5 border p-1.5" style={{ borderRadius: "var(--pres-radius)" }}>
          <ResponsiveContainer width="100%" height={110}>
            <BarChart data={data}>
              <CartesianGrid vertical={false} strokeDasharray="3 3" stroke="color-mix(in srgb, var(--pres-muted) 20%, transparent)" />
              <XAxis dataKey={lk} tick={{ fontSize: 8 }} />
              <YAxis tick={{ fontSize: 8 }} width={30} />
              <Tooltip contentStyle={{ fontSize: 10 }} />
              <Bar dataKey={vk} radius={[3, 3, 0, 0]}>
                {data.map((_, i) => <Cell key={i} fill={themeColors[i % themeColors.length]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )
    }
    case "chart-line": {
      const data = getChartData(node)
      if (data.length === 0) return <ChartPlaceholder type="line" />
      const lk = getLabelKey(data), vk = getValueKey(data)
      return (
        <div className="mb-1.5 border p-1.5" style={{ borderRadius: "var(--pres-radius)" }}>
          <ResponsiveContainer width="100%" height={110}>
            <LineChart data={data}>
              <CartesianGrid vertical={false} strokeDasharray="3 3" />
              <XAxis dataKey={lk} tick={{ fontSize: 8 }} />
              <YAxis tick={{ fontSize: 8 }} width={30} />
              <Tooltip contentStyle={{ fontSize: 10 }} />
              <Line type="monotone" dataKey={vk} stroke={themeColors[0]} strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )
    }
    case "chart-pie":
    case "chart-donut": {
      const data = getChartData(node)
      if (data.length === 0) return <ChartPlaceholder type={node.type === "chart-donut" ? "donut" : "pie"} />
      const lk = getLabelKey(data), vk = getValueKey(data)
      const innerRadius = node.type === "chart-donut" ? 25 : 0
      return (
        <div className="mb-1.5 border p-1.5" style={{ borderRadius: "var(--pres-radius)" }}>
          <ResponsiveContainer width="100%" height={130}>
            <PieChart>
              <Pie data={data} dataKey={vk} nameKey={lk} innerRadius={innerRadius} outerRadius={50} labelLine={false}
                label={({ percent }: { percent?: number }) => percent ? `${Math.round(percent * 100)}%` : ""}>
                {data.map((_, i) => <Cell key={i} fill={themeColors[i % themeColors.length]} />)}
              </Pie>
              <Tooltip contentStyle={{ fontSize: 10 }} />
              <Legend wrapperStyle={{ fontSize: 8 }} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      )
    }
    case "chart-area": {
      const data = getChartData(node)
      if (data.length === 0) return <ChartPlaceholder type="area" />
      const lk = getLabelKey(data), vk = getValueKey(data)
      return (
        <div className="mb-1.5 border p-1.5" style={{ borderRadius: "var(--pres-radius)" }}>
          <ResponsiveContainer width="100%" height={110}>
            <AreaChart data={data}>
              <defs>
                <linearGradient id={`areaGrad-${node.type}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={themeColors[0]} stopOpacity={0.3} />
                  <stop offset="95%" stopColor={themeColors[0]} stopOpacity={0.05} />
                </linearGradient>
              </defs>
              <CartesianGrid vertical={false} strokeDasharray="3 3" />
              <XAxis dataKey={lk} tick={{ fontSize: 8 }} />
              <YAxis tick={{ fontSize: 8 }} width={30} />
              <Tooltip contentStyle={{ fontSize: 10 }} />
              <Area type="monotone" dataKey={vk} stroke={themeColors[0]} fill={`url(#areaGrad-${node.type})`} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )
    }
    case "chart-radar": {
      const data = getChartData(node)
      if (data.length === 0) return <ChartPlaceholder type="radar" />
      const lk = getLabelKey(data), vk = getValueKey(data)
      return (
        <div className="mb-1.5 border p-1.5" style={{ borderRadius: "var(--pres-radius)" }}>
          <ResponsiveContainer width="100%" height={130}>
            <RadarChart data={data} outerRadius={45}>
              <PolarGrid />
              <PolarAngleAxis dataKey={lk} tick={{ fontSize: 7 }} />
              <PolarRadiusAxis tick={{ fontSize: 6 }} />
              <Radar dataKey={vk} stroke={themeColors[0]} fill={themeColors[0]} fillOpacity={0.2} />
              <Tooltip contentStyle={{ fontSize: 10 }} />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      )
    }
    case "chart-scatter": {
      const data = getChartData(node)
      if (data.length === 0) return <ChartPlaceholder type="scatter" />
      return (
        <div className="mb-1.5 border p-1.5" style={{ borderRadius: "var(--pres-radius)" }}>
          <ResponsiveContainer width="100%" height={110}>
            <ScatterChart>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="x" tick={{ fontSize: 8 }} />
              <YAxis dataKey="y" tick={{ fontSize: 8 }} width={30} />
              <Tooltip contentStyle={{ fontSize: 10 }} />
              <Scatter data={data} fill={themeColors[0]} />
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      )
    }

    // Exotic charts — styled placeholder
    case "chart-funnel":
    case "chart-treemap":
    case "chart-radial-bar":
    case "chart-waterfall":
    case "chart-nightingale":
    case "chart-gauge":
    case "chart-sunburst":
    case "chart-heatmap":
      return <ChartPlaceholder type={node.type.replace("chart-", "")} />

    // ── Image ──
    case "img":
      return (
        <div
          className="flex items-center justify-center py-4 mb-1.5 border border-dashed"
          style={{
            backgroundColor: "color-mix(in srgb, var(--pres-muted) 8%, transparent)",
            borderColor: "color-mix(in srgb, var(--pres-muted) 30%, transparent)",
            borderRadius: "var(--pres-radius)",
          }}
        >
          <span className="text-xs" style={{ color: "var(--pres-muted)" }}>
            {node.url ? "Image" : "Emplacement image"}
          </span>
        </div>
      )

    default:
      return <div className="mb-1">{renderChildren()}</div>
  }
}
