/**
 * PDF renderer — React SSR + Playwright pipeline.
 *
 * 1. renderToStaticMarkup(SlideDocument) → HTML string
 * 2. Playwright page.setContent(html)
 * 3. Wait for data-slides-ready + all images loaded
 * 4. page.pdf() → PDF buffer
 */
import { renderToStaticMarkup } from "react-dom/server";
import { createElement } from "react";
import { SlideDocument } from "@ancre/presentation-layout";
import type { ThemeData, SlideInput } from "@ancre/presentation-layout";
import { withPage } from "./browser-pool.js";
import { readFileSync } from "fs";
import { createRequire } from "module";

const require = createRequire(import.meta.url);

// Pre-load CSS at startup
const cssContent = readFileSync(
  require.resolve("@ancre/presentation-layout/styles.css"),
  "utf-8"
);

// Font faces — local fonts as base64 data URIs for offline rendering.
// For now, use web-safe fallback. Fonts will be added in packages/presentation-layout/fonts/.
const fontFaces = `
@font-face {
  font-family: 'Plus Jakarta Sans';
  font-weight: 300 800;
  font-style: normal;
  font-display: swap;
  src: local('Plus Jakarta Sans');
}
@font-face {
  font-family: 'DM Sans';
  font-weight: 400 700;
  font-style: normal;
  font-display: swap;
  src: local('DM Sans');
}
`;

export interface PdfExportRequest {
  presentation_id: string;
  tenant_id: string;
  export_id: string;
  slides: SlideInput[];
  theme: ThemeData;
}

/**
 * Render slides to a PDF buffer using React SSR + Playwright.
 */
export async function renderPdf(
  slides: SlideInput[],
  theme: ThemeData
): Promise<Buffer> {
  // 1. React SSR → HTML string
  const html = renderToStaticMarkup(
    createElement(SlideDocument, { slides, theme, cssContent, fontFaces })
  );
  const fullHtml = "<!DOCTYPE html>" + html;

  // 2. Playwright → PDF
  return withPage(async (page) => {
    await page.setContent(fullHtml, { waitUntil: "commit" });

    // Explicit readiness: wait for data-slides-ready attribute
    await page.waitForSelector("body[data-slides-ready='true']", {
      timeout: 10_000,
    });

    // Wait for all images to load (presigned S3 URLs)
    // Pass as string — runs in browser context, not Node
    await page.waitForFunction(
      "Array.from(document.images).every(img => img.complete)",
      { timeout: 15_000 }
    );

    const pdf = await page.pdf({
      width: "960px",
      height: "540px",
      printBackground: true,
      margin: { top: "0", right: "0", bottom: "0", left: "0" },
    });

    return Buffer.from(pdf);
  });
}
