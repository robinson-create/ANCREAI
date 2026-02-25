/**
 * Shape rendering module — backgrounds, decorations → pptxgenjs shapes.
 */

import PptxGenJS from "pptxgenjs";
import type { ResolvedBox, ThemeProperties } from "../types";

/** Add a background/fill shape to a slide. */
export function addShape(
  pptSlide: PptxGenJS.Slide,
  box: ResolvedBox,
  theme: ThemeProperties,
): void {
  const content = box.content;
  const fill = content.fill as string | undefined;

  if (!fill) return;

  const color = fill.replace("#", "");

  pptSlide.addShape("rect", {
    x: box.x,
    y: box.y,
    w: box.w,
    h: box.h,
    fill: { color },
    line: { width: 0 },
  });
}
