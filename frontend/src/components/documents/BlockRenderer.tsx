import { TiptapCanvas } from "./TiptapCanvas"
import { LineItemsTable } from "./LineItemsTable"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Trash2, Plus } from "lucide-react"
import type { DocBlock, LineItemData } from "@/types"

interface BlockRendererProps {
  block: DocBlock
  onChange: (patch: Partial<DocBlock>) => void
  onRemove: () => void
}

export function BlockRenderer({
  block,
  onChange,
  onRemove,
}: BlockRendererProps) {
  const renderContent = () => {
    switch (block.type) {
      case "rich_text":
        return (
          <TiptapCanvas
            blockId={block.id}
            content={block.content || {}}
            onChange={(content) => onChange({ content })}
            editable={!block.locked}
          />
        )

      case "clause":
        return (
          <div className="space-y-1">
            {block.clause_ref && (
              <p className="text-xs text-muted-foreground">
                Ref: {block.clause_ref}
              </p>
            )}
            <TiptapCanvas
              blockId={block.id}
              content={block.content || {}}
              onChange={(content) => onChange({ content })}
              editable={!block.locked}
              placeholder="Redigez la clause..."
            />
          </div>
        )

      case "terms":
        return (
          <TiptapCanvas
            blockId={block.id}
            content={block.content || {}}
            onChange={(content) => onChange({ content })}
            editable={!block.locked}
            placeholder="Conditions generales..."
          />
        )

      case "line_items":
        return (
          <LineItemsTable
            blockId={block.id}
            items={block.items || []}
            currency={block.currency || "EUR"}
            onChange={(items: LineItemData[]) => onChange({ items })}
          />
        )

      case "signature": {
        const parties = (block.parties || []) as Record<string, string>[]
        const updateParty = (idx: number, field: string, value: string) => {
          const updated = parties.map((p, i) =>
            i === idx ? { ...p, [field]: value } : p
          )
          onChange({ parties: updated })
        }
        const addParty = () => {
          onChange({ parties: [...parties, { name: "", role: "" }] })
        }
        const removeParty = (idx: number) => {
          onChange({ parties: parties.filter((_, i) => i !== idx) })
        }
        return (
          <div className="space-y-4 pt-4">
            <div className="flex flex-wrap gap-6">
              {parties.map((party, i) => (
                <div key={i} className="flex-1 min-w-[200px] border-t pt-3 space-y-2">
                  <Input
                    value={party.name || ""}
                    onChange={(e) => updateParty(i, "name", e.target.value)}
                    placeholder="Nom"
                    className="font-medium h-8"
                  />
                  <Input
                    value={party.role || ""}
                    onChange={(e) => updateParty(i, "role", e.target.value)}
                    placeholder="Role (ex: Emetteur)"
                    className="text-sm h-8"
                  />
                  {parties.length > 1 && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 text-xs text-muted-foreground hover:text-destructive px-1"
                      onClick={() => removeParty(i)}
                    >
                      <Trash2 className="h-3 w-3 mr-1" />
                      Retirer
                    </Button>
                  )}
                </div>
              ))}
            </div>
            <Button
              variant="outline"
              size="sm"
              className="h-7 text-xs"
              onClick={addParty}
            >
              <Plus className="h-3 w-3 mr-1" />
              Ajouter un signataire
            </Button>
          </div>
        )
      }

      case "attachments":
        return (
          <div className="space-y-1">
            {(block.files || []).map((file, i) => (
              <div
                key={i}
                className="flex items-center gap-2 text-sm text-muted-foreground"
              >
                <span>
                  {(file as Record<string, string>).filename ||
                    (file as Record<string, string>).name ||
                    "Fichier"}
                </span>
              </div>
            ))}
            {(!block.files || block.files.length === 0) && (
              <p className="text-sm text-muted-foreground italic">
                Aucune piece jointe
              </p>
            )}
          </div>
        )

      case "variables":
        return (
          <div className="grid grid-cols-2 gap-2 text-sm">
            {Object.entries(block.variables || {}).map(([key, val]) => (
              <div key={key} className="flex gap-2">
                <span className="font-medium">{key}:</span>
                <span className="text-muted-foreground">{String(val)}</span>
              </div>
            ))}
          </div>
        )

      default:
        return (
          <p className="text-sm text-muted-foreground italic">
            Bloc non supporte: {block.type}
          </p>
        )
    }
  }

  return (
    <div className="group relative">
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          {block.label && (
            <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              {block.label}
            </span>
          )}
          <Badge variant="outline" className="text-[10px] py-0">
            {block.type}
          </Badge>
          {block.locked && (
            <Badge variant="secondary" className="text-[10px] py-0">
              verrouille
            </Badge>
          )}
        </div>
        <Button
          variant="ghost"
          size="sm"
          className="h-6 w-6 p-0 opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-destructive"
          onClick={onRemove}
        >
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      </div>
      {renderContent()}
    </div>
  )
}
