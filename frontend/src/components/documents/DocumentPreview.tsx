/**
 * Read-only document preview — renders blocks in a clean, print-like format.
 * No editing chrome, no block labels/badges, no delete buttons.
 */

import { useEditor, EditorContent } from "@tiptap/react"
import StarterKit from "@tiptap/starter-kit"
import type { DocBlock, DocModel } from "@/types"
import { normalizeProseMirror } from "@/lib/prosemirror"

interface DocumentPreviewProps {
  title: string
  docType: string
  docModel: DocModel | null
}

// ── Read-only Tiptap renderer ──

function ReadOnlyRichText({ content }: { content: Record<string, unknown> }) {
  const normalized = normalizeProseMirror(content)
  const editor = useEditor({
    extensions: [StarterKit],
    content: normalized as Record<string, unknown>,
    editable: false,
  })

  if (!editor) return null

  return (
    <EditorContent
      editor={editor}
      className="prose prose-zinc prose-sm max-w-none [&_.ProseMirror]:outline-none leading-relaxed"
    />
  )
}

// ── Line items table (read-only) ──

function ReadOnlyLineItems({
  block,
}: {
  block: DocBlock
}) {
  const rawItems = block.items || []
  const currency = block.currency || "EUR"

  // Normalize: AI may return strings instead of numbers
  const items = rawItems.map((item) => ({
    ...item,
    quantity: Number(item.quantity) || 0,
    unit_price: Number(item.unit_price) || 0,
    tax_rate: Number(item.tax_rate) || 0,
    total: Number(item.total) || 0,
  }))

  const grandTotal = items.reduce((sum, item) => sum + item.total, 0)

  if (items.length === 0) return null

  return (
    <table className="w-full text-sm border-collapse">
      <thead>
        <tr className="border-b-2 border-foreground/20">
          <th className="text-left py-2 font-semibold">Description</th>
          <th className="text-right py-2 font-semibold w-16">Qte</th>
          <th className="text-left py-2 font-semibold w-16">Unite</th>
          <th className="text-right py-2 font-semibold w-24">P.U.</th>
          <th className="text-right py-2 font-semibold w-16">TVA</th>
          <th className="text-right py-2 font-semibold w-24">Total</th>
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <tr key={item.id} className="border-b border-border/50">
            <td className="py-2">{item.description || ""}</td>
            <td className="py-2 text-right">{item.quantity}</td>
            <td className="py-2">{item.unit || ""}</td>
            <td className="py-2 text-right">
              {item.unit_price.toFixed(2)} {currency}
            </td>
            <td className="py-2 text-right">{item.tax_rate}%</td>
            <td className="py-2 text-right font-medium">
              {item.total.toFixed(2)} {currency}
            </td>
          </tr>
        ))}
      </tbody>
      <tfoot>
        <tr className="border-t-2 border-foreground/20">
          <td colSpan={5} className="py-2 text-right font-semibold">
            Total TTC
          </td>
          <td className="py-2 text-right font-bold">
            {grandTotal.toFixed(2)} {currency}
          </td>
        </tr>
      </tfoot>
    </table>
  )
}

// ── Signature block (read-only) ──

function ReadOnlySignature({ block }: { block: DocBlock }) {
  const parties = block.parties || []
  if (parties.length === 0) return null

  return (
    <div className="flex gap-12 pt-8 mt-4">
      {parties.map((party, i) => {
        const p = party as Record<string, string>
        return (
          <div key={i} className="flex-1">
            <div className="border-b border-foreground/30 pb-16 mb-2" />
            <p className="font-medium text-sm">{p.name || ""}</p>
            <p className="text-xs text-muted-foreground">{p.role || ""}</p>
            {p.date && (
              <p className="text-xs text-muted-foreground mt-1">
                Date : {p.date}
              </p>
            )}
          </div>
        )
      })}
    </div>
  )
}

// ── Block renderer for preview ──

function PreviewBlock({ block }: { block: DocBlock }) {
  switch (block.type) {
    case "rich_text":
    case "clause":
    case "terms":
      if (!block.content || Object.keys(block.content).length === 0) return null
      return <ReadOnlyRichText content={block.content} />

    case "line_items":
      return <ReadOnlyLineItems block={block} />

    case "signature":
      return <ReadOnlySignature block={block} />

    case "variables": {
      const vars = block.variables || {}
      if (Object.keys(vars).length === 0) return null
      return (
        <div className="grid grid-cols-2 gap-x-8 gap-y-1 text-sm">
          {Object.entries(vars).map(([key, val]) => (
            <div key={key} className="flex gap-2">
              <span className="font-medium">{key} :</span>
              <span>{String(val)}</span>
            </div>
          ))}
        </div>
      )
    }

    case "attachments":
      return null // Don't show in preview

    default:
      return null
  }
}

// ── Document type labels ──

const DOC_TYPE_LABELS: Record<string, string> = {
  generic: "Document",
  quote: "Devis",
  invoice: "Facture",
  contract: "Contrat",
  nda: "Accord de confidentialite",
  email: "Email",
  procedure: "Procedure",
}

// ── Main Preview Component ──

export function DocumentPreview({
  title,
  docType,
  docModel,
}: DocumentPreviewProps) {
  const blocks = docModel?.blocks || []

  if (blocks.length === 0) {
    return (
      <div className="flex items-center justify-center py-20 text-sm text-muted-foreground">
        Aucun contenu a previsualiser. Ajoutez des blocs au document.
      </div>
    )
  }

  return (
    <div className="max-w-3xl mx-auto bg-white dark:bg-card rounded-lg shadow-elevated border border-border overflow-hidden print:shadow-none print:border-none">
      {/* Document header */}
      <div className="px-10 pt-10 pb-6 border-b border-border/50">
        <p className="text-xs uppercase tracking-wider text-muted-foreground mb-2">
          {DOC_TYPE_LABELS[docType] || docType}
        </p>
        <h1 className="text-2xl font-bold text-foreground leading-tight">
          {title || "Sans titre"}
        </h1>
      </div>

      {/* Document body */}
      <div className="px-10 py-8 space-y-6">
        {blocks.map((block) => {
          const rendered = <PreviewBlock key={block.id} block={block} />
          if (!rendered) return null

          return (
            <div key={block.id}>
              {block.label && (
                <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
                  {block.label}
                </h3>
              )}
              {rendered}
            </div>
          )
        })}
      </div>

      {/* Document footer */}
      <div className="px-10 py-4 border-t border-border/50 text-xs text-muted-foreground text-center">
        Genere par Ancre — {new Date().toLocaleDateString("fr-FR")}
      </div>
    </div>
  )
}
