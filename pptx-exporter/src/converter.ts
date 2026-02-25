/**
 * Slide converter — orchestrates pptxgenjs to build the full deck.
 */

import PptxGenJS from "pptxgenjs";
import type { ExportRequest, ResolvedSlide, ResolvedBox } from "./types";
import { addTextBox, addBulletGroup } from "./modules/text";
import { addImage } from "./modules/images";
import { addShape } from "./modules/shapes";

/** Convert a resolved export request into a pptxgenjs presentation buffer. */
export async function convertToBuffer(
  request: ExportRequest,
): Promise<Buffer> {
  const pptx = new PptxGenJS();

  // Page size
  pptx.defineLayout({
    name: "CUSTOM",
    width: request.page_size.width,
    height: request.page_size.height,
  });
  pptx.layout = "CUSTOM";

  // Metadata
  pptx.title = `Presentation ${request.presentation_id}`;
  pptx.author = "Ancre";

  // Sort slides by position
  const slides = [...request.slides].sort(
    (a, b) => a.position - b.position,
  );

  for (const slide of slides) {
    const pptSlide = pptx.addSlide();

    // Background color
    if (slide.bg_color) {
      pptSlide.background = {
        fill: slide.bg_color.replace("#", ""),
      };
    }

    // Render each box based on node_type
    for (const box of slide.boxes) {
      renderBox(pptSlide, box, request);
    }
  }

  // Generate buffer
  const output = await pptx.write({ outputType: "nodebuffer" });
  return output as Buffer;
}

/** Dispatch a single box to the correct renderer. */
function renderBox(
  pptSlide: PptxGenJS.Slide,
  box: ResolvedBox,
  request: ExportRequest,
): void {
  switch (box.node_type) {
    case "text":
      if (box.content.type === "bullet_group") {
        addBulletGroup(pptSlide, box, request.theme);
      } else {
        addTextBox(pptSlide, box, request.theme);
      }
      break;

    case "image":
      addImage(pptSlide, box, request.theme, request.assets);
      break;

    case "shape":
      addShape(pptSlide, box, request.theme);
      break;

    case "chart":
      // V2: chart rendering
      addPlaceholderBox(pptSlide, box, "Chart");
      break;

    case "svg":
      // V2: SVG rendering
      addPlaceholderBox(pptSlide, box, "SVG");
      break;

    default:
      console.warn(`Unknown node_type: ${box.node_type}`);
  }
}

/** Placeholder for unsupported node types. */
function addPlaceholderBox(
  pptSlide: PptxGenJS.Slide,
  box: ResolvedBox,
  label: string,
): void {
  pptSlide.addShape("rect", {
    x: box.x,
    y: box.y,
    w: box.w,
    h: box.h,
    fill: { color: "f3f4f6" },
    line: { color: "d1d5db", width: 1 },
  });

  pptSlide.addText(label, {
    x: box.x,
    y: box.y,
    w: box.w,
    h: box.h,
    align: "center",
    valign: "middle",
    color: "6b7280",
    fontSize: 11,
    fontFace: "Arial",
  });
}
