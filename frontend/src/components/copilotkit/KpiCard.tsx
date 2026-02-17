/**
 * KPI Card - Generative UI component rendered by CopilotKit actions.
 *
 * This card is rendered inline in the CopilotKit chat when the LLM
 * calls the "render_kpi_card" action. It demonstrates how CopilotKit
 * can produce structured UI (not just text) in chat responses.
 */

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { TrendingUp, TrendingDown, Minus, BarChart3 } from "lucide-react"

export interface KpiItem {
  label: string
  value: string | number
  change?: number // percentage change, positive = up
}

export interface KpiCardProps {
  title: string
  description?: string
  kpis: KpiItem[]
  period?: string
}

function TrendIcon({ change }: { change?: number }) {
  if (change === undefined || change === 0) {
    return <Minus className="h-3 w-3 text-muted-foreground" />
  }
  if (change > 0) {
    return <TrendingUp className="h-3 w-3 text-green-600" />
  }
  return <TrendingDown className="h-3 w-3 text-red-600" />
}

function trendColor(change?: number): string {
  if (change === undefined || change === 0) return "text-muted-foreground"
  return change > 0 ? "text-green-600" : "text-red-600"
}

export function KpiCard({ title, description, kpis, period }: KpiCardProps) {
  return (
    <Card className="w-full max-w-md my-2 border-primary/20">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <BarChart3 className="h-5 w-5 text-primary" />
            <CardTitle className="text-base">{title}</CardTitle>
          </div>
          {period && (
            <Badge variant="secondary" className="text-xs">
              {period}
            </Badge>
          )}
        </div>
        {description && (
          <CardDescription className="text-sm">{description}</CardDescription>
        )}
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {kpis.map((kpi, idx) => (
            <div
              key={idx}
              className="flex items-center justify-between rounded-md bg-muted/50 px-3 py-2"
            >
              <span className="text-sm text-muted-foreground">{kpi.label}</span>
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold">{kpi.value}</span>
                {kpi.change !== undefined && (
                  <span
                    className={`flex items-center gap-0.5 text-xs ${trendColor(kpi.change)}`}
                  >
                    <TrendIcon change={kpi.change} />
                    {Math.abs(kpi.change)}%
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
