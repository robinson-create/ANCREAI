import { useCallback } from "react"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  TableFooter,
} from "@/components/ui/table"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Plus, Trash2 } from "lucide-react"
import type { LineItemData } from "@/types"

interface LineItemsTableProps {
  blockId: string
  items: LineItemData[]
  currency?: string
  onChange: (items: LineItemData[]) => void
}

function generateId() {
  return crypto.randomUUID()
}

export function LineItemsTable({
  blockId: _blockId,
  items,
  currency = "EUR",
  onChange,
}: LineItemsTableProps) {
  const updateItem = useCallback(
    (index: number, field: keyof LineItemData, value: string | number) => {
      const updated = items.map((item, i) => {
        if (i !== index) return item
        const newItem = { ...item, [field]: value }
        // Auto-calc total
        if (
          field === "quantity" ||
          field === "unit_price" ||
          field === "tax_rate"
        ) {
          const qty =
            field === "quantity" ? Number(value) : Number(newItem.quantity)
          const price =
            field === "unit_price" ? Number(value) : Number(newItem.unit_price)
          const tax =
            field === "tax_rate" ? Number(value) : Number(newItem.tax_rate)
          newItem.total = Math.round(qty * price * (1 + tax / 100) * 100) / 100
        }
        return newItem
      })
      onChange(updated)
    },
    [items, onChange]
  )

  const addRow = useCallback(() => {
    const newItem: LineItemData = {
      id: generateId(),
      description: "",
      quantity: 1,
      unit: "unite",
      unit_price: 0,
      tax_rate: 20,
      total: 0,
    }
    onChange([...items, newItem])
  }, [items, onChange])

  const removeRow = useCallback(
    (index: number) => {
      onChange(items.filter((_, i) => i !== index))
    },
    [items, onChange]
  )

  // Normalize items to ensure all numeric fields have defaults (AI may omit some)
  const safeItems = items.map((item) => ({
    ...item,
    quantity: item.quantity ?? 0,
    unit_price: item.unit_price ?? 0,
    tax_rate: item.tax_rate ?? 0,
    total: item.total ?? 0,
    unit: item.unit ?? "",
    description: item.description ?? "",
  }))

  const grandTotal = safeItems.reduce((sum, item) => sum + (item.total || 0), 0)

  return (
    <div className="border rounded-lg overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-[40%]">Description</TableHead>
            <TableHead className="w-[10%] text-right">Qte</TableHead>
            <TableHead className="w-[10%]">Unite</TableHead>
            <TableHead className="w-[15%] text-right">
              P.U. ({currency})
            </TableHead>
            <TableHead className="w-[10%] text-right">TVA %</TableHead>
            <TableHead className="w-[15%] text-right">
              Total ({currency})
            </TableHead>
            <TableHead className="w-8" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {safeItems.map((item, index) => (
            <TableRow key={item.id}>
              <TableCell>
                <Input
                  value={item.description}
                  onChange={(e) =>
                    updateItem(index, "description", e.target.value)
                  }
                  className="h-8 border-0 shadow-none bg-transparent"
                  placeholder="Description..."
                />
              </TableCell>
              <TableCell>
                <Input
                  type="number"
                  value={item.quantity}
                  onChange={(e) =>
                    updateItem(index, "quantity", parseFloat(e.target.value) || 0)
                  }
                  className="h-8 border-0 shadow-none bg-transparent text-right"
                />
              </TableCell>
              <TableCell>
                <Input
                  value={item.unit}
                  onChange={(e) => updateItem(index, "unit", e.target.value)}
                  className="h-8 border-0 shadow-none bg-transparent"
                />
              </TableCell>
              <TableCell>
                <Input
                  type="number"
                  step="0.01"
                  value={item.unit_price}
                  onChange={(e) =>
                    updateItem(
                      index,
                      "unit_price",
                      parseFloat(e.target.value) || 0
                    )
                  }
                  className="h-8 border-0 shadow-none bg-transparent text-right"
                />
              </TableCell>
              <TableCell>
                <Input
                  type="number"
                  step="0.1"
                  value={item.tax_rate}
                  onChange={(e) =>
                    updateItem(
                      index,
                      "tax_rate",
                      parseFloat(e.target.value) || 0
                    )
                  }
                  className="h-8 border-0 shadow-none bg-transparent text-right"
                />
              </TableCell>
              <TableCell className="text-right font-medium tabular-nums">
                {item.total.toFixed(2)}
              </TableCell>
              <TableCell>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive"
                  onClick={() => removeRow(index)}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
        <TableFooter>
          <TableRow>
            <TableCell colSpan={5} className="text-right font-semibold">
              Total TTC
            </TableCell>
            <TableCell className="text-right font-bold tabular-nums">
              {grandTotal.toFixed(2)} {currency}
            </TableCell>
            <TableCell />
          </TableRow>
        </TableFooter>
      </Table>
      <div className="px-3 py-2 border-t bg-muted/30">
        <Button
          variant="ghost"
          size="sm"
          className="text-xs"
          onClick={addRow}
        >
          <Plus className="h-3.5 w-3.5 mr-1" />
          Ajouter une ligne
        </Button>
      </div>
    </div>
  )
}
