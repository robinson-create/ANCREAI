/**
 * Slide rendering utilities and shared components.
 *
 * Exports:
 * - buildThemeCSSVars: CSS variable builder
 * - AccentTopBar, DecorativeCornerDots, SlideFooter: decorative elements
 * - DEFAULT_THEME, SLIDE_REF_WIDTH, SLIDE_REF_HEIGHT, etc.
 */
import React from "react"
import type { ThemeData, DesignTokens, FooterConfig } from "@/types"

// ── Constants ──

export const SLIDE_REF_WIDTH = 960
export const SLIDE_REF_HEIGHT = 540


// ── Default theme ──

export const DEFAULT_THEME: ThemeData = {
  colors: {
    primary: "#323F50",
    secondary: "#313F4F",
    accent: "#EFEBEA",
    background: "#FFFFFF",
    text: "#323F50",
    heading: "#323F50",
    muted: "#8896A6",
  },
  fonts: { heading: "Plus Jakarta Sans", body: "DM Sans" },
  border_radius: "6px",
}

// ── Design tokens defaults ──

export const DEFAULT_DESIGN_TOKENS: DesignTokens = {
  shadow_level: "soft",
  card_style: "flat",
  accent_usage: "balanced",
}

const SHADOW_MAP: Record<string, string> = {
  none: "none",
  soft: "0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.06)",
  medium: "0 4px 6px rgba(0,0,0,0.1), 0 2px 4px rgba(0,0,0,0.08)",
}

const CARD_BORDER_MAP: Record<string, string> = {
  flat: "1px solid color-mix(in srgb, var(--pres-muted) 25%, transparent)",
  outline: "1.5px solid color-mix(in srgb, var(--pres-primary) 35%, transparent)",
  "soft-elevated": "1px solid color-mix(in srgb, var(--pres-muted) 15%, transparent)",
}

const CARD_BG_MAP: Record<string, string> = {
  flat: "white",
  outline: "transparent",
  "soft-elevated": "white",
}

// ── Theme & sizing CSS var builders ──

export function buildThemeCSSVars(theme: ThemeData): React.CSSProperties {
  const tokens = theme.design_tokens ?? DEFAULT_DESIGN_TOKENS
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
    "--pres-shadow": SHADOW_MAP[tokens.shadow_level] ?? SHADOW_MAP.soft,
    "--pres-card-border": CARD_BORDER_MAP[tokens.card_style] ?? CARD_BORDER_MAP["soft-elevated"],
    "--pres-card-bg": CARD_BG_MAP[tokens.card_style] ?? CARD_BG_MAP["soft-elevated"],
    // Map to template CSS variables
    "--primary-color": theme.colors.primary,
    "--background-color": theme.colors.background,
    "--background-text": theme.colors.text,
    "--card-color": `color-mix(in srgb, ${theme.colors.background} 92%, ${theme.colors.text})`,
    "--accent-color": theme.colors.accent,
    "--stroke": "color-mix(in srgb, " + theme.colors.muted + " 25%, transparent)",
    "--primary-text": "#FFFFFF",
    "--heading-font-family": `"${theme.fonts.heading}", system-ui, sans-serif`,
  } as React.CSSProperties
}

// ── Chart color resolver ──

const CHART_COLORS = ["#323F50", "#8896A6", "#EFEBEA", "#313F4F", "#5A6B7D", "#A8B5C2", "#D1CBC8", "#4A5968"]

export function resolveChartColors(theme: ThemeData): string[] {
  return [theme.colors.primary, theme.colors.accent, theme.colors.secondary, ...CHART_COLORS.slice(3)]
}

// ── Decorative elements ──

export function AccentTopBar() {
  return (
    <div
      className="absolute top-0 left-0 right-0 h-1"
      style={{
        background: "linear-gradient(90deg, var(--pres-primary) 0%, color-mix(in srgb, var(--pres-primary) 50%, var(--pres-accent)) 100%)",
      }}
    />
  )
}

export function DecorativeCornerDots() {
  return (
    <div className="absolute bottom-6 right-6 opacity-[0.06] pointer-events-none">
      <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
        {[0, 10, 20, 30].map(x =>
          [0, 10, 20, 30].map(y => (
            <circle key={`${x}-${y}`} cx={x + 3} cy={y + 3} r="1.5" fill="var(--pres-primary)" />
          ))
        )}
      </svg>
    </div>
  )
}

// ── Slide footer ──

export function SlideFooter({ footer }: { footer?: FooterConfig | null }) {
  if (!footer?.enabled || !footer.text) return null
  return (
    <div
      className="absolute bottom-0 left-0 right-0 px-5 py-1.5 text-[9px] font-medium tracking-wider uppercase"
      style={{
        color: "var(--pres-text)",
        fontFamily: "var(--pres-body-font)",
        backgroundColor: "transparent",
        borderTop: "1px solid color-mix(in srgb, var(--pres-muted) 30%, transparent)",
        opacity: 0.65,
      }}
    >
      {footer.text}
    </div>
  )
}
