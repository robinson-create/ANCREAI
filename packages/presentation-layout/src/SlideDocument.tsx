/**
 * SlideDocument — full HTML document for multi-page slide rendering.
 *
 * Used by the PDF export pipeline:
 * 1. renderToStaticMarkup(SlideDocument) → HTML string
 * 2. Playwright page.setContent(html) → page.pdf()
 *
 * The body has data-slides-ready="true" for explicit readiness detection.
 */
import type { ThemeData, SlideInput } from "./types.js";
import SlidePage from "./SlidePage.js";
import { SLIDE_REF_WIDTH, SLIDE_REF_HEIGHT } from "./theme.js";

export interface SlideDocumentProps {
  slides: SlideInput[];
  theme: ThemeData;
  /** Pre-compiled Tailwind CSS content. */
  cssContent: string;
  /** @font-face rules (base64 data URIs or local paths). */
  fontFaces: string;
}

export default function SlideDocument({
  slides,
  theme,
  cssContent,
  fontFaces,
}: SlideDocumentProps) {
  return (
    <html>
      <head>
        <meta charSet="utf-8" />
        <style dangerouslySetInnerHTML={{ __html: fontFaces }} />
        <style dangerouslySetInnerHTML={{ __html: cssContent }} />
        <style
          dangerouslySetInnerHTML={{
            __html: `
          @page { size: ${SLIDE_REF_WIDTH}px ${SLIDE_REF_HEIGHT}px; margin: 0; }
          * { margin: 0; padding: 0; box-sizing: border-box; }
          body { margin: 0; }
          .slide-page {
            width: ${SLIDE_REF_WIDTH}px;
            height: ${SLIDE_REF_HEIGHT}px;
            overflow: hidden;
            position: relative;
            page-break-after: always;
          }
        `,
          }}
        />
      </head>
      <body data-slides-ready="true">
        {slides.map((slide, i) => (
          <SlidePage
            key={i}
            data={slide.data}
            layoutType={slide.layoutType}
            theme={theme}
          />
        ))}
      </body>
    </html>
  );
}
