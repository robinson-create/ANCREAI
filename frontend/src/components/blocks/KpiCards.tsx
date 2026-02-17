import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { TrendingUp, TrendingDown, Minus, BarChart3 } from "lucide-react"
import type { KpiCardsPayload } from "@/schemas/blocks"

function parseDelta(delta?: string): number | undefined {
  if (!delta) return undefined
  const n = parseFloat(delta.replace(/[^0-9.\-+]/g, ""))
  return Number.isNaN(n) ? undefined : n
}

function TrendIcon({ value }: { value?: number }) {
  if (value === undefined || value === 0)
    return <Minus className="h-3 w-3 text-muted-foreground" />
  if (value > 0) return <TrendingUp className="h-3 w-3 text-green-600" />
  return <TrendingDown className="h-3 w-3 text-red-600" />
}

function trendColor(value?: number): string {
  if (value === undefined || value === 0) return "text-muted-foreground"
  return value > 0 ? "text-green-600" : "text-red-600"
}

export function KpiCards({ title, items }: KpiCardsPayload) {
  return (
    <Card className="w-full my-2 border-primary/20">
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <BarChart3 className="h-5 w-5 text-primary" />
          <CardTitle className="text-base">{title || "KPIs"}</CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {items.map((item, idx) => {
            const numDelta = parseDelta(item.delta)
            return (
              <div
                key={idx}
                className="flex items-center justify-between rounded-md bg-muted/50 px-3 py-2"
              >
                <span className="text-sm text-muted-foreground">
                  {item.label}
                </span>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold">{item.value}</span>
                  {item.delta && (
                    <span
                      className={`flex items-center gap-0.5 text-xs ${trendColor(numDelta)}`}
                    >
                      <TrendIcon value={numDelta} />
                      {item.delta}
                    </span>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}
