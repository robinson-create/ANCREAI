/**
 * Shared types for presentation theming and layout.
 */

export interface ThemeColors {
  primary: string;
  secondary: string;
  accent: string;
  background: string;
  text: string;
  heading: string;
  muted: string;
}

export interface ThemeFonts {
  heading: string;
  body: string;
}

export interface DesignTokens {
  shadow_level: "none" | "soft" | "medium";
  card_style: "flat" | "outline" | "soft-elevated";
  accent_usage: "minimal" | "balanced" | "strong";
}

export interface ThemeData {
  colors: ThemeColors;
  fonts: ThemeFonts;
  border_radius: string;
  design_tokens?: DesignTokens;
}

export interface FooterConfig {
  enabled: boolean;
  text: string;
  style?: "minimal" | "accent";
}

export interface SlideInput {
  layoutType: string;
  data: Record<string, any>;
}
