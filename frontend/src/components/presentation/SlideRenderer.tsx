/**
 * Slide rendering utilities and shared components.
 *
 * Core theme/sizing logic is imported from @ancre/presentation-layout
 * and re-exported here for backward compatibility with existing imports.
 */
import type { ThemeData, FooterConfig } from "@/types"
import {
  buildThemeCSSVars,
  DEFAULT_THEME,
  DEFAULT_DESIGN_TOKENS,
  SLIDE_REF_WIDTH,
  SLIDE_REF_HEIGHT,
} from "@ancre/presentation-layout"

// Re-export shared utilities for backward compatibility
export {
  buildThemeCSSVars,
  DEFAULT_THEME,
  DEFAULT_DESIGN_TOKENS,
  SLIDE_REF_WIDTH,
  SLIDE_REF_HEIGHT,
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
