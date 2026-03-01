import { useState, useCallback } from "react"
import { ChevronUp, ChevronDown, Plus, Trash2, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import type { OutlineItem, PresentationFull } from "@/types"

interface OutlineEditorProps {
  presentation: PresentationFull
  onSaveOutline: (outline: OutlineItem[]) => void
  onGenerateSlides: () => void
  isSaving: boolean
}

export function OutlineEditor({
  presentation,
  onSaveOutline,
  onGenerateSlides,
  isSaving,
}: OutlineEditorProps) {
  const [items, setItems] = useState<OutlineItem[]>(
    presentation.outline.length > 0
      ? presentation.outline
      : [{ title: "Introduction", bullets: [] }],
  )
  const [dirty, setDirty] = useState(false)

  const update = useCallback((newItems: OutlineItem[]) => {
    setItems(newItems)
    setDirty(true)
  }, [])

  const handleSave = useCallback(() => {
    onSaveOutline(items)
    setDirty(false)
  }, [items, onSaveOutline])

  const moveItem = useCallback(
    (index: number, direction: "up" | "down") => {
      const next = [...items]
      const target = direction === "up" ? index - 1 : index + 1
      if (target < 0 || target >= next.length) return
      const temp = next[index]!
      next[index] = next[target]!
      next[target] = temp
      update(next)
    },
    [items, update],
  )

  const updateTitle = useCallback(
    (index: number, title: string) => {
      const next = [...items]
      const item = next[index]
      if (!item) return
      next[index] = { title, bullets: item.bullets }
      update(next)
    },
    [items, update],
  )

  const updateBullet = useCallback(
    (itemIdx: number, bulletIdx: number, text: string) => {
      const next = [...items]
      const item = next[itemIdx]
      if (!item) return
      const bullets = [...item.bullets]
      bullets[bulletIdx] = text
      next[itemIdx] = { title: item.title, bullets }
      update(next)
    },
    [items, update],
  )

  const addBullet = useCallback(
    (itemIdx: number) => {
      const next = [...items]
      const item = next[itemIdx]
      if (!item) return
      next[itemIdx] = { title: item.title, bullets: [...item.bullets, ""] }
      update(next)
    },
    [items, update],
  )

  const removeBullet = useCallback(
    (itemIdx: number, bulletIdx: number) => {
      const next = [...items]
      const item = next[itemIdx]
      if (!item) return
      next[itemIdx] = { title: item.title, bullets: item.bullets.filter((_, i) => i !== bulletIdx) }
      update(next)
    },
    [items, update],
  )

  const removeItem = useCallback(
    (index: number) => {
      update(items.filter((_, i) => i !== index))
    },
    [items, update],
  )

  const addItem = useCallback(() => {
    update([...items, { title: "Nouvelle section", bullets: [] }])
  }, [items, update])

  return (
    <div className="max-w-4xl mx-auto px-4 py-6 space-y-4 overflow-y-auto h-full">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Plan de la présentation</h2>
        {dirty && (
          <Button variant="outline" size="sm" onClick={handleSave} disabled={isSaving}>
            {isSaving ? "Enregistrement..." : "Enregistrer"}
          </Button>
        )}
      </div>

      <div className="space-y-3">
        {items.map((item, itemIdx) => (
          <div
            key={itemIdx}
            className="border rounded-lg p-4 bg-card space-y-2"
          >
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-muted-foreground w-6 shrink-0">
                {itemIdx + 1}.
              </span>

              <div className="flex flex-col gap-0.5 shrink-0">
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-5 w-5"
                  disabled={itemIdx === 0}
                  onClick={() => moveItem(itemIdx, "up")}
                >
                  <ChevronUp className="h-3 w-3" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-5 w-5"
                  disabled={itemIdx === items.length - 1}
                  onClick={() => moveItem(itemIdx, "down")}
                >
                  <ChevronDown className="h-3 w-3" />
                </Button>
              </div>

              <Input
                value={item.title}
                onChange={(e) => updateTitle(itemIdx, e.target.value)}
                className="font-medium flex-1 min-w-0"
                placeholder="Titre de la section"
              />

              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 text-muted-foreground hover:text-destructive shrink-0"
                onClick={() => removeItem(itemIdx)}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>

            {/* Bullets */}
            <div className="pl-14 space-y-1.5">
              {item.bullets.map((bullet, bulletIdx) => (
                <div key={bulletIdx} className="flex items-center gap-2">
                  <span className="text-muted-foreground text-xs">•</span>
                  <Input
                    value={bullet}
                    onChange={(e) =>
                      updateBullet(itemIdx, bulletIdx, e.target.value)
                    }
                    className="h-8 text-sm flex-1 min-w-0"
                    placeholder="Point clé"
                  />
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6 text-muted-foreground hover:text-destructive shrink-0"
                    onClick={() => removeBullet(itemIdx, bulletIdx)}
                  >
                    <X className="h-3 w-3" />
                  </Button>
                </div>
              ))}
              <Button
                variant="ghost"
                size="sm"
                className="h-7 text-xs text-muted-foreground"
                onClick={() => addBullet(itemIdx)}
              >
                <Plus className="h-3 w-3 mr-1" />
                Ajouter un point
              </Button>
            </div>
          </div>
        ))}
      </div>

      <Button variant="outline" onClick={addItem} className="w-full">
        <Plus className="h-4 w-4 mr-2" />
        Ajouter une section
      </Button>

      <div className="pt-4 border-t">
        <Button onClick={onGenerateSlides} className="w-full" size="lg">
          Générer les slides
        </Button>
        <p className="text-xs text-muted-foreground text-center mt-2">
          {items.length} section{items.length > 1 ? "s" : ""} dans le plan
        </p>
      </div>
    </div>
  )
}
