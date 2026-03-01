import React, { useState, useCallback, useRef, useEffect, useMemo } from "react"
import { ChevronUp, ChevronDown, Trash2, GripVertical, ImagePlus, X, icons as lucideIcons } from "lucide-react"
import type { LucideIcon } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  AreaChart, Area, RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  ScatterChart, Scatter, CartesianGrid, XAxis, YAxis, Tooltip, Legend,
  ResponsiveContainer,
} from "recharts"
import type { Slide, SlideNode, TextLeaf, SlideUpdate, ThemeData } from "@/types"

// ── Types ──

interface SlideEditorProps {
  presentationId: string
  slide: Slide
  themeData: ThemeData | null
  onSlideUpdate: (slideId: string, update: SlideUpdate) => void
}

// ── Lucide icon resolver ──

const ICON_ROLE_SIZES: Record<string, number> = {
  inline: 16,
  card: 24,
  section: 32,
  hero: 48,
}

function SlideIcon({ iconName, role = "card" }: { iconName?: string | null; role?: string }) {
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

// ── Theme helpers ──

const DEFAULT_THEME: ThemeData = {
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

function buildThemeCSSVars(theme: ThemeData): React.CSSProperties {
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

function resolveChartColors(theme: ThemeData): string[] {
  return [theme.colors.primary, theme.colors.accent, theme.colors.secondary, ...CHART_COLORS.slice(3)]
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
          className="text-lg font-bold leading-tight mb-1.5"
          style={{
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
          className="text-base font-semibold leading-tight mb-1"
          style={{ color: "var(--pres-heading)", fontFamily: "var(--pres-heading-font)" }}
        >
          {renderChildren()}
        </h2>
      )
    case "h3":
      return (
        <h3
          className="text-sm font-semibold leading-tight mb-0.5"
          style={{ color: "var(--pres-heading)", fontFamily: "var(--pres-heading-font)" }}
        >
          {renderChildren()}
        </h3>
      )
    case "h4":
    case "h5":
    case "h6":
      return (
        <h4
          className="text-sm font-medium leading-tight mb-0.5"
          style={{ color: "var(--pres-heading)", fontFamily: "var(--pres-heading-font)" }}
        >
          {renderChildren()}
        </h4>
      )
    case "p":
      return (
        <p
          className="text-xs leading-snug mb-1"
          style={{ color: "var(--pres-text)", fontFamily: "var(--pres-body-font)" }}
        >
          {renderChildren()}
        </p>
      )

    // ── Lists ──
    case "bullet_group":
      return <ul className="space-y-0.5 mb-1.5">{renderChildren()}</ul>
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
      // Only render resolved icons — never render unresolved ones
      if (iconName) {
        return <SlideIcon iconName={iconName} role={iconRole} />
      }
      // Fallback: colored dot for unresolved icons (should not happen after normalization)
      return <span className="text-sm" style={{ color: "var(--pres-primary)" }}>●</span>
    }

    // ── Boxes ──
    case "box_group": {
      const childCount = (node.children || []).filter(c => !isTextLeaf(c)).length
      const cols = childCount <= 2 ? "grid-cols-2" : childCount === 3 ? "grid-cols-3" : "grid-cols-2"
      return <div className={`grid ${cols} gap-1.5 mb-1.5`}>{renderChildren()}</div>
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
      // Default: solid — light primary background
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
          <div className="space-y-1.5">{renderChildren()}</div>
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
      return <div className="space-y-0.5 mb-1.5">{renderChildren()}</div>
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
      return <div className={`grid ${cols} gap-2 mb-1.5`}>{renderChildren()}</div>
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
      // Default
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
  slide,
  themeData,
  onSlideUpdate,
}: SlideEditorProps) {
  const [localNotes, setLocalNotes] = useState(slide.speaker_notes || "")
  const [localBgColor, setLocalBgColor] = useState(slide.bg_color || "#ffffff")
  const [showImageInput, setShowImageInput] = useState(false)
  const [imageUrl, setImageUrl] = useState("")
  const saveTimerRef = useRef<ReturnType<typeof setTimeout>>()

  const theme = themeData ?? DEFAULT_THEME
  const cssVars = useMemo(() => buildThemeCSSVars(theme), [theme])
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
          <Button
            variant="outline"
            size="sm"
            className="h-7 gap-1 text-xs shrink-0"
            onClick={() => setShowImageInput(true)}
          >
            <ImagePlus className="h-3.5 w-3.5" />
            Image
          </Button>
        )}
      </div>

      {/* Slide canvas */}
      <div className="flex-1 min-h-0 overflow-auto p-6 flex items-start justify-center">
        <div
          className="w-full max-w-3xl aspect-video rounded-lg shadow-lg border overflow-hidden relative shrink-0"
          style={{
            ...cssVars,
            backgroundColor: slideBg,
            color: "var(--pres-text)",
            fontFamily: "var(--pres-body-font)",
          }}
        >
          {/* Background image (layout: background) */}
          {rootImageUrl && slide.layout_type === "background" && (
            <img src={rootImageUrl} alt="" className="absolute inset-0 w-full h-full object-cover" />
          )}
          {rootImageUrl && slide.layout_type === "background" && (
            <div className="absolute inset-0 bg-black/40" />
          )}

          {/* Layout with side image */}
          {rootImageUrl && ["left", "right", "left-fit", "right-fit"].includes(slide.layout_type) ? (
            <div className={`flex h-full ${slide.layout_type.startsWith("right") ? "flex-row" : "flex-row-reverse"}`}>
              <div className="flex-1 p-5 pl-12 overflow-hidden relative">
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
                <img src={rootImageUrl} alt="" className="w-full h-full object-cover" />
              </div>
            </div>
          ) : (
            <div className={`p-5 pl-12 h-full ${slide.layout_type === "background" && rootImageUrl ? "relative z-10" : ""}`}>
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
