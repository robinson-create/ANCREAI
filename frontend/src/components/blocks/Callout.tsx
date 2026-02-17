import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Info, AlertTriangle, CheckCircle2, XCircle } from "lucide-react"
import type { CalloutPayload } from "@/schemas/blocks"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

const toneConfig = {
  info: {
    icon: Info,
    className: "border-blue-500/30 bg-blue-50/50 dark:bg-blue-950/20",
  },
  warning: {
    icon: AlertTriangle,
    className: "border-yellow-500/30 bg-yellow-50/50 dark:bg-yellow-950/20",
  },
  success: {
    icon: CheckCircle2,
    className: "border-green-500/30 bg-green-50/50 dark:bg-green-950/20",
  },
  danger: {
    icon: XCircle,
    className: "border-red-500/30 bg-red-50/50 dark:bg-red-950/20",
  },
}

export function Callout({ tone, title, message }: CalloutPayload) {
  const config = toneConfig[tone] || toneConfig.info
  const Icon = config.icon

  return (
    <Alert className={`my-2 ${config.className}`}>
      <Icon className="h-4 w-4" />
      {title && <AlertTitle>{title}</AlertTitle>}
      <AlertDescription className="prose prose-sm max-w-none dark:prose-invert">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{message}</ReactMarkdown>
      </AlertDescription>
    </Alert>
  )
}
