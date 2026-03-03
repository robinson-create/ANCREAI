/**
 * @ancre/presentation-layout — shared slide layout package.
 *
 * Pure render components for slide templates, SSR-safe.
 * No interactive editing components (those stay in the frontend).
 */

// Types
export type {
  ThemeData,
  ThemeColors,
  ThemeFonts,
  DesignTokens,
  FooterConfig,
  SlideInput,
} from "./types.js";

// Theme utilities
export {
  buildThemeCSSVars,
  DEFAULT_THEME,
  DEFAULT_DESIGN_TOKENS,
  SLIDE_REF_WIDTH,
  SLIDE_REF_HEIGHT,
} from "./theme.js";

// Data utilities
export { stripMarkdown, cleanData } from "./utils.js";

// Pure render components
export { default as StaticText } from "./StaticText.js";
export { default as StaticImage } from "./StaticImage.js";

// Template system
export { default as SlideTemplateRenderer } from "./SlideTemplateRenderer.js";
export {
  TEMPLATE_REGISTRY,
  getTemplate,
  getAllLayoutIds,
} from "./templates/index.js";
export type { TemplateEntry } from "./templates/index.js";

// PDF rendering components
export { default as SlidePage } from "./SlidePage.js";
export type { SlidePageProps } from "./SlidePage.js";
export { default as SlideDocument } from "./SlideDocument.js";
export type { SlideDocumentProps } from "./SlideDocument.js";
