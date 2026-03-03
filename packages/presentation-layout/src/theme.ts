/**
 * Theme utilities and constants — CSS variable builders, default theme, decorative elements.
 */
import React from "react";
import type { ThemeData, DesignTokens } from "./types.js";

export const SLIDE_REF_WIDTH = 960;
export const SLIDE_REF_HEIGHT = 540;

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
};

export const DEFAULT_DESIGN_TOKENS: DesignTokens = {
  shadow_level: "soft",
  card_style: "flat",
  accent_usage: "balanced",
};

const SHADOW_MAP: Record<string, string> = {
  none: "none",
  soft: "0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.06)",
  medium: "0 4px 6px rgba(0,0,0,0.1), 0 2px 4px rgba(0,0,0,0.08)",
};

const CARD_BORDER_MAP: Record<string, string> = {
  flat: "1px solid color-mix(in srgb, var(--pres-muted) 25%, transparent)",
  outline:
    "1.5px solid color-mix(in srgb, var(--pres-primary) 35%, transparent)",
  "soft-elevated":
    "1px solid color-mix(in srgb, var(--pres-muted) 15%, transparent)",
};

const CARD_BG_MAP: Record<string, string> = {
  flat: "white",
  outline: "transparent",
  "soft-elevated": "white",
};

export function buildThemeCSSVars(
  theme: ThemeData
): React.CSSProperties {
  const tokens = theme.design_tokens ?? DEFAULT_DESIGN_TOKENS;
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
    "--pres-card-border":
      CARD_BORDER_MAP[tokens.card_style] ?? CARD_BORDER_MAP["soft-elevated"],
    "--pres-card-bg":
      CARD_BG_MAP[tokens.card_style] ?? CARD_BG_MAP["soft-elevated"],
    // Map to template CSS variables
    "--primary-color": theme.colors.primary,
    "--background-color": theme.colors.background,
    "--background-text": theme.colors.text,
    "--card-color": `color-mix(in srgb, ${theme.colors.background} 92%, ${theme.colors.text})`,
    "--accent-color": theme.colors.accent,
    "--stroke":
      "color-mix(in srgb, " + theme.colors.muted + " 25%, transparent)",
    "--primary-text": "#FFFFFF",
    "--heading-font-family": `"${theme.fonts.heading}", system-ui, sans-serif`,
  } as React.CSSProperties;
}
