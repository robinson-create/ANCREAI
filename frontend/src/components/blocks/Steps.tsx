import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { ListChecks, Circle, Loader2, CheckCircle2 } from "lucide-react"
import type { StepsPayload } from "@/schemas/blocks"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

const statusConfig = {
  todo: {
    icon: Circle,
    label: "À faire",
    variant: "outline" as const,
  },
  doing: {
    icon: Loader2,
    label: "En cours",
    variant: "default" as const,
  },
  done: {
    icon: CheckCircle2,
    label: "Terminé",
    variant: "secondary" as const,
  },
}

export function Steps({ title, steps }: StepsPayload) {
  return (
    <Card className="w-full my-2 border-primary/20">
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <ListChecks className="h-5 w-5 text-primary" />
          <CardTitle className="text-base">{title || "Étapes"}</CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        <div className="relative space-y-4">
          {steps.map((step, idx) => {
            const status = step.status || "todo"
            const config = statusConfig[status]
            const Icon = config.icon
            return (
              <div key={idx} className="flex gap-3">
                {/* Step number + connector line */}
                <div className="flex flex-col items-center">
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border bg-background text-xs font-medium">
                    {idx + 1}
                  </div>
                  {idx < steps.length - 1 && (
                    <div className="mt-1 h-full w-px bg-border" />
                  )}
                </div>
                {/* Step content */}
                <div className="flex-1 pb-2">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium">{step.title}</p>
                    <Badge variant={config.variant} className="text-[10px] px-1.5 py-0">
                      <Icon className="mr-1 h-3 w-3" />
                      {config.label}
                    </Badge>
                  </div>
                  {step.description && (
                    <div className="mt-1 text-xs text-muted-foreground prose prose-sm max-w-none dark:prose-invert">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{step.description}</ReactMarkdown>
                    </div>
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
