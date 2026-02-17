import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { AlertTriangle } from "lucide-react"

interface ErrorBlockProps {
  message: string
  raw?: string
}

export function ErrorBlock({ message, raw }: ErrorBlockProps) {
  return (
    <Card className="my-2 border-red-500/30 bg-red-50/50 dark:bg-red-950/20">
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-red-500" />
          <CardTitle className="text-sm text-red-600 dark:text-red-400">
            Block render error
          </CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        <p className="text-xs text-muted-foreground">{message}</p>
        {raw && (
          <pre className="mt-2 max-h-24 overflow-auto rounded bg-muted p-2 text-[10px] text-muted-foreground">
            {raw.length > 300 ? raw.slice(0, 300) + "..." : raw}
          </pre>
        )}
      </CardContent>
    </Card>
  )
}
