/**
 * SlidePage — wrapper for a single slide with theme CSS vars and fixed dimensions.
 */
import type { ThemeData } from "./types.js";
import { buildThemeCSSVars, SLIDE_REF_WIDTH, SLIDE_REF_HEIGHT } from "./theme.js";
import SlideTemplateRenderer from "./SlideTemplateRenderer.js";

export interface SlidePageProps {
  data: Record<string, any>;
  layoutType: string;
  theme: ThemeData;
}

export default function SlidePage({ data, layoutType, theme }: SlidePageProps) {
  const cssVars = buildThemeCSSVars(theme);
  return (
    <div
      className="slide-page"
      style={{
        ...cssVars,
        width: SLIDE_REF_WIDTH,
        height: SLIDE_REF_HEIGHT,
        overflow: "hidden",
        position: "relative",
        pageBreakAfter: "always",
      }}
    >
      <SlideTemplateRenderer layoutType={layoutType} data={data} />
    </div>
  );
}
