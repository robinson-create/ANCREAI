/**
 * Image rendering module — root images, inline images → pptxgenjs image objects.
 */

import http from "node:http";
import https from "node:https";
import PptxGenJS from "pptxgenjs";
import type { ResolvedBox, ThemeProperties, AssetManifest } from "../types.js";

/** Download an image URL to a base64 data URI. Works with both http and https. */
async function fetchImageAsBase64(url: string): Promise<string | null> {
  return new Promise((resolve) => {
    const client = url.startsWith("https") ? https : http;
    client
      .get(url, (res) => {
        if (res.statusCode !== 200) {
          resolve(null);
          res.resume();
          return;
        }
        const chunks: Buffer[] = [];
        res.on("data", (chunk: Buffer) => chunks.push(chunk));
        res.on("end", () => {
          const buffer = Buffer.concat(chunks);
          const contentType = res.headers["content-type"] ?? "image/jpeg";
          const base64 = `data:${contentType};base64,${buffer.toString("base64")}`;
          resolve(base64);
        });
        res.on("error", () => resolve(null));
      })
      .on("error", () => resolve(null));
  });
}

/** Add an image box to a slide. */
export async function addImage(
  pptSlide: PptxGenJS.Slide,
  box: ResolvedBox,
  theme: ThemeProperties,
  assets: AssetManifest[],
): Promise<void> {
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
    addPlaceholder(pptSlide, box, theme);
    return;
  }

  // Pre-download image to base64 (avoids Node.js http/https protocol issues)
  const base64Data = await fetchImageAsBase64(imageUrl);

  if (!base64Data) {
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
      data: base64Data,
      x: box.x,
      y: box.y,
      w: box.w,
      h: box.h,
      sizing,
    });
  } catch {
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
