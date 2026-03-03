/**
 * Shared utilities for slide data processing.
 */

/** Strip markdown formatting from a string (bold, italic, code, links, headers). */
export function stripMarkdown(text: string): string {
  if (!text) return text;
  let s = text;
  s = s.replace(/\*\*(.+?)\*\*/g, "$1");
  s = s.replace(/__(.+?)__/g, "$1");
  s = s.replace(/\*(.+?)\*/g, "$1");
  s = s.replace(/(?<!\w)_(.+?)_(?!\w)/g, "$1");
  s = s.replace(/`(.+?)`/g, "$1");
  s = s.replace(/\[(.+?)\]\(.+?\)/g, "$1");
  s = s.replace(/^#{1,6}\s+/gm, "");
  return s;
}

/** Recursively strip markdown from all string values in a data object. */
export function cleanData(obj: Record<string, any>): Record<string, any> {
  const result: Record<string, any> = {};
  for (const [key, value] of Object.entries(obj)) {
    if (typeof value === "string") {
      result[key] = stripMarkdown(value);
    } else if (Array.isArray(value)) {
      result[key] = value.map((item) =>
        typeof item === "object" && item !== null && !Array.isArray(item)
          ? cleanData(item)
          : typeof item === "string"
            ? stripMarkdown(item)
            : item
      );
    } else if (typeof value === "object" && value !== null) {
      result[key] = cleanData(value);
    } else {
      result[key] = value;
    }
  }
  return result;
}
