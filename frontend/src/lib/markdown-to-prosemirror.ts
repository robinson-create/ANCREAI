/**
 * Convert markdown text to ProseMirror JSON structure for TipTap.
 * Uses marked's lexer to parse markdown tokens, then maps them
 * to ProseMirror-compatible nodes.
 */
import { marked, type Token, type Tokens } from "marked";

interface PMNode {
  type: string;
  attrs?: Record<string, unknown>;
  content?: PMNode[];
  text?: string;
  marks?: PMMark[];
}

interface PMMark {
  type: string;
  attrs?: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Inline tokens → ProseMirror text nodes with marks
// ---------------------------------------------------------------------------

function inlineTokensToNodes(tokens: Token[]): PMNode[] {
  const nodes: PMNode[] = [];

  for (const token of tokens) {
    switch (token.type) {
      case "text": {
        const t = token as Tokens.Text;
        if (t.tokens && t.tokens.length > 0) {
          nodes.push(...inlineTokensToNodes(t.tokens));
        } else {
          // Split on newlines to create separate text/hardBreak nodes
          const parts = t.text.split("\n");
          parts.forEach((part: string, i: number) => {
            if (part) nodes.push({ type: "text", text: part });
            if (i < parts.length - 1) nodes.push({ type: "hardBreak" });
          });
        }
        break;
      }
      case "strong": {
        const s = token as Tokens.Strong;
        const children = inlineTokensToNodes(s.tokens || []);
        for (const child of children) {
          if (child.type === "hardBreak") {
            nodes.push(child);
          } else {
            nodes.push({
              ...child,
              marks: [...(child.marks || []), { type: "bold" }],
            });
          }
        }
        break;
      }
      case "em": {
        const e = token as Tokens.Em;
        const children = inlineTokensToNodes(e.tokens || []);
        for (const child of children) {
          if (child.type === "hardBreak") {
            nodes.push(child);
          } else {
            nodes.push({
              ...child,
              marks: [...(child.marks || []), { type: "italic" }],
            });
          }
        }
        break;
      }
      case "codespan": {
        const c = token as Tokens.Codespan;
        nodes.push({
          type: "text",
          text: c.text,
          marks: [{ type: "code" }],
        });
        break;
      }
      case "br":
        nodes.push({ type: "hardBreak" });
        break;
      default: {
        // Fallback: extract raw text
        const raw = (token as Record<string, unknown>).text;
        if (typeof raw === "string" && raw) {
          nodes.push({ type: "text", text: raw });
        }
        break;
      }
    }
  }

  return nodes;
}

// ---------------------------------------------------------------------------
// Block tokens → ProseMirror block nodes
// ---------------------------------------------------------------------------

function blockTokensToNodes(tokens: Token[]): PMNode[] {
  const nodes: PMNode[] = [];

  for (const token of tokens) {
    switch (token.type) {
      case "heading": {
        const h = token as Tokens.Heading;
        const content = inlineTokensToNodes(h.tokens || []);
        nodes.push({
          type: "heading",
          attrs: { level: h.depth },
          ...(content.length > 0 ? { content } : {}),
        });
        break;
      }
      case "paragraph": {
        const p = token as Tokens.Paragraph;
        const content = inlineTokensToNodes(p.tokens || []);
        nodes.push({
          type: "paragraph",
          ...(content.length > 0 ? { content } : {}),
        });
        break;
      }
      case "list": {
        const l = token as Tokens.List;
        const listType = l.ordered ? "orderedList" : "bulletList";
        const items = l.items.map((item: Tokens.ListItem) => {
          const itemContent = blockTokensToNodes(item.tokens || []);
          return {
            type: "listItem" as const,
            content:
              itemContent.length > 0
                ? itemContent
                : [{ type: "paragraph" as const }],
          };
        });
        nodes.push({
          type: listType,
          ...(items.length > 0 ? { content: items } : {}),
        });
        break;
      }
      case "blockquote": {
        const bq = token as Tokens.Blockquote;
        const content = blockTokensToNodes(bq.tokens || []);
        nodes.push({
          type: "blockquote",
          content: content.length > 0 ? content : [{ type: "paragraph" }],
        });
        break;
      }
      case "hr":
        nodes.push({ type: "horizontalRule" });
        break;
      case "code":
        // Skip code blocks — not useful in rich-text documents
        break;
      case "space":
        // Ignore whitespace tokens
        break;
      default: {
        // Fallback: try to extract text as paragraph
        const raw = (token as Record<string, unknown>).text;
        if (typeof raw === "string" && raw.trim()) {
          nodes.push({
            type: "paragraph",
            content: [{ type: "text", text: raw.trim() }],
          });
        }
        break;
      }
    }
  }

  return nodes;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Convert a markdown string to a ProseMirror JSON document.
 */
export function markdownToProseMirrorDoc(
  markdown: string
): Record<string, unknown> {
  if (!markdown || !markdown.trim()) {
    return { type: "doc", content: [{ type: "paragraph" }] };
  }

  const tokens = marked.lexer(markdown);
  const nodes = blockTokensToNodes(tokens);

  return {
    type: "doc",
    content: nodes.length > 0 ? nodes : [{ type: "paragraph" }],
  };
}

/**
 * Split markdown into sections based on h2/h3 headings.
 * Each section becomes a separate document block in the editor.
 *
 * Returns an array of { label, doc } where:
 * - label: the heading text (empty string for the preamble before first heading)
 * - doc: ProseMirror JSON document for that section
 */
export function splitMarkdownIntoSections(
  markdown: string
): { label: string; doc: Record<string, unknown> }[] {
  if (!markdown || !markdown.trim()) {
    return [
      { label: "", doc: { type: "doc", content: [{ type: "paragraph" }] } },
    ];
  }

  const tokens = marked.lexer(markdown);

  // Group tokens into sections split at h2/h3 boundaries
  const sections: { label: string; tokens: Token[] }[] = [];
  let current: { label: string; tokens: Token[] } = {
    label: "",
    tokens: [],
  };

  for (const token of tokens) {
    if (token.type === "heading" && (token as Tokens.Heading).depth <= 3) {
      // Push previous section if it has content
      if (current.tokens.length > 0) {
        sections.push(current);
      }
      // Start new section — heading is included in the section content
      current = {
        label: (token as Tokens.Heading).text,
        tokens: [token],
      };
    } else {
      current.tokens.push(token);
    }
  }

  // Push final section
  if (current.tokens.length > 0) {
    sections.push(current);
  }

  // If only one section or no headings, return as single block
  if (sections.length <= 1) {
    return [{ label: "", doc: markdownToProseMirrorDoc(markdown) }];
  }

  return sections.map((section) => {
    const nodes = blockTokensToNodes(section.tokens);
    return {
      label: section.label,
      doc: {
        type: "doc" as const,
        content: nodes.length > 0 ? nodes : [{ type: "paragraph" }],
      },
    };
  });
}
