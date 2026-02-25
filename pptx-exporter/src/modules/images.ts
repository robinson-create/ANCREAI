/**
 * Image rendering module — root images, inline images → pptxgenjs image objects.
 */

import PptxGenJS from "pptxgenjs";
import type { ResolvedBox, ThemeProperties, AssetManifest } from "../types";

/** Add an image box to a slide. */
export function addImage(
  pptSlide: PptxGenJS.Slide,
  box: ResolvedBox,
  theme: ThemeProperties,
  assets: AssetManifest[],
): void {
  const content = box.content;

  // Find the image URL — either from assets manifest or directly
  let imageUrl: string | undefined;

  if (content.asset_id) {
    const asset = assets.find((a) => a.asset_id === content.asset_id);
    if (asset) {
      imageUrl = asset.presigned_url;
    }
  }

  if (!imageUrl && content.url) {
    imageUrl = content.url;
  }

  if (!imageUrl && content.presigned_url) {
    imageUrl = content.presigned_url;
  }

  if (!imageUrl) {
    // No image available — add a placeholder rectangle
    addPlaceholder(pptSlide, box, theme);
    return;
  }

  const sizing: PptxGenJS.ImageProps["sizing"] = {
    type: "cover",
    w: box.w,
    h: box.h,
  };

  try {
    pptSlide.addImage({
      path: imageUrl,
      x: box.x,
      y: box.y,
      w: box.w,
      h: box.h,
      sizing,
    });
  } catch {
    // If image fails, add placeholder
    addPlaceholder(pptSlide, box, theme);
  }
}

/** Add a colored placeholder rectangle when image is unavailable. */
function addPlaceholder(
  pptSlide: PptxGenJS.Slide,
  box: ResolvedBox,
  theme: ThemeProperties,
): void {
  const bgColor = theme.colors?.muted?.replace("#", "") ?? "e5e7eb";

  pptSlide.addShape("rect", {
    x: box.x,
    y: box.y,
    w: box.w,
    h: box.h,
    fill: { color: bgColor },
  });

  pptSlide.addText("Image", {
    x: box.x,
    y: box.y,
    w: box.w,
    h: box.h,
    align: "center",
    valign: "middle",
    color: "9ca3af",
    fontSize: 12,
    fontFace: "Arial",
  });
}
