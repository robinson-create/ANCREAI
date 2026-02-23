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
    // Validate and fix content nodes
    const validatedContent = validateAndFixNodes(contentArray)
    return { type: "doc", content: validatedContent }
  }

  // Content might be a single block (e.g. from AI)
  if (doc.type && typeof doc.type === "string") {
    const validatedContent = validateAndFixNodes([doc])
    return { type: "doc", content: validatedContent }
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

/**
 * Validates and fixes an array of ProseMirror nodes.
 * Filters out invalid nodes and wraps orphan list items.
 */
function validateAndFixNodes(nodes: unknown[]): unknown[] {
  const result: unknown[] = []
  const orphanListItems: unknown[] = []

  for (const node of nodes) {
    if (!node || typeof node !== "object") continue

    const n = node as { type?: string; content?: unknown[] }
    const nodeType = n.type

    // Skip completely invalid nodes
    if (!nodeType || typeof nodeType !== "string") continue

    // Handle orphan list_item nodes (should be listItem in TipTap)
    if (nodeType === "list_item" || nodeType === "listItem") {
      // Normalize to TipTap's naming convention
      orphanListItems.push({ ...n, type: "listItem" })
      continue
    }

    // Recursively validate nested content
    if (n.content && Array.isArray(n.content)) {
      const validatedNestedContent = validateAndFixNodes(n.content)
      result.push({ ...n, content: validatedNestedContent })
    } else {
      result.push(node)
    }
  }

  // Wrap orphan list items in a bullet list
  if (orphanListItems.length > 0) {
    result.push({
      type: "bulletList",
      content: orphanListItems,
    })
  }

  // If no valid content, return an empty paragraph
  return result.length > 0 ? result : [{ type: "paragraph" }]
}

const EMPTY_DOC: Record<string, unknown> = {
  type: "doc",
  content: [{ type: "paragraph" }],
}
