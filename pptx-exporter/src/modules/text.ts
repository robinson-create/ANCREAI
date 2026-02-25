/**
 * Text rendering module — headings, paragraphs, bullets → pptxgenjs text objects.
 */

import PptxGenJS from "pptxgenjs";
import type { ResolvedBox, ThemeProperties } from "../types";

// Font fallback map
const FONT_FALLBACKS: Record<string, string> = {
  Inter: "Inter",
  Poppins: "Poppins",
  Montserrat: "Montserrat",
  Roboto: "Roboto",
  "Open Sans": "Open Sans",
  Arial: "Arial",
  _default: "Arial",
};

function resolveFont(requested: string | undefined): string {
  if (!requested) return FONT_FALLBACKS._default;
  return FONT_FALLBACKS[requested] ?? FONT_FALLBACKS._default;
}

/** Extract plain text recursively from Plate-style nodes. */
function extractText(node: Record<string, any>): string {
  if (node.text !== undefined) return String(node.text);
  const children = node.children ?? [];
  return children.map((c: Record<string, any>) => extractText(c)).join("");
}

/** Convert px string to pt number. */
function pxToPt(value: string | number | undefined): number | undefined {
  if (value === undefined || value === null) return undefined;
  const s = String(value);
  if (s.endsWith("px")) {
    return Math.round(parseFloat(s) * 0.75);
  }
  if (s.endsWith("pt")) {
    return Math.round(parseFloat(s));
  }
  const n = parseFloat(s);
  return isNaN(n) ? undefined : Math.round(n);
}

/** Map node type to default font size in pt. */
function defaultFontSize(nodeType: string): number {
  const map: Record<string, number> = {
    h1: 36,
    h2: 28,
    h3: 22,
    h4: 18,
    h5: 16,
    h6: 14,
    p: 16,
  };
  return map[nodeType] ?? 16;
}

/** Build text options from a Plate text leaf. */
function leafToTextProps(
  leaf: Record<string, any>,
  theme: ThemeProperties,
  nodeType: string,
): PptxGenJS.TextProps {
  const isHeading = nodeType.startsWith("h");
  const fontFamily = resolveFont(
    leaf.font_family ?? (isHeading ? theme.fonts?.heading : theme.fonts?.body),
  );
  const color = isHeading
    ? theme.colors?.heading?.replace("#", "") ?? "1a1a2e"
    : theme.colors?.text?.replace("#", "") ?? "333333";

  return {
    text: leaf.text ?? "",
    options: {
      fontFace: fontFamily,
      fontSize: pxToPt(leaf.font_size) ?? defaultFontSize(nodeType),
      color,
      bold: leaf.bold ?? isHeading,
      italic: leaf.italic ?? false,
      underline: leaf.underline ? { style: "sng" } : undefined,
    },
  };
}

/** Render a text box (heading or paragraph) on a slide. */
export function addTextBox(
  pptSlide: PptxGenJS.Slide,
  box: ResolvedBox,
  theme: ThemeProperties,
): void {
  const node = box.content;
  const nodeType = node.type ?? "p";
  const children = node.children ?? [];

  const textProps: PptxGenJS.TextProps[] = children.map(
    (child: Record<string, any>) => leafToTextProps(child, theme, nodeType),
  );

  if (textProps.length === 0) return;

  const align = node.align ?? (nodeType === "h1" ? "center" : "left");

  pptSlide.addText(textProps, {
    x: box.x,
    y: box.y,
    w: box.w,
    h: box.h,
    align: align as PptxGenJS.HAlign,
    valign: "top",
    wrap: true,
    shrinkText: true,
    margin: [0.05, 0.1, 0.05, 0.1],
  });
}

/** Render a bullet group as a multi-line text box. */
export function addBulletGroup(
  pptSlide: PptxGenJS.Slide,
  box: ResolvedBox,
  theme: ThemeProperties,
): void {
  const node = box.content;
  const items = node.children ?? [];
  const textProps: PptxGenJS.TextProps[] = [];

  for (const item of items) {
    const itemChildren = item.children ?? [];
    for (const child of itemChildren) {
      const cType = child.type ?? "p";
      const text = extractText(child);
      if (!text) continue;

      const isTitle = cType.startsWith("h");
      textProps.push({
        text,
        options: {
          fontFace: resolveFont(
            isTitle ? theme.fonts?.heading : theme.fonts?.body,
          ),
          fontSize: isTitle ? 18 : 14,
          color: isTitle
            ? theme.colors?.heading?.replace("#", "") ?? "1a1a2e"
            : theme.colors?.text?.replace("#", "") ?? "333333",
          bold: isTitle,
          bullet: !isTitle ? { type: "bullet" } : undefined,
          breakLine: true,
          paraSpaceAfter: isTitle ? 2 : 6,
        },
      });
    }
  }

  if (textProps.length === 0) return;

  pptSlide.addText(textProps, {
    x: box.x,
    y: box.y,
    w: box.w,
    h: box.h,
    valign: "top",
    wrap: true,
    shrinkText: true,
    margin: [0.1, 0.15, 0.1, 0.15],
  });
}
