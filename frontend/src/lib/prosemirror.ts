/**
 * Normalizes content to a valid ProseMirror/Tiptap JSON document structure.
 * Handles empty, partial, or malformed content from AI or storage.
 */
export function normalizeProseMirror(
  content: Record<string, unknown> | null | undefined
): Record<string, unknown> {
  if (!content || typeof content !== "object") {
    return EMPTY_DOC
  }

  const doc = content as { type?: string; content?: unknown[] }

  if (doc.type === "doc") {
    const contentArray = Array.isArray(doc.content) ? doc.content : []
    return { type: "doc", content: contentArray }
  }

  // Content might be a single block (e.g. from AI)
  if (doc.type && typeof doc.type === "string") {
    return { type: "doc", content: [doc] }
  }

  // Plain object without type - wrap as paragraph if it has text
  const text = "text" in doc ? String(doc.text) : null
  if (text) {
    return {
      type: "doc",
      content: [{ type: "paragraph", content: [{ type: "text", text }] }],
    }
  }

  return EMPTY_DOC
}

const EMPTY_DOC: Record<string, unknown> = {
  type: "doc",
  content: [{ type: "paragraph" }],
}
